"""Translator rules against real engine failures."""

from __future__ import annotations

import duckdb
import fastexcel
import openpyxl
import polars as pl
import pytest
from polars.exceptions import PanicException

from trigger_designer.core.errors import (
    ErrorContext,
    NodeError,
    translate_exception,
)
from trigger_designer.core.errors.builders import make_error
from trigger_designer.core.ExecutionCheck.executor import ExecutionTimeoutError


def _ctx(**kwargs) -> ErrorContext:
    defaults = {
        "node_id": 1,
        "node_label": "Test node",
        "input_columns": ("Amount", "k", "s"),
        "input_dtypes": {"Amount": "String", "k": "Int64", "s": "String"},
        "referenced_columns": ("Amount",),
    }
    defaults.update(kwargs)
    return ErrorContext(**defaults)


def _translate(call, ctx=None) -> NodeError:
    try:
        call()
    except BaseException as exc:  # noqa: BLE001
        return translate_exception(exc, ctx=ctx or _ctx())
    raise AssertionError("trigger did not raise")


def _frame() -> pl.LazyFrame:
    return pl.LazyFrame(
        {
            "Amount": ["10", "20", "1,2O0.50", "30"],
            "k": [1, 2, 3, 4],
            "s": ["a", "b", "c", "d"],
        }
    )


def test_column_not_found_has_suggestion() -> None:
    error = _translate(lambda: _frame().select("Amnt").collect())
    assert error.code == "TD-SCH-001"
    assert error.columns == ("Amnt",)
    assert error.did_you_mean == ("Amount",)


def test_column_not_found_without_list_uses_context() -> None:
    error = _translate(
        lambda: _frame().drop("Amnt").collect(),
        _ctx(input_columns=("Amount", "k", "s")),
    )
    assert error.code == "TD-SCH-001"
    assert error.did_you_mean == ("Amount",)


def test_cast_reports_column_target_and_value() -> None:
    error = _translate(
        lambda: _frame().select(pl.col("Amount").cast(pl.Int64)).collect()
    )
    assert error.code == "TD-TYP-001"
    assert error.columns == ("Amount",)
    assert error.params["target"] == "i64"
    assert error.params["value"] == "1,2O0.50"
    assert "whole numbers" in error.title


def test_integer_overflow_is_typ_005() -> None:
    error = _translate(
        lambda: (
            pl.DataFrame({"a": [300]})
            .lazy()
            .select(pl.col("a").cast(pl.Int8))
            .collect()
        )
    )
    assert error.code == "TD-TYP-005"
    assert "does not fit" in error.title


def test_sum_on_text_is_typ_003() -> None:
    error = _translate(
        lambda: _frame().group_by("k").agg(pl.col("Amount").sum()).collect()
    )
    assert error.code == "TD-TYP-003"
    assert error.columns == ("Amount",)
    assert "summed" in error.title


def test_compare_text_number_is_typ_004() -> None:
    error = _translate(lambda: _frame().filter(pl.col("Amount") > 5).collect())
    assert error.code == "TD-TYP-004"


def test_filter_predicate_is_typ_007() -> None:
    error = _translate(lambda: _frame().filter(pl.col("k")).collect())
    assert error.code == "TD-TYP-007"
    assert "Int64" in error.title


def test_unnest_wrong_type_is_typ_006() -> None:
    error = _translate(lambda: pl.DataFrame({"a": [1]}).lazy().unnest("a").collect())
    assert error.code == "TD-TYP-006"
    assert error.columns == ("a",)


def test_join_key_mismatch_is_typ_002() -> None:
    left = pl.LazyFrame({"k": [1], "x": [1]})
    right = pl.LazyFrame({"k": ["1"], "y": [1]})
    error = _translate(lambda: left.join(right, on="k").collect())
    assert error.code == "TD-TYP-002"
    assert error.columns == ("k", "k")


def test_concat_schema_mismatch_is_sch_004() -> None:
    left = pl.LazyFrame({"k": [1], "x": [1]})
    right = pl.LazyFrame({"k": ["1"], "y": [1]})
    error = _translate(lambda: pl.concat([left, right]).collect())
    assert error.code == "TD-SCH-004"
    assert "k" in error.detail


def test_shape_error_is_sch_005() -> None:
    error = _translate(lambda: pl.DataFrame({"a": [1, 2], "b": [1]}))
    assert error.code == "TD-SCH-005"


