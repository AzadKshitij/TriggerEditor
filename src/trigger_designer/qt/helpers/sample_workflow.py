"""The sample workflow shipped with the app.

The welcome dialog offers a runnable example on first install: without it a
fresh install opens the app and a welcome dialog that lists no files (issue
#31). The sample is the AE Winter Watch workflow over twelve NHS England
monthly returns - curated, and validated in the release smoke check.

The bundle holds the ``.tds`` and its ``data/`` folder under
``resources/samples/``; the workflow's paths are absolute, and the bundle is
read-only inside an installed copy. So opening the sample first materializes
it into the user's app-data directory and rewrites the stored paths there:

* ``File Input`` keeps ``filePathRel`` ("data"), which resolves against the
  materialized ``.tds``;
* ``File Output`` has no relative-path storage, so its absolute ``filePath``
  is rewritten to the materialized ``output/`` folder;
* ``output/`` is created - the writer does not create missing folders.

The user's copy is theirs: later runs and edits keep working, and the bundle
is never written.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import orjson
from loguru import logger

from trigger_designer.qt.preferences import app_data_dir, bundle_base

#: Sample id. Matches the folder name under ``resources/samples/``.
SAMPLE_NAME = "ae_winter_watch"

#: Display metadata the welcome dialog shows.
SAMPLE_TITLE = "A&E Winter Watch (sample workflow)"
SAMPLE_DESCRIPTION = (
    "Twelve NHS England monthly returns. Run it, then select a Graph node and "
    "click Show graph - or browse the nodes to see how it was built."
)

TDS_NAME = f"{SAMPLE_NAME}.tds"
_PATH_MARKER = "Example_3_AE_Winter_Watch"


def bundled_sample_dir() -> Path:
    return bundle_base() / "resources" / "samples" / SAMPLE_NAME


def user_sample_dir() -> Path:
    return app_data_dir() / "samples" / SAMPLE_NAME


def materialize_sample() -> Path:
    """Copy the bundled sample into the user's data dir and return its ``.tds``.

    Re-run on every call: files already present are kept (the user's copy is
    not overwritten), but the ``.tds`` paths are rewritten every time so the
    workflow still resolves if the app-data directory moved.
    """
    source = bundled_sample_dir()
    if not (source / TDS_NAME).is_file():
        raise FileNotFoundError(
            f"the bundled sample is missing at {source} - the install is incomplete"
        )
    target = user_sample_dir()
    _copy_missing(source / TDS_NAME, target / TDS_NAME)
    _copy_tree_missing(source / "data", target / "data")
    (target / "output").mkdir(parents=True, exist_ok=True)
    _rewrite_paths(target / TDS_NAME, target)
    return target / TDS_NAME


def _copy_missing(source: Path, target: Path) -> None:
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _copy_tree_missing(source: Path, target: Path) -> None:
    for item in sorted(source.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(source)
        _copy_missing(item, target / relative)


def _rewrite_paths(tds: Path, target_dir: Path) -> None:
    """Point every stored path that names the sample at ``target_dir``."""
    root = str(target_dir).replace("\\", "/")
    data = orjson.loads(tds.read_bytes())
    if not isinstance(data, dict):
        return
    changed = False
    for node in data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        content = node.get("content")
        if not isinstance(content, dict):
            continue
        changed |= _rewrite_mapping(content, root)
        settings = content.get("settings")
        if isinstance(settings, dict):
            changed |= _rewrite_mapping(settings, root)
    if changed:
        tds.write_bytes(orjson.dumps(data))
        logger.debug("sample workflow: paths rewritten to {}", root)


def _rewrite_mapping(mapping: dict, root: str) -> bool:
    changed = False
    for key, value in list(mapping.items()):
        if not isinstance(value, str) or _PATH_MARKER not in value:
            continue
        suffix = value.split(_PATH_MARKER, 1)[1].replace("\\", "/").lstrip("/")
        mapping[key] = f"{root}/{suffix}"
        changed = True
    return changed


def sample_workflow_path() -> Path:
    """Where the welcome dialog should point the user at."""
    try:
        return materialize_sample()
    except (OSError, orjson.JSONDecodeError) as exc:
        logger.exception("could not materialize the sample workflow")
        raise RuntimeError(
            "the sample workflow could not be unpacked - see the log for details"
        ) from exc
