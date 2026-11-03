"""Shared fixtures for the Data Profile tests (plan 05)."""

from __future__ import annotations

import polars as pl

NAN = float("nan")
INF = float("inf")

#: Ten rows that each exercise one rule of the profile engine. Values are the
#: hand-computed ones in docs/plan/05-data-profile-node.md section 6.1.
FX = pl.DataFrame(
    {
        "id": [f"{i:03d}" for i in range(1, 11)],
        "amount": [
            "10",
            "20.5",
            "30",
            " 40 ",
            "",
            None,
            "1,5",
            "abc",
            "123-",
            "7",
        ],
        "qty": [1, 2, 2, 3, None, 0, -1, 5, 5, 5],
        "price": [1.5, NAN, INF, None, 2.5, -0.5, 0.0, 1.5, 1.5, 3.0],
        "when": [
            "2024-01-31",
            "2024-02-29",
            "2023-12-01",
            "2024-03-15",
            "2024-04-01",
            "2024-05-05",
            "2024-06-30",
            "2024-07-04",
            "2024-08-08",
            "2024-09-09",
        ],
        "flag": ["Y", "N", "Y", "Y", "N", "Y", "N", "Y", "Y", "N"],
        "const": ["x"] * 10,
        "nada": pl.Series([None] * 10, dtype=pl.String),
        "locale": [
            "1,5",
            "2,25",
            "3,0",
            "10,75",
            "0,5",
            "100,5",
            "7,1",
            "8,2",
            "9,9",
            "4,4",
        ],
        "sap": ["100-", "200", "300-", "50", "75-", "10", "20", "30", "40", "5"],
    }
)

#: A small hand-checked CSV a user could plausibly export from a ledger.
MESSY_CSV = (
    "id,amount,qty,posted,flag,note\n"
    '001,"1,234.50",1,2024-01-31,Y,ok\n'
    '002, 20.5 ,2,2024-02-29,N,""\n'
    "003,30-,2,2024-03-15,Y,ok\n"
    "004,abc,,2024-04-01,Y,ok\n"
    "005,7,0,31/12/2024,N, ok\n"
    "006,,5,not a date,Y,ok\n"
)