def test_duplicate_projection_is_sch_002() -> None:
    error = _translate(
        lambda: (
            _frame().select(pl.col("k").alias("z"), pl.col("s").alias("z")).collect()
        )
    )
    assert error.code == "TD-SCH-002"
    assert "z" in error.columns


def test_regex_error_is_exp_004() -> None:
    error = _translate(
        lambda: (
            pl.DataFrame({"s": ["a"]})
            .lazy()
            .select(pl.col("s").str.replace("(", "x"))
            .collect()
        )
    )
    assert error.code == "TD-EXP-004"
    assert "unclosed group" in error.detail


def test_missing_file_is_in_001_and_attributes_source(tmp_path) -> None:
    missing = tmp_path / "nope.csv"
    ctx = _ctx(input_paths={str(missing): 7})
    error = _translate(lambda: pl.scan_csv(missing).collect(), ctx)
    assert error.code == "TD-IN-001"
    assert error.culprit_node_id == 7
    assert error.path


def test_empty_csv_is_in_005(tmp_path) -> None:
    path = tmp_path / "empty.csv"
    path.write_bytes(b"")
    error = _translate(
        lambda: pl.scan_csv(path, infer_schema=False).collect(),
        _ctx(input_paths={str(path): 3}),
    )
    assert error.code == "TD-IN-005"


