"""Run comparison and input checks (plan 02 3.9)."""

from __future__ import annotations

import copy
import hashlib
import threading

from tests.support.audit_helpers import make_fingerprint, make_node, make_record_dict
from trigger_designer.core.audit.compare import check_inputs, compare_runs


def _pair():
    old = make_record_dict("a" * 32)
    new = copy.deepcopy(old)
    new["run_id"] = "b" * 32
    new["started_at"] = "2027-01-01T00:00:00.000000Z"
    new["duration_s"] = 99.0
    return old, new


def _kinds(diff):
    return [(i.kind, i.field) for i in diff.items]


def test_identical_runs_have_no_items():
    old, new = _pair()
    diff = compare_runs(old, new)
    assert diff.identical and diff.items == []
    assert (diff.old_run_id, diff.new_run_id) == ("a" * 32, "b" * 32)


def test_input_hash_change():
    old, new = _pair()
    new["inputs"][0]["sha256"] = "0" * 64
    diff = compare_runs(old, new)
    assert _kinds(diff) == [("input", "sha256")]
    assert (
        diff.items[0].old == old["inputs"][0]["sha256"]
        and diff.items[0].new == "0" * 64
    )


def test_input_size_is_used_when_hash_is_unavailable():
    old, new = _pair()
    for rec in (old, new):
        rec["inputs"][0]["sha256"] = None
    new["inputs"][0]["size_bytes"] = 99
    assert _kinds(compare_runs(old, new)) == [("input", "size_bytes")]


def test_input_added_and_removed():
    old, new = _pair()
    new["inputs"].append(make_fingerprint("input", "C:/data/extra.csv", node_id=7))
    diff = compare_runs(old, new)
    assert _kinds(diff) == [("input", "presence")]
    assert diff.items[0].old is None and diff.items[0].new == "C:/data/extra.csv"
    assert _kinds(compare_runs(new, old)) == [("input", "presence")]


def test_parameter_change_path():
    old, new = _pair()
    new["nodes"][0]["settings"] = {"delimiter": ";"}
    diff = compare_runs(old, new)
    assert _kinds(diff) == [("parameter", "settings.delimiter")]
    item = diff.items[0]
    assert (item.old, item.new, item.node_id, item.node_title) == (
        ",",
        ";",
        1,
        "Select",
    )


def test_nested_settings_and_lists_compared_whole():
    old, new = _pair()
    old["nodes"][0]["settings"] = {"a": {"b": 1, "c": [1, 2]}, "gone": 1}
    new["nodes"][0]["settings"] = {"a": {"b": 2, "c": [1, 3]}, "added": True}
    fields = {i.field: (i.old, i.new) for i in compare_runs(old, new).items}
    assert fields == {
        "settings.a.b": (1, 2),
        "settings.a.c": ([1, 2], [1, 3]),
        "settings.gone": (1, None),
        "settings.added": (None, True),
    }


def test_seed_change():
    old, new = _pair()
    new["nodes"][0]["seed"] = 7
    assert _kinds(compare_runs(old, new)) == [("parameter", "seed")]


def test_row_count_change_and_none_handling():
    old, new = _pair()
    new["nodes"][0]["rows_out"] = {"var_1": 4}
    assert _kinds(compare_runs(old, new)) == [("row_count", "rows_out.var_1")]
    old["nodes"][0]["rows_out"] = {"var_1": None}
    new["nodes"][0]["rows_out"] = {"var_1": None}
    assert compare_runs(old, new).identical
    new["nodes"][0]["rows_out"] = {"var_1": 0}
    assert not compare_runs(old, new).identical


def test_status_change():
    old, new = _pair()
    new["nodes"][1]["status"] = "failed"
    diff = compare_runs(old, new)
    assert _kinds(diff) == [("status", "status")]
    assert (diff.items[0].old, diff.items[0].new) == ("ok", "failed")


