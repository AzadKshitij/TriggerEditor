"""The app reaches the network in one place, and only when the user asks.

Phase 5 of the AI plan (``docs/plans/2026-11-13-ai-first-bring-your-own-harness.md``)
adds a single user-initiated download, ``core/modules/downloader.py``. Everything
else must stay offline. This module checks that three ways, cheapest first:

1. A static scan of every file under ``src/trigger_designer``. No file except the
   downloader imports a networking library, calls a connection function, or uses
   ``socket``. The three files that read the computer's name may import
   ``socket`` and use nothing from it but ``gethostname`` and ``getfqdn``.
2. Import hygiene. Importing the module package, the command line and the agent
   tools adds no networking module to what a bare interpreter already loads.
3. Runtime. With every connection function replaced by a recorder that refuses,
   the offline paths run to the end and the recorder is never called.

A failure means a change added a network path. Remove the path, or settle the
change in the plan before widening an allow-list here.
"""

from __future__ import annotations

import ast
import json
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.support.cli import call_main, cli_env
from trigger_designer.agent.tools import AgentTools

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "src" / "trigger_designer"

#: The one file that may reach the network, relative to the package.
DOWNLOADER = "core/modules/downloader.py"

#: Files that already read the computer's name for the run record. They may
#: import ``socket``, and may use nothing from it but the two functions below.
SOCKET_HOST_NAME_FILES = frozenset(
    {
        "core/audit/recorder.py",
        "core/headless/locks.py",
        "core/headless/runner.py",
    }
)
SOCKET_HOST_NAME_ATTRS = frozenset({"gethostname", "getfqdn"})

#: Modules that open a network connection, or exist only to. An import is caught
#: when its dotted name equals an entry or starts with ``entry + "."``, so
#: ``from urllib import request`` is ``urllib.request`` and
#: ``from PySide6 import QtNetwork`` is ``PySide6.QtNetwork``. ``urllib.error``,
#: ``urllib.parse`` and ``http`` on its own are plain parsing or constants.
FORBIDDEN_MODULES = frozenset(
    {
        "urllib.request",
        "urllib3",
        "http.client",
        "http.server",
        "http.cookiejar",
        "requests",
        "httpx",
        "aiohttp",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "telnetlib",
        "nntplib",
        "websocket",
        "websockets",
        "xmlrpc.client",
        "xmlrpc.server",
        "socketserver",
        "ssl",
        # Qt's network stack under each binding the code may be run with.
        "PySide6.QtNetwork",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtWebChannel",
        "qtpy.QtNetwork",
        "qtpy.QtWebEngineCore",
        "qtpy.QtWebEngineWidgets",
        "qtpy.QtWebSockets",
        "qtpy.QtWebChannel",
        "PyQt6.QtNetwork",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebSockets",
        "PyQt6.QtWebChannel",
    }
)
#: The entries that name a module inside a package, for attribute chains.
_PACKAGE_ENTRIES = tuple(sorted(e for e in FORBIDDEN_MODULES if "." in e))

#: Names that open or resolve a connection. Caught wherever they appear, as a
#: call, as a value passed on, or as an import.
CONNECTION_NAMES = frozenset(
    {
        "urlopen",
        "create_connection",
        "open_connection",
        "start_server",
        "getaddrinfo",
        "gethostbyname",
        "gethostbyaddr",
    }
)

#: What the runtime check replaces: (owner, attribute, the name a recorder reports).
CONNECTION_FUNCTIONS = (
    (socket.socket, "connect", "socket.socket.connect"),
    (socket.socket, "connect_ex", "socket.socket.connect_ex"),
    (socket.socket, "sendto", "socket.socket.sendto"),
    (socket, "create_connection", "socket.create_connection"),
    (socket, "getaddrinfo", "socket.getaddrinfo"),
    (socket, "gethostbyname", "socket.gethostbyname"),
    (socket, "gethostbyaddr", "socket.gethostbyaddr"),
)


