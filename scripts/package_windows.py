"""Package a Windows build into a versioned zip and refresh SHA256SUMS.txt.

Two layouts:

* ``folder`` - the PyInstaller onedir build (``dist/TriggerEditor/``): the
  editor, ``tds.exe`` (command line and AI-tool server) and one shared
  ``_internal`` runtime. Zipped as ``-windows-portable.zip`` with one top
  folder, ``TriggerDesigner\\``.
* ``single-file`` - the onefile build (``dist/TriggerEditor.exe``): editor only,
  no command line and no AI-tool server. Zipped as
  ``-windows-editor-single-file.zip``.

``dist/SHA256SUMS.txt`` lists every zip and setup program in ``dist/``.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
TOP = "TriggerDesigner"


def version() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from trigger_designer.core.constants import VERSION

    return VERSION


def build_zip(layout: str) -> Path:
    tag = version()
    if layout == "folder":
        source = DIST / "TriggerEditor"
        for exe in ("TriggerEditor.exe", "tds.exe"):
            if not (source / exe).is_file():
                raise SystemExit(f"missing {source / exe}; run the folder build first")
        archive = DIST / f"TriggerDesigner-{tag}-windows-portable.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    zf.write(path, Path(TOP) / path.relative_to(source))
            zf.write(ROOT / "LICENSE", f"{TOP}/LICENSE")
            zf.write(ROOT / "installer" / "README.txt", f"{TOP}/README.txt")
            zf.write(
                ROOT / "docs" / "guide" / "mcp-server.md",
                f"{TOP}/docs/mcp-server.md",
            )
    elif layout == "single-file":
        source = DIST / "TriggerEditor.exe"
        if not source.is_file():
            raise SystemExit(f"missing {source}; run the single-file build first")
        archive = DIST / f"TriggerDesigner-{tag}-windows-editor-single-file.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(source, source.name)
            zf.write(ROOT / "LICENSE", "LICENSE")
    else:
        raise SystemExit(f"unknown layout: {layout}")
    return archive


def write_sums() -> Path:
    lines = []
    for archive in sorted([*DIST.glob("*.zip"), *DIST.glob("*-setup.exe")]):
        digest = hashlib.sha256()
        with archive.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        lines.append(f"{digest.hexdigest()}  {archive.name}")
    target = DIST / "SHA256SUMS.txt"
    target.write_text("\n".join(lines) + "\n", encoding="ascii")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--layout", choices=("folder", "single-file", "sums"), required=True
    )
    args = parser.parse_args()
    if args.layout != "sums":
        print(f"packaged {build_zip(args.layout).relative_to(ROOT)}")
    print(f"wrote {write_sums().relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