def test_bad_utf8_is_in_004(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    path.write_bytes(b"a,b\n1,\xff\xfe\n")
    error = _translate(
        lambda: pl.scan_csv(path, infer_schema=False).collect(),
        _ctx(input_paths={str(path): 3}),
    )
    assert error.code == "TD-IN-004"


def test_ragged_csv_is_in_007(tmp_path) -> None:
    path = tmp_path / "ragged.csv"
    path.write_text("a,b\n1,2,3\n", encoding="utf-8")
    error = _translate(lambda: pl.scan_csv(path, infer_schema=False).collect())
    assert error.code == "TD-IN-007"


def test_corrupt_workbook_is_in_006(tmp_path) -> None:
    path = tmp_path / "broken.xlsx"
    path.write_text("not a workbook", encoding="utf-8")
    error = _translate(
        lambda: fastexcel.read_excel(path),
        _ctx(input_paths={str(path): 2}),
    )
    assert error.code == "TD-IN-006"


def test_missing_sheet_is_in_003_with_suggestion(tmp_path) -> None:
    path = tmp_path / "book.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.title = "Data"
    workbook.active.append(["a"])
    workbook.save(path)
    reader = fastexcel.read_excel(path)
    error = _translate(
        lambda: reader.load_sheet("Dat"),
        _ctx(input_paths={str(path): 2}),
    )
    assert error.code == "TD-IN-003"
    assert error.did_you_mean == ("Data",)


def _duck(tmp_path):
    connection = duckdb.connect()
    connection.execute("create table t(k integer, Amount varchar, s varchar)")
    connection.execute("insert into t values (1,'10','a'),(2,'1,2O0.50','b')")
    return connection


def test_duckdb_binder_column_not_found(tmp_path) -> None:
    connection = _duck(tmp_path)
    error = _translate(lambda: connection.execute("select Amnt+1 from t").fetchall())
    assert error.code == "TD-SCH-001"
    assert error.params.get("engine_duckdb") == "1"


def test_duckdb_parser_error_is_exp_001(tmp_path) -> None:
    connection = _duck(tmp_path)
    error = _translate(lambda: connection.execute("select *, k + AS z from t"))
    assert error.code == "TD-EXP-001"


def test_duckdb_unknown_function_is_exp_002(tmp_path) -> None:
    connection = _duck(tmp_path)
    error = _translate(lambda: connection.execute("select lenght(s) from t"))
    assert error.code == "TD-EXP-002"
    assert error.params.get("suggestion") == "length"


def test_duckdb_conversion_is_typ_001(tmp_path) -> None:
    connection = _duck(tmp_path)
    error = _translate(
        lambda: connection.execute("select cast(Amount as integer) from t").fetchall()
    )
    assert error.code == "TD-TYP-001"
    assert error.params.get("value") == "1,2O0.50"
    assert error.params.get("engine_duckdb") == "1"


def test_duckdb_compare_is_typ_004(tmp_path) -> None:
    connection = _duck(tmp_path)
    error = _translate(
        lambda: connection.execute("select * from t where Amount > 5").fetchall()
    )
    assert error.code == "TD-TYP-004"


def test_name_error_maps_variable_owner() -> None:
    ctx = _ctx(
        variable_owners={"var_formula_555": 555}, node_labels={555: "Formula 'x'"}
    )
    error = _translate(lambda: exec("x = var_formula_555"), ctx)  # noqa: S102
    assert error.code == "TD-RUN-006"
    assert error.culprit_node_id == 555


def test_timeout_and_memory() -> None:
    timeout = ExecutionTimeoutError("Code execution timed out after 2 seconds")
    error = translate_exception(timeout, ctx=_ctx())
    assert error.code == "TD-RUN-001"
    assert error.params["seconds"] == "2"

    memory = MemoryError()
    error = translate_exception(memory, ctx=_ctx())
    assert error.code == "TD-RUN-002"


def test_panic_and_unknown_are_distinct() -> None:
    panic = translate_exception(PanicException("boom"), ctx=_ctx())
    assert panic.code == "TD-SYS-998"

    class Weird(Exception):
        pass

    unknown = translate_exception(Weird("what"), ctx=_ctx())
    assert unknown.code == "TD-SYS-999"


def test_legacy_value_error_is_sys_001() -> None:
    error = translate_exception(ValueError("Both inputs must be connected"), ctx=_ctx())
    assert error.code == "TD-SYS-001"
    assert error.title == "Both inputs must be connected"


def test_out_codes() -> None:
    error = translate_exception(
        ModuleNotFoundError("No module named 'xlsxwriter'"), ctx=_ctx()
    )
    assert error.code == "TD-OUT-003"
    error = translate_exception(
        ValueError("File Output: no incoming data - connect an input"), ctx=_ctx()
    )
    assert error.code == "TD-OUT-006"


def test_rule0_known_code_passthrough() -> None:
    class Coded(Exception):
        code = "TD-AUDIT-001"
        columns = ("Key",)

    error = translate_exception(Coded("Choose the key column."), ctx=_ctx())
    assert error.code == "TD-AUDIT-001"
    assert error.title == "Choose the key column."
    assert error.columns == ("Key",)
    assert error.hint


def test_rule0_text_code_and_unknown_code() -> None:
    error = translate_exception(
        ValueError("[TD-SHAPE-003] Column(s) not found: a"), ctx=_ctx()
    )
    assert error.code == "TD-SHAPE-003"
    assert error.title == "Column(s) not found: a"

    unknown = translate_exception(Exception("[TD-ZZZ-999] something"), ctx=_ctx())
    assert unknown.code == "TD-ZZZ-999"
    assert unknown.title == "something"
    assert unknown.hint == ""


def test_plan_one_input_error_passthrough_and_attribution(tmp_path) -> None:
    from trigger_designer.core.inputs import InputReadError

    path = str(tmp_path / "nope.csv")
    error = translate_exception(
        InputReadError(
            "file_not_found",
            f"Cannot find the input file '{path}'.",
            path=path,
        ),
        ctx=_ctx(input_paths={path: 11}),
    )
    assert error.code == "TD-IN-001"
    assert error.culprit_node_id == 11
    assert "nope.csv" in error.title

    parse = translate_exception(
        InputReadError("parse", "I could not read the data in this file"),
        ctx=_ctx(),
    )
    assert parse.code == "TD-IN-010"
    assert parse.title == "I could not read the data in this file"
    assert parse.hint


def test_rule0_ignores_non_td_codes() -> None:
    class Coded(Exception):
        code = 404

    error = translate_exception(Coded("plain failure"), ctx=_ctx())
    assert error.code == "TD-SYS-999"


def test_make_error_knock_on() -> None:
    error = make_error(
        "TD-RUN-003", _ctx(node_label="Output"), culprit_label="Aggregate"
    )
    assert error.knock_on
    assert "Aggregate" in error.title


@pytest.mark.parametrize(
    "exc",
    [
        None,
        "",
        "plain string",
        Exception(),
        KeyboardInterrupt(),
        SystemExit(3),
        ExceptionGroup("many", [ValueError("a")]),
    ],
)
def test_translate_never_raises(exc) -> None:
    error = translate_exception(exc, ctx=_ctx())
    assert isinstance(error, NodeError)
    assert error.code.startswith("TD-")
    assert error.title
    assert len(error.title) <= 90
    assert len(error.technical) <= 100_020


def test_translate_broken_str_never_raises() -> None:
    class Broken(Exception):
        def __str__(self):
            raise RuntimeError("no text")

    error = translate_exception(Broken(), ctx=_ctx())
    assert isinstance(error, NodeError)
    assert error.title