# --------------------------------------------------------------- static scan
@dataclass(frozen=True)
class Finding:
    path: str  # relative to the package, POSIX style
    line: int
    name: str  # the module, function or attribute that was found
    reason: str

    def __str__(self) -> str:
        where = f"src/trigger_designer/{self.path}:{self.line}"
        return f"{where}  {self.name}  ({self.reason})"


def package_files() -> list[Path]:
    return sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)


def _under(dotted: str, prefix: str) -> bool:
    return dotted == prefix or dotted.startswith(prefix + ".")


def _forbidden(dotted: str) -> bool:
    return any(_under(dotted, entry) for entry in FORBIDDEN_MODULES)


def _imports(tree: ast.AST):
    """Every import in the tree, at any depth, as ``(line, module, name, alias)``.

    ``name`` is None for ``import module`` and the imported name for
    ``from module import name``. Relative imports stay inside the package.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name, None, alias.asname
        elif isinstance(node, ast.ImportFrom) and not node.level:
            for alias in node.names:
                yield node.lineno, node.module or "", alias.name, alias.asname


def _imported(module: str, name: str | None) -> str:
    """The dotted name an import brings in; ``from a import b`` gives ``a.b``."""
    if name in (None, "*"):
        return module
    return f"{module}.{name}" if module else name


def _attribute_chain(node: ast.Attribute) -> str | None:
    """``a.b.c`` for an attribute chain that starts at a plain name, else None."""
    parts = [node.attr]
    value = node.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if not isinstance(value, ast.Name):
        return None
    parts.append(value.id)
    return ".".join(reversed(parts))


def _through_package(chain: str | None) -> str | None:
    """The networking module that an attribute chain reaches, if any."""
    if chain is None:
        return None
    return next((e for e in _PACKAGE_ENTRIES if _under(chain, e)), None)


def _dynamic_import(call: ast.Call) -> str | None:
    """The module named by ``__import__("m")`` or ``importlib.import_module("m")``."""
    func = call.func
    named = (
        isinstance(func, ast.Name) and func.id in ("__import__", "import_module")
    ) or (
        isinstance(func, ast.Attribute)
        and func.attr == "import_module"
        and isinstance(func.value, ast.Name)
        and func.value.id == "importlib"
    )
    if not named:
        return None
    first = (
        call.args[0]
        if call.args
        else next((kw.value for kw in call.keywords if kw.arg == "name"), None)
    )
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def scan_source(source: bytes, path: str) -> list[Finding]:
    """Every network use in one file. ``path`` is relative to the package."""
    tree = ast.parse(source, filename=path)
    socket_allowed = path in SOCKET_HOST_NAME_FILES
    socket_names: set[str] = set()  # the names this file gives the socket module
    found: list[Finding] = []

    for line, module, name, alias in _imports(tree):
        dotted = _imported(module, name)
        if name in CONNECTION_NAMES:
            found.append(Finding(path, line, name, "connection function"))
        if _forbidden(dotted):
            found.append(Finding(path, line, dotted, "networking module"))
        elif _under(dotted, "socket"):
            if not socket_allowed:
                found.append(
                    Finding(path, line, dotted, "socket (only the host-name files)")
                )
            elif module != "socket" or (
                name is not None and name not in SOCKET_HOST_NAME_ATTRS
            ):
                found.append(
                    Finding(path, line, dotted, "socket beyond gethostname/getfqdn")
                )
            elif name is None:
                socket_names.add(alias or "socket")

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if (
                socket_allowed
                and isinstance(node.value, ast.Name)
                and node.value.id in socket_names
                and node.attr not in SOCKET_HOST_NAME_ATTRS
            ):
                found.append(
                    Finding(
                        path,
                        node.lineno,
                        f"{node.value.id}.{node.attr}",
                        "socket beyond gethostname/getfqdn",
                    )
                )
            if node.attr in CONNECTION_NAMES:
                found.append(
                    Finding(path, node.lineno, node.attr, "connection function")
                )
            entry = _through_package(_attribute_chain(node))
            if entry is not None:
                found.append(
                    Finding(path, node.lineno, entry, "reached through its package")
                )
        elif isinstance(node, ast.Name) and node.id in CONNECTION_NAMES:
            found.append(Finding(path, node.lineno, node.id, "connection function"))
        elif isinstance(node, ast.Call):
            target = _dynamic_import(node)
            if target is not None and (_forbidden(target) or _under(target, "socket")):
                found.append(Finding(path, node.lineno, target, "dynamic import"))

    return sorted(set(found), key=lambda f: (f.line, f.name, f.reason))


def scan_package() -> list[Finding]:
    """Every network use in the package, except the downloader's own file."""
    found: list[Finding] = []
    for path in package_files():
        relative = path.relative_to(PACKAGE).as_posix()
        if relative != DOWNLOADER:
            found.extend(scan_source(path.read_bytes(), relative))
    return sorted(found, key=lambda f: (f.path, f.line, f.name))


