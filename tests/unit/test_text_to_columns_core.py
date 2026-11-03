"""Text to Columns core: hand-computed expectations, errors, live == code."""

from __future__ import annotations

import ast
from pathlib import Path

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.core.shaping import text_to_columns as ttc
from trigger_designer.core.shaping.common import ERROR_CODES, ShapingError
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

TT = pl.DataFrame(
    {
        "id": [1, 2, 3, 4, 5],
        "acct": ["1000-200-30-4", "7", " a - b ", None, ""],
    }
)


def _cols(settings: dict, frame: pl.DataFrame = TT) -> pl.DataFrame:
    return ttc.apply_text_to_columns(frame.lazy(), settings).collect()


def _code(settings: dict, frame: pl.DataFrame = TT) -> str:
    with pytest.raises(ShapingError) as error:
        _cols(settings, frame)
    return error.value.code


def test_columns_mode_last_piece_takes_remainder() -> None:
    out = _cols({"column": "acct", "pattern": "-", "max_splits": 2})
    assert out.columns == ["id", "acct", "acct_1", "acct_2", "acct_3"]
    assert out.select("acct_1", "acct_2", "acct_3").rows() == [
        ("1000", "200", "30-4"),
        ("7", None, None),
        ("a", "b", None),
        (None, None, None),
        ("", None, None),
    ]
    assert out.schema["acct_1"] == pl.String


def test_two_pieces_with_names_and_no_original() -> None:
    out = _cols(
        {
            "column": "acct",
            "pattern": "-",
            "max_splits": 1,
            "names": "Main, Rest",
            "keep_original": False,
        }
    )
    assert out.columns == ["id", "Main", "Rest"]
    assert out.row(0) == (1, "1000", "200-30-4")


def test_trim_false_keeps_spaces_and_trim_covers_remainder() -> None:
    raw = _cols({"column": "acct", "pattern": "-", "max_splits": 2, "trim": False})
    assert raw["acct_1"][2] == " a "
    remainder = _cols(
        {"column": "acct", "pattern": "-", "max_splits": 1},
        pl.DataFrame({"acct": ["a- b - c "]}),
    )
    assert remainder.row(0) == ("a- b - c ", "a", "b - c")


def test_names_longer_than_columns_ignored_and_clashes_renamed() -> None:
    out = _cols(
        {"column": "acct", "pattern": "-", "max_splits": 1, "names": "x, y, z, w"}
    )
    assert out.columns == ["id", "acct", "x", "y"]
    clash = _cols(
        {"column": "acct", "pattern": "-", "max_splits": 2, "names": "id, id"},
    )
    assert clash.columns == ["id", "acct", "id_2", "id_3", "acct_3"]
    # the dropped source name is still reserved
    dropped = _cols(
        {
            "column": "acct",
            "pattern": "-",
            "max_splits": 1,
            "names": "acct",
            "keep_original": False,
        },
    )
    assert dropped.columns == ["id", "acct_2", "acct_2_2"]


def test_rows_mode_unlimited_with_piece_number() -> None:
    out = _cols(
        {
            "column": "acct",
            "pattern": "-",
            "max_splits": 0,
            "output": "rows",
            "row_index_column": "n",
            "keep_original": False,
        }
    )
    assert out.columns == ["id", "acct", "n"]
    assert out.rows() == [
        (1, "1000", 1),
        (1, "200", 2),
        (1, "30", 3),
        (1, "4", 4),
        (2, "7", 1),
        (3, "a", 1),
        (3, "b", 2),
        (4, None, 1),
        (5, "", 1),
    ]
    assert out.schema["n"] == pl.Int64


def test_rows_mode_keeps_original_and_limits_pieces() -> None:
    out = _cols({"column": "acct", "pattern": "-", "max_splits": 2, "output": "rows"})
    assert out.columns == ["id", "acct", "acct_original"]
    assert out.filter(pl.col("id") == 1)["acct"].to_list() == ["1000", "200", "30-4"]
    assert set(out.filter(pl.col("id") == 1)["acct_original"]) == {"1000-200-30-4"}
    assert out.height == 8


