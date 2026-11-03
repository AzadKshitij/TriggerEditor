"""Package a Windows build into a versioned zip and refresh SHA256SUMS.txt.

Two layouts are supported:

* ``folder`` - the PyInstaller onedir build (``dist/TriggerEditor/``). It starts
  faster than the single-file build because nothing is extracted at launch.
* ``portable`` - the PyInstaller onefile build (``dist/TriggerEditor.exe``).

Both zips carry the LICENSE. ``dist/SHA256SUMS.txt`` lists every zip in
``dist/`` so the file stays correct whichever layouts were built.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def version() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from trigger_designer.core.constants import VERSION

    return VERSION


def build_zip(layout: str) -> Path:
    tag = version()
    if layout == "folder":
        source = DIST / "TriggerEditor"
        if not (source / "TriggerEditor.exe").is_file():
            raise SystemExit(
                f"missing {source / 'TriggerEditor.exe'}; run the onedir build first"
            )
        archive = DIST / f"TriggerDesigner-{tag}-windows-folder.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    zf.write(path, Path("TriggerEditor") / path.relative_to(source))
            zf.write(ROOT / "LICENSE", "TriggerEditor/LICENSE")
    elif layout == "portable":
        source = DIST / "TriggerEditor.exe"
        if not source.is_file():
            raise SystemExit(f"missing {source}; run the portable build first")
        archive = DIST / f"TriggerDesigner-{tag}-windows-portable.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(source, source.name)
            zf.write(ROOT / "LICENSE", "LICENSE")
    else:
        raise SystemExit(f"unknown layout: {layout}")
    return archive


def write_sums() -> Path:
    lines = []
    for archive in sorted(DIST.glob("*.zip")):
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
    parser.add_argument("--layout", choices=("folder", "portable"), required=True)
    args = parser.parse_args()
    archive = build_zip(args.layout)
    sums = write_sums()
    print(f"packaged {archive.relative_to(ROOT)}")
    print(f"wrote {sums.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