def _imported_names(source: bytes) -> set[str]:
    tree = ast.parse(source)
    return {_imported(module, name) for _line, module, name, _alias in _imports(tree)}


def _listing(findings: list[Finding]) -> str:
    return "\n".join(f"  {finding}" for finding in findings)


def test_the_scan_reads_the_whole_package():
    """A scan that looked in the wrong folder would find nothing and pass."""
    files = package_files()
    assert len(files) > 100, f"only {len(files)} files under {PACKAGE}"
    assert (PACKAGE / "core" / "headless" / "runner.py").is_file()


def test_no_file_outside_the_downloader_uses_the_network():
    found = scan_package()
    assert not found, f"network use outside {DOWNLOADER}:\n" + _listing(found)


def test_the_downloader_exists_and_is_the_only_urllib_request_importer():
    assert (PACKAGE / DOWNLOADER).is_file(), f"{DOWNLOADER} is missing"
    importers = sorted(
        path.relative_to(PACKAGE).as_posix()
        for path in package_files()
        if any(
            _under(name, "urllib.request")
            for name in _imported_names(path.read_bytes())
        )
    )
    assert importers == [DOWNLOADER], importers


def test_the_host_name_allow_list_is_still_needed():
    """A file that stops reading the host name should leave the allow-list."""
    for relative in sorted(SOCKET_HOST_NAME_FILES):
        path = PACKAGE / relative
        assert path.is_file(), f"allow-listed file is gone: {relative}"
        assert "socket" in _imported_names(path.read_bytes()), (
            f"{relative} no longer imports socket; remove it from "
            "SOCKET_HOST_NAME_FILES"
        )


#: Each form of network use the scanner must catch: (source, what it names).
_FORMS = [
    ("import urllib.request", "urllib.request"),
    ("from urllib import request", "urllib.request"),
    ("from urllib import request as fetch", "urllib.request"),
    ("import http.client as hc", "http.client"),
    ("from http import client", "http.client"),
    ("def fetch():\n    import ssl\n", "ssl"),
    ("from PySide6 import QtNetwork", "PySide6.QtNetwork"),
    ("from qtpy.QtNetwork import QNetworkAccessManager", "qtpy.QtNetwork"),
    ("import requests", "requests"),
    ("import socket", "socket"),
    ("from socket import socket as raw", "socket.socket"),
    ("import importlib\nimportlib.import_module('socket')", "socket"),
    ("__import__('urllib.request')", "urllib.request"),
    ("import urllib\nurllib.request.build_opener()", "urllib.request"),
    ("import asyncio\nasyncio.open_connection('host', 80)", "open_connection"),
    ("from helpers import urlopen", "urlopen"),
]

#: Ordinary code that must pass, including names that only look like the above.
_ORDINARY = [
    "import urllib.parse",
    "from urllib import error, parse",
    "from http import HTTPStatus",
    "import sslfoo",
    "import xmlrpc",
    "requests = []\nrequests.append(1)",
    "socket = object()\nsocket.get('x')",
    "import importlib\nimportlib.import_module(name)",
]


@pytest.mark.parametrize(("source", "expected"), _FORMS, ids=[e for _, e in _FORMS])
def test_the_scan_catches_each_form_of_network_use(source, expected):
    found = scan_source(source.encode(), "core/example.py")
    assert any(f.name.startswith(expected) for f in found), found


