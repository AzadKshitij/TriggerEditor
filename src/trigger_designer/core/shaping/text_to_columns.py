"""Text to Columns: split one text column into columns or into rows."""

from __future__ import annotations

import re

import polars as pl

from trigger_designer.core.shaping.common import (
    LIVE_SAMPLE_ROWS,
    Frame,
    ShapingError,
    as_lazy,
    require_columns,
    schema_of,
    unique_name,
)

#: Regex mode turns the matches that split into this character, then splits on
#: it (``str.splitn`` has no regex form). A cell that already contains it splits
#: there too; that is documented and accepted.
SENTINEL = "␟"
MAX_COLUMNS = 50
MAX_SPLITS = MAX_COLUMNS - 1
POS = "__pos"
REST = "rest_piece"

_ESCAPES = {"\\t": "\t", "\\n": "\n", "\\r": "\r", "\\\\": "\\"}

DEFAULTS = {
    "column": "",
    "split_mode": "delimiter",
    "pattern": ",",
    "output": "columns",
    "max_splits": 2,
    "names": "",
    "trim": True,
    "keep_original": True,
    "skip_empty": False,
    "row_index_column": "",
}


def normalize(settings: dict) -> dict:
    """Validate the settings and return a clean copy (shared by live and Run)."""
    s = {**DEFAULTS, **(settings or {})}
    s["column"] = str(s["column"] or "")
    if not s["column"]:
        raise ShapingError("TD-SHAPE-001", "Pick the column to split")
    if s["split_mode"] not in ("delimiter", "regex") or s["output"] not in (
        "columns",
        "rows",
    ):
        raise ShapingError("TD-SHAPE-004", "Unknown split mode or output")
    pattern = str(s["pattern"] if s["pattern"] is not None else "")
    if pattern == "":
        raise ShapingError("TD-SHAPE-001", "Delimiter is empty")
    low = 1 if s["output"] == "columns" else 0
    try:
        max_splits = int(s["max_splits"])
    except TypeError, ValueError:
        max_splits = -1
    if not low <= max_splits <= MAX_SPLITS:
        raise ShapingError("TD-SHAPE-004", f"Max splits must be {low}-{MAX_SPLITS}")
    s["max_splits"] = max_splits
    if s["split_mode"] == "delimiter":
        pattern = re.sub(r"\\[tnr\\]", lambda m: _ESCAPES[m.group(0)], pattern)
    else:
        try:
            matches_empty = pl.select(pl.lit("").str.contains(pattern)).item()
        except Exception as exc:
            raise ShapingError(
                "TD-SHAPE-040", f"Invalid pattern ({str(exc)[:80]})"
            ) from exc
        if matches_empty:
            raise ShapingError("TD-SHAPE-101", "Pattern must not match an empty string")
    s["pattern"] = pattern
    s["names"] = str(s["names"] or "")
    s["row_index_column"] = str(s["row_index_column"] or "").strip()
    for key in ("trim", "keep_original", "skip_empty"):
        s[key] = bool(s[key])
    return s


def _remainder_pattern(pattern: str, matches: int) -> str:
    """Regex capturing the text after the first ``matches`` separator matches."""
    return f"(?s)^(?:.*?(?:{pattern})){{{matches}}}(?P<{REST}>.*)$"


def _pieces(s: dict) -> list[pl.Expr]:
    """The ``max_splits + 1`` pieces; the last one is the untouched remainder."""
    column = pl.col(s["column"])
    count = s["max_splits"] + 1
    if s["split_mode"] == "delimiter":
        parts = column.str.splitn(s["pattern"], count)
        return [parts.struct.field(f"field_{i}") for i in range(count)]
    # ``str.splitn`` has no regex form: mark every match, split on the mark, and
    # take the last piece from the original so its own separators survive.
    parts = column.str.replace_all(s["pattern"], SENTINEL).str.splitn(SENTINEL, count)
    pieces = [parts.struct.field(f"field_{i}") for i in range(count)]
    rest = column.str.extract_groups(_remainder_pattern(s["pattern"], count - 1))
    pieces[-1] = rest.struct.field(REST)
    return pieces


def _column_names(s: dict, taken: list[str]) -> list[str]:
    count = s["max_splits"] + 1
    given = [x.strip() for x in s["names"].split(",") if x.strip()][:count]
    names: list[str] = []
    for index in range(count):
        base = given[index] if index < len(given) else f"{s['column']}_{index + 1}"
        name = unique_name(base, taken)
        taken.append(name)
        names.append(name)
    return names


def apply_text_to_columns(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = normalize(settings)
    lf = as_lazy(frame)
    schema = schema_of(lf)
    require_columns(schema, [s["column"]])
    if schema[s["column"]] != pl.String:
        raise ShapingError(
            "TD-SHAPE-044", "Only text columns can be split", [s["column"]]
        )
    if s["output"] == "columns":
        names = _column_names(s, list(schema))
        exprs = []
        for piece, name in zip(_pieces(s), names):
            exprs.append((piece.str.strip_chars() if s["trim"] else piece).alias(name))
        out = lf.with_columns(exprs)
        if not s["keep_original"]:
            out = out.drop(s["column"])
        return out
    # rows: one output row per piece (the other columns repeat)
    if s["max_splits"]:
        pieces = pl.concat_list(_pieces(s)).list.drop_nulls()
    elif s["split_mode"] == "regex":
        pieces = (
            pl.col(s["column"])
            .str.replace_all(s["pattern"], SENTINEL)
            .str.split(SENTINEL)
        )
    else:
        pieces = pl.col(s["column"]).str.split(s["pattern"])
    if s["trim"]:
        pieces = pieces.list.eval(pl.element().str.strip_chars())
    if s["skip_empty"]:
        pieces = pieces.list.eval(pl.element().filter(pl.element() != ""))
    out = lf.with_row_index(POS)
    if s["keep_original"]:
        original = unique_name(f"{s['column']}_original", schema)
        out = out.with_columns(pl.col(s["column"]).alias(original))
    out = out.with_columns(pieces.alias(s["column"])).explode(
        s["column"], empty_as_null=True, keep_nulls=True
    )
    if s["row_index_column"]:
        name = unique_name(s["row_index_column"], out.collect_schema().names())
        out = out.with_columns(
            (pl.int_range(pl.len(), dtype=pl.Int64).over(POS) + 1).alias(name)
        )
    return out.drop(POS)


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    """Advisory chip: how many rows the split produced in the live sample."""
    try:
        s = normalize(settings)
        if s["output"] != "rows":
            return []
        source = as_lazy(frames[0])
        before, after = pl.collect_all(
            [
                source.select(pl.len()),
                apply_text_to_columns(source, settings).select(pl.len()),
            ]
        )
    except Exception:  # noqa: BLE001 - chips are advisory
        return []
    scope = f"first {LIVE_SAMPLE_ROWS} rows"
    return [(f"{before.item()} rows become {after.item()} ({scope})", "accent")]


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [apply_text_to_columns(frames[0], settings)]
