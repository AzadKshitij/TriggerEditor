"""Live evaluation and generated code must produce the same frame."""

from __future__ import annotations

import polars as pl
import pytest

from tests.support.input_fixtures import (
    duckdb_db,
    json_files,
    monthly_csvs,
    multi_sheet_xlsx,
    parquet_files,
    sqlite_db,
)
from trigger_designer.core.inputs import InputReadError
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow


def _node(window, path, file_type: str, **extra):
    node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    content = node.content
    content.filePath = str(path)
    content.file_type = file_type
    for key, value in extra.items():
        setattr(content, key, value)
    node.markDirty(True)
    return node


def _case(name: str, root):
    if name == "folder_csv":
        return monthly_csvs(root), "csv", {"output_filename_as_field": True}
    if name == "parquet":
        return parquet_files(root), "parquet", {}
    if name == "ndjson":
        _array, ndjson = json_files(root)
        return ndjson, "ndjson", {}
    if name == "json":
        array, _ndjson = json_files(root)
        return array, "json", {}
    if name == "excel_all":
        return (
            multi_sheet_xlsx(root),
            "excel",
            {"sheet_mode": "all", "add_sheet_name_column": True},
        )
    if name == "sqlite":
        return sqlite_db(root), "sqlite", {"db_mode": "table", "db_table": "sales"}
    if name == "duckdb":
        return (
            duckdb_db(root),
            "duckdb",
            {
                "db_mode": "query",
                "db_query": (
                    "SELECT region, SUM(amount) AS total FROM sales "
                    "GROUP BY region ORDER BY region"
                ),
            },
        )
    raise AssertionError(name)


@pytest.mark.parametrize(
    "name",
    ["folder_csv", "parquet", "ndjson", "json", "excel_all", "sqlite", "duckdb"],
)
def test_builder_code_executes_and_matches_live(tmp_path, name: str) -> None:
    window = TriggerSubWindow()
    path, file_type, extra = _case(name, tmp_path)
    node = _node(window, path, file_type, **extra)
    result = node.eval()
    assert result is not None
    assert not node.isInvalid(), node.grNode.toolTip()
    live = node.content.data.collect()

    code = node.get_code()
    namespace: dict = {}
    exec(code, {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    generated = namespace[node.content.variable_name].collect()
    assert generated.equals(live)
    window.close()


def test_builder_code_defines_variable_on_failure(tmp_path) -> None:
    window = TriggerSubWindow()
    missing = tmp_path / "missing"
    node = _node(window, missing, "csv", file_name_column_name="Src")
    namespace: dict = {}
    with pytest.raises(InputReadError):
        exec(node.get_code(), {"pl": pl}, namespace)  # noqa: S102
    assert node.content.variable_name in namespace
    assert namespace[node.content.variable_name].height == 0
    window.close()


def test_builder_code_is_idempotent_and_pure(tmp_path) -> None:
    window = TriggerSubWindow()
    path, file_type, extra = _case("parquet", tmp_path)
    node = _node(window, path, file_type, **extra)
    first_file = (path / "p1.parquet").stat().st_mtime_ns
    code_one = node.get_code()
    code_two = node.get_code()
    assert code_one == code_two
    assert (path / "p1.parquet").stat().st_mtime_ns == first_file
    window.close()


def test_builder_code_quotes_hostile_values(tmp_path) -> None:
    directory = tmp_path / "o'brien"
    directory.mkdir()
    pl.DataFrame({"id": [1]}).write_parquet(directory / "a.parquet")
    window = TriggerSubWindow()
    node = _node(
        window,
        directory,
        "parquet",
        output_filename_as_field=True,
        file_name_column_name="a'b\\c",
    )
    result = node.eval()
    assert result is not None
    namespace: dict = {}
    exec(node.get_code(), {"pl": pl}, namespace)  # noqa: S102
    generated = namespace[node.content.variable_name].collect()
    assert generated.equals(node.content.data.collect())
    assert "a'b\\c" in generated.columns
    window.close()


def test_unconfigured_node_defines_empty_frame() -> None:
    window = TriggerSubWindow()
    node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    namespace: dict = {}
    exec(node.get_code(), {"pl": pl}, namespace)  # noqa: S102
    assert node.content.variable_name in namespace
    assert namespace[node.content.variable_name].height == 0
    window.close()


def test_builder_code_uses_repr_not_interpolation(tmp_path) -> None:
    window = TriggerSubWindow()
    node = _node(window, tmp_path / "x.csv", "csv", encoding="utf8-lossy")
    code = node.get_code()
    assert "build_source" in code
    assert "_spec_" in code
    assert "encoding': 'utf8-lossy'" in code
    window.close()