@pytest.mark.parametrize("source", _ORDINARY)
def test_the_scan_passes_ordinary_code(source):
    assert scan_source(source.encode(), "core/example.py") == []


@pytest.mark.parametrize("path", sorted(SOCKET_HOST_NAME_FILES))
def test_host_name_files_may_read_the_host_name_only(path):
    assert scan_source(b"import socket\nname = socket.gethostname()\n", path) == []
    found = scan_source(b"import socket\nsocket.socket().connect(('h', 80))\n", path)
    assert any(f.name == "socket.socket" for f in found), found


# ----------------------------------------------------------- import hygiene
_BARE = "import json, sys\nprint(json.dumps(sorted(sys.modules)))\n"
_OFFLINE_IMPORTS = (
    "import json, sys\n"
    "import trigger_designer.core.modules\n"
    "import trigger_designer.cli\n"
    "import trigger_designer.cli.app\n"
    "import trigger_designer.agent.tools\n"
    "print(json.dumps(sorted(sys.modules)))\n"
)


def _network_module(name: str) -> bool:
    return (
        _forbidden(name)
        or _under(name, "socket")
        or _under(name, "trigger_designer.core.modules.downloader")
    )


def _loaded_by(code: str, env: dict) -> set[str]:
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=240,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return set(json.loads(proc.stdout.splitlines()[-1]))


def test_importing_the_offline_packages_adds_no_network_module(tmp_path):
    env = cli_env(tmp_path)
    before = _loaded_by(_BARE, env)
    after = _loaded_by(_OFFLINE_IMPORTS, env)
    added = sorted(name for name in after - before if _network_module(name))
    assert not added, "importing the offline packages loaded: " + ", ".join(added)


# ------------------------------------------------------------------ runtime
@pytest.fixture()
def refused_network(monkeypatch) -> list[str]:
    """Every connection function raises, and each call is recorded before it does.

    A caller that catches the exception still leaves its name in the list, so a
    test that uses this fixture checks the list at the end, not only for a raise.
    """
    refused: list[str] = []

    def refusing(name: str):
        def _refuse(*_args, **_kwargs):
            refused.append(name)
            raise AssertionError("network used")

        return _refuse

    for owner, attr, name in CONNECTION_FUNCTIONS:
        monkeypatch.setattr(owner, attr, refusing(name))
    return refused


def _example_manifest():
    """A valid module, described in the test. Nothing is read from disk or network."""
    from trigger_designer.core.modules import parse_manifest

    return parse_manifest(
        {
            "id": "example-module",
            "name": "Example module",
            "version": "1.0.0",
            "description": "A module described inside the test.",
            "license": "MIT",
            "files": [
                {
                    "name": "model.bin",
                    "url": "https://downloads.example.org/example-module/model.bin",
                    "size_bytes": 4,
                    "sha256": (
                        "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
                    ),
                }
            ],
        }
    )


def test_offline_paths_run_with_every_connection_refused(
    refused_network, tmp_path, monkeypatch
):
    from trigger_designer.core.modules import (
        ModuleStore,
        consent_summary,
        load_catalogue,
    )

    monkeypatch.delenv("TRIGGER_DESIGNER_MODULE_CATALOGUE", raising=False)
    load_catalogue()
    assert not ModuleStore(tmp_path).installed()
    consent_summary(_example_manifest())

    listed = call_main(
        ["modules", "list", "--json"],
        env={
            "TRIGGER_DESIGNER_DATA_DIR": str(tmp_path / "data"),
            "TRIGGER_DESIGNER_STATE_DIR": str(tmp_path / "state"),
        },
    )
    assert listed.code == 0, listed.stderr
    json.loads(listed.stdout)

    tools = AgentTools(workspaces=[str(tmp_path)])
    assert tools.list_ops()["ops"]
    assert tools.explain_error("TD-MOD-007")["code"] == "TD-MOD-007"

    assert refused_network == [], f"network used by: {refused_network}"