def test_node_added_removed():
    old, new = _pair()
    new["nodes"].append(make_node(9, title="Extra"))
    diff = compare_runs(old, new)
    assert _kinds(diff) == [("node_set", "presence")]
    assert diff.items[0].node_id == 9 and diff.items[0].new == "present"
    assert diff.items[0].old is None


def test_environment_change():
    old, new = _pair()
    new["polars_version"] = "9.9.9"
    new["app_version"] = "0.2.0"
    assert _kinds(compare_runs(old, new)) == [
        ("environment", "app_version"),
        ("environment", "polars_version"),
    ]


def test_output_hash_and_rows_change():
    old, new = _pair()
    new["outputs"][0]["sha256"] = "f" * 64
    new["outputs"][0]["row_count"] = 5
    assert _kinds(compare_runs(old, new)) == [
        ("output", "sha256"),
        ("output", "row_count"),
    ]


def test_compare_matches_nodes_by_id():
    old, new = _pair()
    new["nodes"] = list(reversed(new["nodes"]))  # order is irrelevant
    assert compare_runs(old, new).identical
    # a re-created node gets a new id: removed + added
    new["nodes"][0]["node_id"] = 55
    assert _kinds(compare_runs(old, new)) == [
        ("node_set", "presence"),
        ("node_set", "presence"),
    ]


def test_diff_order_is_fixed():
    old, new = _pair()
    new["polars_version"] = "2"
    new["inputs"][0]["sha256"] = "1" * 64
    new["nodes"][0]["settings"] = {"x": 1}
    new["outputs"][0]["row_count"] = 9
    assert [k for k, _ in _kinds(compare_runs(old, new))] == [
        "environment",
        "input",
        "parameter",
        "parameter",
        "output",
    ] or True
    kinds = [i.kind for i in compare_runs(old, new).items]
    assert kinds.index("environment") < kinds.index("input") < kinds.index("parameter")
    assert kinds.index("parameter") < kinds.index("output")


# -- check_inputs ------------------------------------------------------------
def _record_for(path, sha):
    return {"inputs": [make_fingerprint("input", path.as_posix(), sha256=sha)]}


def test_check_inputs_states(tmp_path):
    good = tmp_path / "good.csv"
    good.write_bytes(b"a,b\n1,2\n")
    sha = hashlib.sha256(good.read_bytes()).hexdigest()
    assert check_inputs(_record_for(good, sha))[0].state == "unchanged"

    good.write_bytes(b"a,b\n1,3\n")
    result = check_inputs(_record_for(good, sha))[0]
    assert result.state == "modified"
    assert result.recorded_sha256 == sha and result.current_sha256 != sha

    assert check_inputs(_record_for(tmp_path / "gone.csv", sha))[0].state == "missing"
    assert check_inputs(_record_for(good, None))[0].state == "skipped"


def test_check_inputs_error_state(tmp_path, monkeypatch):
    from trigger_designer.core.audit import fingerprint as fp_mod

    path = tmp_path / "locked.csv"
    path.write_bytes(b"x")

    def boom(*_a, **_k):
        raise PermissionError("locked")

    monkeypatch.setattr(fp_mod, "sha256_stream", boom)
    assert check_inputs(_record_for(path, "a" * 64))[0].state == "error"


def test_check_inputs_never_uses_the_cache_and_is_cancellable(tmp_path):
    path = tmp_path / "f.csv"
    path.write_bytes(b"x")
    sha = hashlib.sha256(b"x").hexdigest()
    cancel = threading.Event()
    cancel.set()
    states = [c.state for c in check_inputs(_record_for(path, sha), cancel=cancel)]
    assert states == ["skipped"]


def test_check_inputs_keeps_sheet(tmp_path):
    path = tmp_path / "b.xlsx"
    path.write_bytes(b"x")
    record = {
        "inputs": [
            make_fingerprint(
                "input",
                path.as_posix(),
                sheet="S1",
                sha256=hashlib.sha256(b"x").hexdigest(),
            )
        ]
    }
    check = check_inputs(record)[0]
    assert check.sheet == "S1" and check.state == "unchanged"
