"""Qt-free workflow reading and static validation (plan 08 S1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.workflow_file import (
    file_nodes,
    op_counts,
    parse_workflow_bytes,
    read_workflow,
    static_validate,
)


def _node(nid, op, *, ins=(), outs=(), content=None, title=None):
    return {
        "id": nid,
        "op": op,
        "title": title or op,
        "inputs": [{"id": i} for i in ins],
        "outputs": [{"id": o} for o in outs],
        "content": content or {},
    }


def _wf(nodes, edges, schema=2):
    return {
        "workflow_metadata": {"schema_version": schema, "app_version": "0.1.0"},
        "nodes": nodes,
        "edges": [
            {"id": 900 + i, "start": s, "end": e} for i, (s, e) in enumerate(edges)
        ],
    }


def _doc(data, path="wf.tds"):
    return parse_workflow_bytes(json.dumps(data).encode(), path)


def _codes(findings, level=None):
    return [f.td_code for f in findings if level is None or f.level == level]


def _simple():
    return _wf(
        [
            _node(1, "input.file_input", outs=[11], content={"filePath": "in.csv"}),
            _node(
                2,
                "input.file_output",
                ins=[21],
                content={"settings": {"filePath": "out.csv"}},
            ),
        ],
        [(11, 21)],
    )


def test_reads_utf8(tmp_path):
    path = tmp_path / "a.tds"
    path.write_text(json.dumps(_simple(), ensure_ascii=False), encoding="utf-8")
    doc = read_workflow(str(path))
    assert doc.encoding == "utf-8"
    assert doc.schema_version == 2
    assert len(doc.sha256) == 64


def test_reads_utf8_bom(tmp_path):
    path = tmp_path / "a.tds"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(_simple()).encode())
    assert read_workflow(str(path)).encoding == "utf-8"


def test_reads_cp1252_bytes():
    data = _simple()
    data["nodes"][0]["title"] = "Caf\xe9"
    raw = json.dumps(data, ensure_ascii=False).encode("cp1252")
    doc = parse_workflow_bytes(raw, "wf.tds")
    assert doc.encoding in ("cp1252", "windows-1252") or doc.encoding.startswith("cp")
    assert doc.nodes[0]["title"] == "Caf\xe9"


def test_not_json_is_td_cli_001(tmp_path):
    path = tmp_path / "bad.tds"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(CliError) as exc:
        read_workflow(str(path))
    assert exc.value.td_code == "TD-CLI-001"
    assert exc.value.code == ExitCode.INVALID


def test_missing_file_and_wrong_shape_are_td_cli_001(tmp_path):
    with pytest.raises(CliError) as exc:
        read_workflow(str(tmp_path / "nope.tds"))
    assert exc.value.td_code == "TD-CLI-001"
    with pytest.raises(CliError):
        parse_workflow_bytes(b'{"nodes": []}', "x")
    with pytest.raises(CliError):
        parse_workflow_bytes(b"[1, 2]", "x")


def test_newer_schema_td_cli_002():
    findings = static_validate(_doc(_wf(_simple()["nodes"], [], schema=3)))
    assert "TD-CLI-002" in _codes(findings, "error")


def test_unknown_op_td_cli_003():
    data = _simple()
    data["nodes"].append(_node(3, "preparation.teleport"))
    findings = static_validate(_doc(data))
    assert "TD-CLI-003" in _codes(findings, "error")


def test_cycle_td_cli_004():
    data = _wf(
        [
            _node(1, "preparation.sort", ins=[10], outs=[11]),
            _node(2, "preparation.sort", ins=[20], outs=[21]),
        ],
        [(11, 20), (21, 10)],
    )
    assert "TD-CLI-004" in _codes(static_validate(_doc(data)), "error")


def test_clean_workflow_has_no_findings():
    assert static_validate(_doc(_simple())) == []


def test_v1_node_without_op_is_warning_only():
    data = _simple()
    data["nodes"].append(
        {"id": 3, "title": "Mystery", "inputs": [], "outputs": [], "content": {}}
    )
    findings = static_validate(_doc(data))
    assert [f.level for f in findings if f.td_code == "TD-CLI-003"] == ["warning"]


def test_v1_opcode_resolves_to_op():
    data = {
        "nodes": [
            {
                "id": 5,
                "op_type": "INPUT",
                "op_code": 4,
                "title": "File Input",
                "content": {"filePath": "x.csv"},
            },
            {
                "id": 6,
                "op_type": "INPUT",
                "op_code": 5,
                "title": "File Output",
                "content": {"filePath": "y.csv"},
            },
        ],
        "edges": [],
    }
    doc = _doc(data)
    assert [(f.kind, f.raw_path) for f in file_nodes(doc)] == [
        ("input", "x.csv"),
        ("output", "y.csv"),
    ]
    assert "TD-CLI-003" not in _codes(static_validate(doc))


def test_big_ids_exact():
    data = _simple()
    data["nodes"][0]["id"] = 2176004824160
    doc = parse_workflow_bytes(json.dumps(data).encode(), "x")
    assert doc.nodes[0]["id"] == 2176004824160
    assert file_nodes(doc)[0].node_id == 2176004824160


def test_no_file_output_warns_td_cli_018():
    data = _wf([_node(1, "input.file_input", outs=[11])], [])
    findings = static_validate(_doc(data))
    assert ("warning", "TD-CLI-018") in [(f.level, f.td_code) for f in findings]


def test_file_nodes_read_settings_or_top_level_path():
    doc = _doc(_simple())
    nodes = file_nodes(doc)
    assert [(n.kind, n.raw_path, n.node_id) for n in nodes] == [
        ("input", "in.csv", 1),
        ("output", "out.csv", 2),
    ]


def test_op_counts():
    assert op_counts(_doc(_simple())) == {"input.file_input": 1, "input.file_output": 1}


def _file_touching_ops():
    from trigger_designer.core.headless.op_catalog import OPS

    return [
        (info, key, kind)
        for info in OPS.values()
        for kind, keys in (
            ("input", getattr(info, "input_keys", ())),
            ("output", info.output_keys),
        )
        for key in keys
    ]


def test_every_file_touching_op_in_the_catalogue_is_listed():
    """C3: approve/info/paths must show every path the run reads or writes."""
    from trigger_designer.cli.commands.approve import review_block
    from trigger_designer.core.headless.op_catalog import OPS

    if "input.workpaper_output" not in OPS:
        pytest.skip("input.workpaper_output is not registered in this build")
    ops = _file_touching_ops()
    assert {i.op for i, _, _ in ops} >= {
        "input.file_input",
        "input.file_output",
        "input.workpaper_output",
    }
    nodes = [
        _node(
            100 + n,
            info.op,
            content={"settings": {key: f"C:/data/{info.op}_{key}.xlsx"}},
        )
        for n, (info, key, _) in enumerate(ops)
    ]
    doc = _doc(_wf(nodes, []))
    listed = {(f.kind, f.raw_path) for f in file_nodes(doc)}
    assert listed == {
        (kind, f"C:/data/{info.op}_{key}.xlsx") for info, key, kind in ops
    }
    _text, reads, writes = review_block(doc)
    for info, key, kind in ops:
        want = str(Path(f"C:/data/{info.op}_{key}.xlsx"))
        assert want in (reads if kind == "input" else writes)


@pytest.fixture
def subst_drive(tmp_path):
    """A ``subst`` drive pointing at ``tmp_path`` (Windows only)."""
    import os
    import string
    import subprocess

    if os.name != "nt":
        pytest.skip("subst drives are a Windows feature")
    free = [
        c for c in reversed(string.ascii_uppercase) if not os.path.exists(c + ":\\")
    ]
    if not free:
        pytest.skip("no free drive letter")
    letter = free[0]
    if subprocess.run(["subst", f"{letter}:", str(tmp_path)], check=False).returncode:
        pytest.skip("subst is not available")
    try:
        yield f"{letter}:\\"
    finally:
        subprocess.run(["subst", f"{letter}:", "/D"], check=False)


@pytest.mark.parametrize("saved_via", ["subst", "real"])
def test_paths_relativize_works_on_a_subst_drive(tmp_path, subst_drive, saved_via):
    """C4: base_dir must not resolve the drive away from the saved spelling."""
    import json as _json

    from tests.support.cli import call_main, synthetic_workflow

    (tmp_path / "data").mkdir()
    root = subst_drive if saved_via == "subst" else str(tmp_path) + "\\"
    data = synthetic_workflow(input_path=root + "data/in.csv")
    wf = tmp_path / "wf.tds"
    wf.write_text(_json.dumps(data), encoding="utf-8")
    out = call_main(
        ["paths", subst_drive + "wf.tds", "--relativize", "--format", "json"]
    )
    assert out.code == 0, out.stderr
    changes = out.json()["relativize"]
    assert [c["to"] for c in changes] == ["data/in.csv"]
