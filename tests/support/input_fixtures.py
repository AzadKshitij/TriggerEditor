"""Deterministic input fixtures.

Every function writes byte-identical files on each call, so goldens and
reports stay stable across machines.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import duckdb
import openpyxl
import polars as pl


def write_text(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode(encoding))
    return path


def monthly_csvs(root: Path) -> Path:
    """Folder ``monthly`` with 3 CSVs plus noise that must be excluded."""
    directory = root / "monthly"
    write_text(
        directory / "sales_2024-01.csv", "id,region,amount\n1,N,10.50\n2,S,20.00\n"
    )
    write_text(directory / "sales_2024-02.csv", "id,region,amount\n3,N,30.25\n")
    write_text(
        directory / "sales_2024-03.csv",
        "id,region,amount,channel\n4,E,40.00,web\n5,W,5.75,store\n",
    )
    write_text(directory / "~$sales_2024-04.csv", "garbage-lock-file")
    write_text(directory / "notes.txt", "not data\n")
    write_text(directory / ".hidden.csv", "id\n999\n")
    return directory


def natural_order_csvs(root: Path) -> Path:
    directory = root / "natural"
    for number in (10, 2, 1):
        write_text(directory / f"part_{number}.csv", f"v\n{number}\n")
    return directory


def nested_csvs(root: Path) -> Path:
    directory = root / "nested"
    write_text(directory / "a" / "data.csv", "k\nA\n")
    write_text(directory / "b" / "data.csv", "k\nB\n")
    write_text(directory / "top.csv", "k\nT\n")
    return directory


def parquet_files(root: Path) -> Path:
    directory = root / "pq"
    directory.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"id": [1, 2], "amount": [10, 20]}).write_parquet(
        directory / "p1.parquet"
    )
    pl.DataFrame({"id": [3], "amount": [30.5], "tag": ["x"]}).write_parquet(
        directory / "p2.parquet"
    )
    return directory


def json_files(root: Path) -> tuple[Path, Path]:
    directory = root / "json"
    array = write_text(
        directory / "records.json",
        json.dumps(
            [
                {"a": 1, "b": {"c": 2}, "t": [1, 2]},
                {"a": 3, "b": None, "t": None},
            ]
        ),
    )
    ndjson = write_text(
        directory / "lines.ndjson", '{"a":1,"s":"x"}\n{"a":2,"s":"y","extra":true}\n'
    )
    return array, ndjson


def sqlite_db(root: Path) -> Path:
    path = root / "db" / "t.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("create table sales(id integer, region text, amount real)")
    connection.executemany(
        "insert into sales values(?,?,?)",
        [(1, "N", 10.5), (2, "S", 20.0), (3, "N", 30.25)],
    )
    connection.execute("create view big as select * from sales where amount > 15")
    connection.commit()
    connection.close()
    return path


def duckdb_db(root: Path) -> Path:
    path = root / "db" / "t.duckdb"
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(path))
    connection.execute("create table sales(id integer, region varchar, amount double)")
    connection.execute(
        "insert into sales values (1,'N',10.5),(2,'S',20.0),(3,'N',30.25)"
    )
    connection.close()
    return path


def multi_sheet_xlsx(root: Path, name: str = "book.xlsx") -> Path:
    path = root / "xl" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    jan = workbook.active
    jan.title = "Jan"
    jan.append(["id", "amt"])
    jan.append([1, 2.5])
    feb = workbook.create_sheet("Feb")
    feb.append(["id", "amt", "note"])
    feb.append([2, "n/a", "x"])
    workbook.save(path)
    return path


def many_csvs(root: Path, files: int, rows: int) -> Path:
    directory = root / f"many_{files}x{rows}"
    for file_index in range(files):
        body = "id,grp,val\n" + "".join(
            f"{file_index * rows + row},{row % 7},{(row * 13) % 101}\n"
            for row in range(rows)
        )
        write_text(directory / f"f_{file_index:04d}.csv", body)
    return directory