def test_rows_mode_skip_empty_keeps_one_null_row_for_all_empty_cell() -> None:
    frame = pl.DataFrame({"k": [1, 2, 3], "s": ["a,,b", ",,", "c"]})
    out = _cols(
        {
            "column": "s",
            "pattern": ",",
            "max_splits": 0,
            "output": "rows",
            "skip_empty": True,
            "keep_original": False,
        },
        frame,
    )
    assert out.rows() == [(1, "a"), (1, "b"), (2, None), (3, "c")]
    without = _cols(
        {
            "column": "s",
            "pattern": ",",
            "max_splits": 0,
            "output": "rows",
            "keep_original": False,
        },
        frame,
    )
    assert without.height == 3 + 3 + 1


def test_regex_mode_and_escape_delimiter() -> None:
    frame = pl.DataFrame({"s": ["a, b;c"]})
    out = _cols(
        {
            "column": "s",
            "split_mode": "regex",
            "pattern": r"\s*[,;]\s*",
            "max_splits": 2,
        },
        frame,
    )
    assert out.row(0)[1:] == ("a", "b", "c")
    tab = _cols(
        {"column": "s", "pattern": "\\t", "max_splits": 1},
        pl.DataFrame({"s": ["x\ty"]}),
    )
    assert tab.row(0)[1:] == ("x", "y")
    backslash = _cols(
        {"column": "s", "pattern": "\\\\", "max_splits": 1},
        pl.DataFrame({"s": ["x\\y"]}),
    )
    assert backslash.row(0)[1:] == ("x", "y")


def test_delimiter_is_literal_not_regex() -> None:
    out = _cols(
        {"column": "s", "pattern": ".", "max_splits": 1},
        pl.DataFrame({"s": ["a.b", "axb"]}),
    )
    assert out.rows() == [("a.b", "a", "b"), ("axb", "axb", None)]


def test_zero_rows_stay_typed() -> None:
    empty = TT.clear()
    out = _cols({"column": "acct", "pattern": "-", "max_splits": 2}, empty)
    assert out.height == 0 and out.columns[-1] == "acct_3"
    rows = _cols(
        {"column": "acct", "pattern": "-", "max_splits": 0, "output": "rows"}, empty
    )
    assert rows.height == 0 and rows.schema["acct"] == pl.String


@pytest.mark.parametrize(
    ("settings", "code"),
    [
        ({"column": "", "pattern": "-"}, "TD-SHAPE-001"),
        ({"column": "acct", "pattern": ""}, "TD-SHAPE-001"),
        ({"column": "nope", "pattern": "-"}, "TD-SHAPE-003"),
        ({"column": "id", "pattern": "-"}, "TD-SHAPE-044"),
        ({"column": "acct", "pattern": "-", "max_splits": 0}, "TD-SHAPE-004"),
        ({"column": "acct", "pattern": "-", "max_splits": 50}, "TD-SHAPE-004"),
        (
            {"column": "acct", "pattern": "-", "max_splits": 50, "output": "rows"},
            "TD-SHAPE-004",
        ),
        ({"column": "acct", "pattern": "-", "max_splits": "x"}, "TD-SHAPE-004"),
        ({"column": "acct", "pattern": "-", "split_mode": "glob"}, "TD-SHAPE-004"),
        ({"column": "acct", "pattern": "-", "output": "cells"}, "TD-SHAPE-004"),
        ({"column": "acct", "split_mode": "regex", "pattern": "("}, "TD-SHAPE-040"),
        ({"column": "acct", "split_mode": "regex", "pattern": r"\s*"}, "TD-SHAPE-101"),
        ({"column": "acct", "split_mode": "regex", "pattern": "^"}, "TD-SHAPE-101"),
    ],
)
def test_error_codes(settings: dict, code: str) -> None:
    assert _code(settings) == code


def test_error_codes_are_registered() -> None:
    for code in (
        "TD-SHAPE-001",
        "TD-SHAPE-004",
        "TD-SHAPE-040",
        "TD-SHAPE-044",
        "TD-SHAPE-101",
    ):
        assert code in ERROR_CODES
    from trigger_designer.core.errors.catalogue import CATALOGUE

    assert "TD-SHAPE-101" in CATALOGUE


