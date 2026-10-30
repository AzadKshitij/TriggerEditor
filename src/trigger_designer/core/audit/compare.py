"""Compare two run records and re-check inputs (docs/plan/02-audit-trail.md 3.9).

Pure functions over raw record dicts (``RunStore.load_dict``); Qt-free.
Timestamps, durations and run ids are never compared, so two runs of the same
workflow on the same data are ``identical``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from trigger_designer.core.audit.fingerprint import fingerprint_file

_ENVIRONMENT_FIELDS = (
    "app_version",
    "polars_version",
    "python_version",
    "duckdb_version",
)
_UNSET = object()


@dataclass(frozen=True)
class DiffItem:
    kind: (
        str  # input | parameter | row_count | status | output | environment | node_set
    )
    node_id: int | None
    node_title: str | None
    field: str  # e.g. "sha256", "settings.delimiter", "rows_out.var_x_5"
    old: object
    new: object


@dataclass(frozen=True)
class RunDiff:
    old_run_id: str
    new_run_id: str
    items: list[DiffItem]

    @property
    def identical(self) -> bool:
        return not self.items


def _by_key(items: Any, key_fn) -> dict:
    out: dict = {}
    for item in items or []:
        if isinstance(item, dict):
            out.setdefault(key_fn(item), item)
    return out


def _settings_diff(old: Any, new: Any, prefix: str):
    """Yield ``(dotted_field, old, new)`` for each changed leaf."""
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new), key=str):
            yield from _settings_diff(
                old.get(key, _UNSET), new.get(key, _UNSET), f"{prefix}.{key}"
            )
        return
    if old is _UNSET and isinstance(new, dict):
        for key in sorted(new, key=str):
            yield from _settings_diff(_UNSET, new[key], f"{prefix}.{key}")
        return
    if new is _UNSET and isinstance(old, dict):
        for key in sorted(old, key=str):
            yield from _settings_diff(old[key], _UNSET, f"{prefix}.{key}")
        return
    if old != new:
        yield prefix, None if old is _UNSET else old, None if new is _UNSET else new


def compare_runs(old: dict, new: dict) -> RunDiff:
    """Differences that matter to a reviewer, in a fixed order."""
    items: list[DiffItem] = []

    for name in _ENVIRONMENT_FIELDS:
        if old.get(name) != new.get(name):
            items.append(
                DiffItem("environment", None, None, name, old.get(name), new.get(name))
            )

    def input_key(item: dict):
        return (item.get("node_id"), item.get("path"), item.get("sheet"))

    old_in = _by_key(old.get("inputs"), input_key)
    new_in = _by_key(new.get("inputs"), input_key)
    for key in sorted(set(old_in) | set(new_in), key=repr):
        before, after = old_in.get(key), new_in.get(key)
        node_id, path, _sheet = key
        if before is None or after is None:
            items.append(
                DiffItem(
                    "input",
                    node_id,
                    None,
                    "presence",
                    path if before else None,
                    path if after else None,
                )
            )
            continue
        old_sha, new_sha = before.get("sha256"), after.get("sha256")
        if old_sha and new_sha:
            if old_sha != new_sha:
                items.append(
                    DiffItem("input", node_id, None, "sha256", old_sha, new_sha)
                )
        elif before.get("size_bytes") != after.get("size_bytes"):
            items.append(
                DiffItem(
                    "input",
                    node_id,
                    None,
                    "size_bytes",
                    before.get("size_bytes"),
                    after.get("size_bytes"),
                )
            )

    old_nodes = _by_key(old.get("nodes"), lambda n: n.get("node_id"))
    new_nodes = _by_key(new.get("nodes"), lambda n: n.get("node_id"))
    for node_id in sorted(set(old_nodes) ^ set(new_nodes), key=repr):
        node = old_nodes.get(node_id) or new_nodes.get(node_id)
        items.append(
            DiffItem(
                "node_set",
                node_id,
                node.get("title"),
                "presence",
                "present" if node_id in old_nodes else None,
                "present" if node_id in new_nodes else None,
            )
        )

    for node_id in sorted(set(old_nodes) & set(new_nodes), key=repr):
        before, after = old_nodes[node_id], new_nodes[node_id]
        title = after.get("title") or before.get("title")
        for field, o, n in _settings_diff(
            before.get("settings") or {}, after.get("settings") or {}, "settings"
        ):
            items.append(DiffItem("parameter", node_id, title, field, o, n))
        if before.get("seed") != after.get("seed"):
            items.append(
                DiffItem(
                    "parameter",
                    node_id,
                    title,
                    "seed",
                    before.get("seed"),
                    after.get("seed"),
                )
            )
        if before.get("status") != after.get("status"):
            items.append(
                DiffItem(
                    "status",
                    node_id,
                    title,
                    "status",
                    before.get("status"),
                    after.get("status"),
                )
            )
        old_rows, new_rows = before.get("rows_out") or {}, after.get("rows_out") or {}
        for variable in sorted(set(old_rows) | set(new_rows)):
            o, n = old_rows.get(variable), new_rows.get(variable)
            if o != n:
                items.append(
                    DiffItem("row_count", node_id, title, f"rows_out.{variable}", o, n)
                )

    def output_key(item: dict):
        return (item.get("node_id"), item.get("path"))

    old_out = _by_key(old.get("outputs"), output_key)
    new_out = _by_key(new.get("outputs"), output_key)
    titles = {nid: n.get("title") for nid, n in {**old_nodes, **new_nodes}.items()}
    for key in sorted(set(old_out) | set(new_out), key=repr):
        before, after = old_out.get(key), new_out.get(key)
        node_id, path = key
        title = titles.get(node_id)
        if before is None or after is None:
            items.append(
                DiffItem(
                    "output",
                    node_id,
                    title,
                    "presence",
                    path if before else None,
                    path if after else None,
                )
            )
            continue
        for field in ("sha256", "row_count"):
            if before.get(field) != after.get(field):
                items.append(
                    DiffItem(
                        "output",
                        node_id,
                        title,
                        field,
                        before.get(field),
                        after.get(field),
                    )
                )

    return RunDiff(str(old.get("run_id")), str(new.get("run_id")), items)


@dataclass(frozen=True)
class InputCheck:
    path: str
    sheet: str | None
    state: str  # "unchanged" | "modified" | "missing" | "skipped" | "error"
    recorded_sha256: str | None
    current_sha256: str | None


def check_inputs(
    record: dict,
    *,
    cancel: threading.Event | None = None,
    use_cache: bool = False,
) -> list[InputCheck]:
    """Re-hash every recorded input now and compare with the record."""
    results: list[InputCheck] = []
    for item in record.get("inputs") or []:
        if not isinstance(item, dict) or not item.get("path"):
            continue
        path, sheet = str(item["path"]), item.get("sheet")
        recorded = item.get("sha256")

        def done(
            state: str,
            current: str | None = None,
            *,
            path=path,
            sheet=sheet,
            recorded=recorded,
        ):
            results.append(InputCheck(path, sheet, state, recorded, current))

        if cancel is not None and cancel.is_set():
            done("skipped")
            continue
        current = fingerprint_file(
            path,
            "input",
            item.get("node_id"),
            sheet,
            cancel=cancel,
            hash_enabled=True,
            hash_max_bytes=1 << 62,
            use_cache=use_cache,
        )
        if current.sha256_status == "missing":
            done("missing")
        elif current.sha256_status == "error":
            done("error")
        elif current.sha256_status == "cancelled":
            done("skipped")
        elif not recorded:
            done("skipped", current.sha256)
        elif current.sha256 == recorded:
            done("unchanged", current.sha256)
        else:
            done("modified", current.sha256)
    return results
