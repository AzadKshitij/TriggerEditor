"""trigger.spec hides the core packages from PyInstaller's static analysis."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "trigger.spec"
BEGIN = "# --- core hidden imports begin"
END = "# --- core hidden imports end"


def _run_block() -> list[str]:
    text = SPEC.read_text(encoding="utf-8")
    ast.parse(text)  # the whole spec is valid Python
    block = text.split(BEGIN, 1)[1].split(END, 1)[0]
    ns = {"Path": Path, "collect_submodules": lambda name: [f"{name}.stub"]}
    import os

    old = os.getcwd()
    os.chdir(ROOT)
    try:
        exec(compile(block, "trigger.spec", "exec"), ns)  # noqa: S102
    finally:
        os.chdir(old)
    return ns["core_hiddenimports"]


def test_spec_parses_and_wires_core_hiddenimports() -> None:
    text = SPEC.read_text(encoding="utf-8")
    assert "+ core_hiddenimports" in text
    assert "collect_submodules" in text


def test_core_packages_are_listed() -> None:
    mods = _run_block()
    for expected in (
        "trigger_designer.core.shaping.common",
        "trigger_designer.core.shaping.formula",
        "trigger_designer.core.errors",
        "trigger_designer.core.audit.benford",
        "trigger_designer.core.excel",
        "xlsxwriter",
        "trigger_designer.cli",
    ):
        assert expected in mods, expected


def test_listed_core_modules_exist() -> None:
    for mod in _run_block():
        if mod.startswith("trigger_designer.core"):
            rel = Path("src", *mod.split("."))
            assert rel.with_suffix(".py").exists() or (rel / "__init__.py").exists(), (
                mod
            )


def test_every_module_generated_code_imports_is_in_the_spec() -> None:
    """Generated code is exec'd, so PyInstaller never sees its imports."""
    import importlib.util

    from trigger_designer.core.headless.code_policy import GENERATED_IMPORTS

    listed = set(_run_block())
    literal = SPEC.read_text(encoding="utf-8")
    missing = []
    for module in GENERATED_IMPORTS:
        if not module.startswith("trigger_designer."):
            # third-party: must be a hidden import; the stdlib needs nothing
            spec = importlib.util.find_spec(module)
            stdlib = spec is not None and "site-packages" not in (spec.origin or "")
            if not stdlib and f'"{module}"' not in literal:
                missing.append(module)
        elif module not in listed and not any(
            item.startswith(f"{module}.") for item in listed
        ):
            missing.append(module)
    assert not missing, f"missing from trigger.spec hidden imports: {missing}"