def test_run_node_validates_like_live() -> None:
    with pytest.raises(ShapingError) as error:
        ttc.run_node([TT.lazy()], {"column": "acct", "pattern": "", "max_splits": 2})
    assert error.value.code == "TD-SHAPE-001"
    out = ttc.run_node([TT.lazy()], {"column": "acct", "pattern": "-"})[0]
    assert isinstance(out, pl.LazyFrame)


def test_input_is_lazy_and_describe_chip() -> None:
    chips = ttc.describe(
        [TT.lazy()],
        {"column": "acct", "pattern": "-", "max_splits": 0, "output": "rows"},
    )
    assert chips and chips[0][0].startswith("5 rows become 9")
    assert ttc.describe([TT.lazy()], {"column": "acct", "pattern": "-"}) == []
    assert ttc.describe([TT.lazy()], {"column": "", "pattern": "-"}) == []


def test_core_has_no_qt_import() -> None:
    source = Path(ttc.__file__).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"qtpy", "PyQt5", "PyQt6", "PySide2", "PySide6"}
    assert "trigger_designer.qt" not in source


# ---- generated code agrees with live evaluation ---------------------------


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame) -> None:
        self._frame = frame
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def _node(window):
    cls = get_class_from_opcode(PreparationNodes.TEXT_TO_COLUMNS, NodeTypes.PREPARATION)
    return cls(window.scene)


@pytest.mark.parametrize(
    "settings",
    [
        {"column": "acct", "pattern": "-", "max_splits": 2},
        {
            "column": "acct",
            "pattern": "-",
            "max_splits": 0,
            "output": "rows",
            "row_index_column": "n",
        },
        # quotes and backslashes in user text never reach the code unescaped
        {
            "column": "acct",
            "pattern": "'\"\\\\",
            "max_splits": 1,
            "names": "a'b, \"c\\",
        },
        {
            "column": "acct",
            "split_mode": "regex",
            "pattern": r"[-']\s*",
            "max_splits": 3,
        },
    ],
)
def test_live_equals_generated_code(settings: dict) -> None:
    window = TriggerSubWindow()
    frame = TT.lazy()
    source = Source(window.scene, frame)
    node = _node(window)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.content.settings.update(settings)
    node.markDirty(True)
    out = node.eval()
    assert out is not None and not node.isInvalid()
    live = out[0]["data"].collect()
    namespace = {"var_src": frame}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    generated = namespace[node.content.variable_name].collect()
    assert generated.equals(live)
    assert generated.height > 0


def test_unwired_defines_every_output_variable() -> None:
    window = TriggerSubWindow()
    node = _node(window)
    namespace: dict = {}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    for variable in node.content.output_variables:
        assert variable in namespace
    assert len(node.content.output_variables) == 1


def test_bad_settings_raise_same_code_live_and_in_code() -> None:
    window = TriggerSubWindow()
    source = Source(window.scene, TT.lazy())
    node = _node(window)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.content.settings.update(
        {"column": "acct", "split_mode": "regex", "pattern": r"\s*"}
    )
    node.markDirty(True)
    assert node.eval() is None
    assert node.isInvalid()
    namespace = {"var_src": TT.lazy()}
    with pytest.raises(ShapingError) as error:
        exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    assert error.value.code == "TD-SHAPE-101"


def test_regex_remainder_keeps_original_separators() -> None:
    frame = pl.DataFrame({"s": ["200 - 30 -4", "a-b"]})
    out = _cols(
        {"column": "s", "split_mode": "regex", "pattern": r"\s*-\s*", "max_splits": 1},
        frame,
    )
    assert out.select("s_1", "s_2").rows() == [("200", "30 -4"), ("a", "b")]
    rows = _cols(
        {
            "column": "s",
            "split_mode": "regex",
            "pattern": r"\s*-\s*",
            "max_splits": 1,
            "output": "rows",
            "keep_original": False,
        },
        frame,
    )
    assert rows.rows() == [("200",), ("30 -4",), ("a",), ("b",)]
