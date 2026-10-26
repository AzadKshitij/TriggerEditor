"""Select core: ordered projection, rename, dtype conversion, inference."""

# ruff: noqa: DTZ001 - these assertions compare Polars' naive datetimes

from __future__ import annotations

from datetime import date, datetime

import polars as pl

from trigger_designer.core.shaping import select as core


def _settings(columns):
    return {"columns": columns, "auto_accept_new_columns": True}


def test_select_projects_in_table_order_and_renames() -> None:
    frame = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]}).lazy()
    out = core.run_node(
        [frame],
        _settings(
            [
                {"name": "b", "selected": True, "dtype": "String", "rename": "Bee"},
                {"name": "a", "selected": True, "dtype": "Int64", "rename": ""},
            ]
        ),
    )[0].collect()
    assert out.columns == ["Bee", "a"]
    assert out.rows() == [("x", 1), ("y", 2)]


def test_select_converts_dtype_and_dates() -> None:
    frame = pl.DataFrame({"n": ["1", "2"], "d": ["2024-01-02", "2024-01-03"]}).lazy()
    out = core.run_node(
        [frame],
        _settings(
            [
                {"name": "n", "selected": True, "dtype": "Int64", "rename": ""},
                {
                    "name": "d",
                    "selected": True,
                    "dtype": "Date",
                    "date_format": "%Y-%m-%d",
                    "rename": "",
                },
            ]
        ),
    )[0].collect()
    assert out["n"].to_list() == [1, 2]
    assert out["d"].to_list() == [date(2024, 1, 2), date(2024, 1, 3)]


def test_select_skips_missing_columns_and_keeps_all_when_none_selected() -> None:
    frame = pl.DataFrame({"a": [1], "b": ["x"]}).lazy()
    out = core.run_node(
        [frame],
        _settings(
            [
                {"name": "gone", "selected": True, "dtype": "String", "rename": ""},
                {"name": "a", "selected": True, "dtype": "Int64", "rename": ""},
            ]
        ),
    )[0].collect()
    assert out.columns == ["a"]

    out = core.run_node(
        [frame],
        _settings(
            [
                {"name": "a", "selected": False, "dtype": "Int64", "rename": ""},
                {"name": "b", "selected": False, "dtype": "String", "rename": ""},
            ]
        ),
    )[0].collect()
    assert out.columns == ["a", "b"]


def test_infer_dtype() -> None:
    assert core.infer_dtype(["1", "2"]) == ("Int64", None)
    assert core.infer_dtype(["1.5", "2"]) == ("Float64", None)
    assert core.infer_dtype(["true", "false"]) == ("Boolean", None)
    assert core.infer_dtype(["2024-01-02"]) == ("Date", "%Y-%m-%d")
    assert core.infer_dtype(["hello"]) == ("String", None)


def test_mixed_date_formats_to_date_and_datetime() -> None:
    frame = pl.DataFrame(
        {
            "raw_date": [
                "2024-04-12",
                "12-04-2024",
                "31/01/2024",
                "2024/04/12 10:30:00",
                "12 Apr 2024",
            ]
        }
    ).lazy()
    dates = (
        core.run_node(
            [frame],
            _settings(
                [{"name": "raw_date", "selected": True, "dtype": "Date", "rename": ""}]
            ),
        )[0]
        .collect()["raw_date"]
        .to_list()
    )
    assert dates == [
        date(2024, 4, 12),
        date(2024, 4, 12),
        date(2024, 1, 31),
        date(2024, 4, 12),
        date(2024, 4, 12),
    ]

    frame = pl.DataFrame(
        {
            "raw_datetime": [
                "2024-04-12 10:30:00",
                "12-04-2024 10:30:00",
                "31/01/2024 01:02:03",
                "2024/04/12T10:30:00",
                "12 Apr 2024",
            ]
        }
    ).lazy()
    values = (
        core.run_node(
            [frame],
            _settings(
                [
                    {
                        "name": "raw_datetime",
                        "selected": True,
                        "dtype": "Datetime",
                        "rename": "",
                    }
                ]
            ),
        )[0]
        .collect()["raw_datetime"]
        .to_list()
    )
    assert values == [
        datetime(2024, 4, 12, 10, 30),
        datetime(2024, 4, 12, 10, 30),
        datetime(2024, 1, 31, 1, 2, 3),
        datetime(2024, 4, 12, 10, 30),
        datetime(2024, 4, 12),
    ]


def test_dtype_matches_and_known_date_format() -> None:
    assert core.dtype_matches(pl.Datetime, "Datetime")
    assert core.dtype_matches(pl.Int64, "Int64")
    assert not core.dtype_matches(pl.Date, "Datetime")
    assert not core.dtype_matches(None, "Date")
    assert not core.dtype_matches(pl.String, "Bogus")

    frame = pl.DataFrame({"d": ["31/01/2024"]}).lazy()
    out = core.run_node(
        [frame],
        _settings(
            [
                {
                    "name": "d",
                    "selected": True,
                    "dtype": "Date",
                    "date_format": "%d/%m/%Y",
                    "rename": "",
                }
            ]
        ),
    )[0].collect()
    assert out["d"].to_list() == [date(2024, 1, 31)]
