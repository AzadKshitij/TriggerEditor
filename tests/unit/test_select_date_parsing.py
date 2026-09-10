#!/usr/bin/env python3

import datetime as dt
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl

from trigger_designer.qt.widgets.nodes.Preparation.select import SelectContent


def test_select_content_parses_mixed_date_formats_to_date() -> None:
    content = SelectContent.__new__(SelectContent)

    df = pl.DataFrame(
        {
            "raw_date": [
                "2024-04-12",
                "12-04-2024",
                "31/01/2024",
                "2024/04/12 10:30:00",
                "12 Apr 2024",
            ]
        }
    )

    result = df.with_columns(content._build_dtype_conversion_expr("raw_date", "Date"))

    assert result["raw_date"].to_list() == [
        dt.date(2024, 4, 12),
        dt.date(2024, 4, 12),
        dt.date(2024, 1, 31),
        dt.date(2024, 4, 12),
        dt.date(2024, 4, 12),
    ]


def test_select_content_parses_mixed_date_formats_to_datetime() -> None:
    content = SelectContent.__new__(SelectContent)

    df = pl.DataFrame(
        {
            "raw_datetime": [
                "2024-04-12 10:30:00",
                "12-04-2024 10:30:00",
                "31/01/2024 01:02:03",
                "2024/04/12T10:30:00",
                "12 Apr 2024",
            ]
        }
    )

    result = df.with_columns(
        content._build_dtype_conversion_expr("raw_datetime", "Datetime")
    )

    assert result["raw_datetime"].to_list() == [
        dt.datetime(2024, 4, 12, 10, 30, 0),
        dt.datetime(2024, 4, 12, 10, 30, 0),
        dt.datetime(2024, 1, 31, 1, 2, 3),
        dt.datetime(2024, 4, 12, 10, 30, 0),
        dt.datetime(2024, 4, 12, 0, 0, 0),
    ]