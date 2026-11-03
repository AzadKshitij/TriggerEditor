"""Qt-free data profiling (plan 05). Imports only stdlib, polars, orjson."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any

import orjson
import polars as pl

TYPE_SHARE = 0.98  # share of non-blank values that must parse to suggest a type
MIXED_MIN = 0.02  # numeric share at/above which a text column is "mixed"
FAMILY_MIN = 0.5  # numeric-family share needed before a format flag fires
HIGH_CARD_MIN_ROWS = 20
HIGH_CARD_RATIO = 0.95
MOSTLY_NULL_PCT = 50.0
DATE_MIXED_MIN = 0.5  # date-like share at/above which a text column is "mixed dates"
OUTLIER_Z = 10.0  # distance from the mean, in standard deviations
OUTLIER_MIN_ROWS = 20
MAX_TEXT = 100  # characters kept of a top value / min / max text

INT_RE = r"^[+-]?\d{1,18}$"
NUM_RE = r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$"
DOT_DEC_RE = r"^[+-]?\d*\.\d+$"
TRAIL_RE = r"^\d+([.,]\d+)?-$"
DEC_COMMA_RE = r"^[+-]?(\d+|\d{1,3}(\.\d{3})+),\d{1,2}$|^[+-]?\d{1,3}(\.\d{3})+,\d+$"
GROUPED_RE = r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$"
LEAD0_RE = r"^[+-]?0\d+$"
BOOL_RE = r"^(?i:true|false|yes|no|y|n)$"
DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y%m%d",
    "%d-%b-%Y",
    "%d %b %Y",
)
DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
)
FLAG_ORDER = (
    "all_null",
    "all_blank",
    "constant",
    "high_cardinality",
    "mostly_null",
    "mixed_numeric_text",
    "mixed_date_text",
    "leading_zeros",
    "trailing_minus",
    "decimal_comma_suspected",
    "leading_trailing_whitespace",
    "numeric_as_text",
    "date_as_text",
    "negative_values",
    "outlier_suspected",
    "nan_values",
    "inf_values",
)
#: How loudly the dock shows a flag. ``info`` is true but expected (every
#: numeric column of a CSV is "numbers stored as text"); ``warning`` needs a look.
FLAG_TONE: dict[str, str] = {
    flag: "info"
    if flag
    in {
        "numeric_as_text",
        "date_as_text",
        "high_cardinality",
        "constant",
        "negative_values",
    }
    else "warning"
    for flag in FLAG_ORDER
}

PROFILE_SCHEMA: dict[str, Any] = {
    "column": pl.String,
    "position": pl.Int64,
    "dtype": pl.String,
    "row_count": pl.Int64,
    "null_count": pl.Int64,
    "null_pct": pl.Float64,
    "empty_count": pl.Int64,
    "empty_pct": pl.Float64,
    "blank_count": pl.Int64,
    "whitespace_count": pl.Int64,
    "distinct_count": pl.Int64,
    "distinct_is_approx": pl.Boolean,
    "distinct_pct": pl.Float64,
    "min_value": pl.String,
    "max_value": pl.String,
    "min_length": pl.Int64,
    "max_length": pl.Int64,
    "mean_value": pl.Float64,
    "median_value": pl.Float64,
    "std_value": pl.Float64,
    "sum_value": pl.Float64,
    "min_numeric": pl.Float64,
    "max_numeric": pl.Float64,
    "numeric_basis": pl.String,
    "negative_count": pl.Int64,
    "zero_count": pl.Int64,
    "nan_count": pl.Int64,
    "inf_count": pl.Int64,
    "numeric_like_count": pl.Int64,
    "integer_like_count": pl.Int64,
    "date_like_count": pl.Int64,
    "bool_like_count": pl.Int64,
    "leading_zero_count": pl.Int64,
    "trailing_minus_count": pl.Int64,
    "decimal_comma_count": pl.Int64,
    "top_values": pl.String,
    "top_value": pl.String,
    "top_count": pl.Int64,
    "histogram": pl.String,
    "suggested_type": pl.String,
    "suggested_confidence": pl.Float64,
    "flags": pl.String,
    "sampled": pl.Boolean,
}


@dataclass(frozen=True)
class ProfileSettings:
    sample_mode: str = "full"  # "full" | "head" | "random"
    sample_rows: int = 100_000
    seed: int = 42
    top_n: int = 5
    approx_distinct_threshold: int = 2_000_000
    histogram_bins: int = 20

    def key(self) -> tuple:
        return (
            self.sample_mode,
            self.sample_rows,
            self.seed,
            self.top_n,
            self.approx_distinct_threshold,
            self.histogram_bins,
        )


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    count: int  # rows profiled (nulls included)
    null_count: int
    null_pct: float
    distinct_count: int | None
    min: str | None
    max: str | None
    mean: float | None
    sample_values: list[str]  # top-N value texts, most frequent first
    # --- plan-05 extensions (all defaulted; plan 06 reads only the fields above) ---
    position: int = 0
    empty_count: int | None = None
    empty_pct: float | None = None
    blank_count: int | None = None
    whitespace_count: int | None = None
    distinct_is_approx: bool = False
    distinct_pct: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    median: float | None = None
    std: float | None = None
    sum: float | None = None
    min_numeric: float | None = None
    max_numeric: float | None = None
    numeric_basis: str = ""
    negative_count: int | None = None
    zero_count: int | None = None
    nan_count: int | None = None
    inf_count: int | None = None
    numeric_like_count: int | None = None
    integer_like_count: int | None = None
    date_like_count: int | None = None
    bool_like_count: int | None = None
    leading_zero_count: int | None = None
    trailing_minus_count: int | None = None
    decimal_comma_count: int | None = None
    datetime_like_count: int | None = None
    dot_decimal_count: int | None = None
    top_values: list[tuple[str, int]] = field(default_factory=list)
    date_format_hint: str = ""
    suggested_type: str = ""
    suggested_confidence: float = 0.0
    flags: list[str] = field(default_factory=list)
    histogram: list[int] = field(default_factory=list)
    sampled: bool = False


@dataclass
class DataProfile:
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    sampled: bool
    settings: ProfileSettings = field(default_factory=ProfileSettings)
    passes: int = 0
    seconds: float = 0.0

    def to_frame(self) -> pl.DataFrame:
        return profile_to_frame(self)


def empty_profile_frame() -> pl.DataFrame:
    return pl.DataFrame(schema=PROFILE_SCHEMA)


def dtype_class(dt: pl.DataType) -> str:
    if dt.is_numeric():
        return "numeric"
    if dt == pl.String:
        return "string"
    if dt == pl.Categorical or isinstance(dt, (pl.Categorical, pl.Enum)):
        return "categorical"
    if dt == pl.Boolean:
        return "boolean"
    if dt in (pl.Date, pl.Time) or isinstance(dt, pl.Datetime):
        return "temporal"
    if isinstance(dt, pl.Duration):
        return "duration"
    if dt == pl.Null:
        return "null"
    if dt == pl.Binary:
        return "binary"
    return "nested"  # List, Array, Struct, Object, Unknown


class _Collector:
    """Counts collect calls so tests can prove the pass budget."""

    def __init__(self) -> None:
        self.passes = 0

    def one(self, lf: pl.LazyFrame) -> pl.DataFrame:
        self.passes += 1
        return lf.collect()

    def many(self, frames: list[pl.LazyFrame]) -> list[pl.DataFrame]:
        self.passes += 1
        return pl.collect_all(frames)


def _parse_date(st: pl.Expr) -> pl.Expr:
    """First matching date format wins, per value."""
    return pl.coalesce(
        [st.str.to_date(f, strict=False, exact=True) for f in DATE_FORMATS]
    )


def _parse_datetime(st: pl.Expr) -> pl.Expr:
    return pl.coalesce(
        [st.str.to_datetime(f, strict=False, exact=True) for f in DATETIME_FORMATS]
    )


def _aggregate_exprs(i: int, name: str, dt: pl.DataType, approx: bool) -> list[pl.Expr]:
    c = pl.col(name)

    def k(m: str) -> str:
        return f"c{i}__{m}"

    cls = dtype_class(dt)
    out: list[pl.Expr] = [c.null_count().alias(k("nulls"))]
    if cls == "numeric":
        f = c.cast(pl.Float64)
        fin = f.filter(f.is_finite())
        out += [
            f.is_nan().sum().alias(k("nan")),
            f.is_infinite().sum().alias(k("inf")),
            fin.min().alias(k("nmin")),
            fin.max().alias(k("nmax")),
            fin.mean().alias(k("mean")),
            fin.median().alias(k("median")),
            fin.std().alias(k("std")),
            fin.sum().alias(k("sum")),
            (fin < 0).sum().alias(k("neg")),
            (fin == 0).sum().alias(k("zero")),
            c.min().alias(k("min")),
            c.max().alias(k("max")),
        ]
    elif cls == "string":
        s = c.cast(pl.String)
        st = s.str.strip_chars()
        ln = s.str.len_chars()
        parsed = pl.when(st.str.contains(NUM_RE)).then(
            st.cast(pl.Float64, strict=False)
        )
        pf = parsed.filter(parsed.is_finite())
        date_ok = _parse_date(st).is_not_null()
        dtm_ok = _parse_datetime(st).is_not_null()

        def cnt(e: pl.Expr, m: str) -> pl.Expr:
            return e.sum().alias(k(m))

        out += [
            cnt(s == "", "empty"),
            cnt(st == "", "blank"),
            cnt(s != st, "ws"),
            ln.min().alias(k("minlen")),
            ln.max().alias(k("maxlen")),
            s.min().alias(k("min")),
            s.max().alias(k("max")),
            cnt(st.str.contains(INT_RE), "int"),
            cnt(st.str.contains(NUM_RE), "num"),
            cnt(st.str.contains(DOT_DEC_RE), "dotdec"),
            cnt(st.str.contains(TRAIL_RE), "trail"),
            cnt(st.str.contains(DEC_COMMA_RE), "deccomma"),
            cnt(st.str.contains(GROUPED_RE), "grouped"),
            cnt(st.str.contains(LEAD0_RE), "lead0"),
            cnt(st.str.contains(BOOL_RE), "bool"),
            cnt(date_ok | dtm_ok, "date"),
            cnt(dtm_ok, "dtm"),
            pf.min().alias(k("nmin")),
            pf.max().alias(k("nmax")),
            pf.mean().alias(k("mean")),
            pf.median().alias(k("median")),
            pf.std().alias(k("std")),
            pf.sum().alias(k("sum")),
            cnt(pf < 0, "neg"),
            cnt(pf == 0, "zero"),
            pf.len().alias(k("pn")),
        ]
    elif cls in ("boolean", "temporal", "duration"):
        out += [c.min().alias(k("min")), c.max().alias(k("max"))]
    elif cls == "categorical":
        out += [
            c.cast(pl.String).min().alias(k("min")),
            c.cast(pl.String).max().alias(k("max")),
        ]
    if cls != "nested":
        nn = c.drop_nulls()
        out.append(
            (nn.approx_n_unique() if approx else nn.n_unique()).alias(k("distinct"))
        )
    return out


def _text(v: Any) -> str | None:
    if v is None:
        return None
    t = v if isinstance(v, str) else str(v)
    return t if len(t) <= MAX_TEXT else t[: MAX_TEXT - 1] + "…"


def _suggest(cp: ColumnProfile, base: int, fam: int) -> tuple[str, float]:
    """Suggested type for a String column; first matching rule wins."""
    if base <= 0:
        return "Unknown", 0.0
    ints = cp.integer_like_count or 0
    if ints / base >= TYPE_SHARE and (cp.leading_zero_count or 0) > 0:
        return "String", 1.0  # keep text: converting would drop the zeros
    if ints / base >= TYPE_SHARE:
        return "Int64", round(ints / base, 4)
    if fam / base >= TYPE_SHARE:
        return "Float64", round(fam / base, 4)
    bools = cp.bool_like_count or 0
    if bools / base >= TYPE_SHARE:
        return "Boolean", round(bools / base, 4)
    dates = cp.date_like_count or 0
    if dates / base >= TYPE_SHARE:
        dtm = cp.datetime_like_count or 0
        return ("Datetime" if dtm * 2 >= dates else "Date"), round(dates / base, 4)
    return "String", 1.0


def _flags(cp: ColumnProfile, base: int, fam: int, native: bool) -> list[str]:
    nn = cp.count - cp.null_count
    hit: set[str] = set()
    if cp.count > 0 and cp.null_count == cp.count:
        hit.add("all_null")
    if cp.count > 0 and cp.null_count < cp.count and base == 0 and not native:
        hit.add("all_blank")
    if cp.count >= 2 and cp.null_count == 0 and cp.distinct_count == 1:
        hit.add("constant")
    if (
        nn >= HIGH_CARD_MIN_ROWS
        and cp.distinct_count is not None
        and cp.distinct_count / nn >= HIGH_CARD_RATIO
    ):
        hit.add("high_cardinality")
    if cp.null_pct >= MOSTLY_NULL_PCT and "all_null" not in hit:
        hit.add("mostly_null")
    if (cp.nan_count or 0) > 0:
        hit.add("nan_values")
    if (cp.inf_count or 0) > 0:
        hit.add("inf_values")
    if not native and base > 0:
        share = fam / base
        if MIXED_MIN <= share < TYPE_SHARE:
            hit.add("mixed_numeric_text")
        date_share = (cp.date_like_count or 0) / base
        if (
            DATE_MIXED_MIN <= date_share < TYPE_SHARE
            and (cp.integer_like_count or 0) / base < TYPE_SHARE
        ):
            hit.add("mixed_date_text")
        if (cp.leading_zero_count or 0) > 0 and (
            cp.integer_like_count or 0
        ) / base >= FAMILY_MIN:
            hit.add("leading_zeros")
        if (cp.trailing_minus_count or 0) > 0 and share >= FAMILY_MIN:
            hit.add("trailing_minus")
        if (
            (cp.decimal_comma_count or 0) > 0
            and share >= FAMILY_MIN
            and (cp.decimal_comma_count or 0) > (cp.dot_decimal_count or 0)
        ):
            hit.add("decimal_comma_suspected")
        if cp.suggested_type in ("Int64", "Float64"):
            hit.add("numeric_as_text")
        if cp.suggested_type in ("Date", "Datetime"):
            hit.add("date_as_text")
    if (cp.whitespace_count or 0) > 0:
        hit.add("leading_trailing_whitespace")
    if cp.numeric_basis and (cp.negative_count or 0) > 0:
        hit.add("negative_values")
    if (
        cp.numeric_basis
        and nn >= OUTLIER_MIN_ROWS
        and cp.std
        and cp.mean is not None
        and cp.min_numeric is not None
        and cp.max_numeric is not None
        and max(cp.max_numeric - cp.mean, cp.mean - cp.min_numeric) / cp.std
        >= OUTLIER_Z
    ):
        hit.add("outlier_suspected")
    return [f for f in FLAG_ORDER if f in hit]


def _stable(x: float | None) -> float | None:
    """Round to 12 significant digits.

    Polars adds floats across threads, so the last bit of a mean/std/sum can
    differ from one run to the next. Two runs over the same data must give the
    same profile (reperformance), and 12 digits is far below what anyone reads.
    """
    if x is None or not math.isfinite(x):
        return x
    return float(f"{x:.12g}")


def _num_text(x: float | None) -> str | None:
    return None if x is None else f"{x:.15g}"


def _pct(part: int | None, whole: int) -> float | None:
    if part is None:
        return None
    return 0.0 if whole <= 0 else part * 100.0 / whole


def _prepare(lf: pl.LazyFrame, s: ProfileSettings, coll: _Collector):
    """Return (work frame, rows profiled, sampled)."""
    n = max(1, int(s.sample_rows))
    if s.sample_mode == "head":
        df = coll.one(lf.head(n))
        return df.lazy(), df.height, df.height >= n
    total = int(coll.one(lf.select(pl.len())).item())
    if s.sample_mode == "random" and total > n:
        idx = sorted(random.Random(s.seed).sample(range(total), n))
        keep = pl.Series("i", idx, dtype=pl.Int64)
        tag = "__pf_i"
        while tag in lf.collect_schema().names():
            tag += "_"
        sampled = (
            lf.with_row_index(tag)
            .filter(pl.col(tag).cast(pl.Int64).is_in(keep.implode()))
            .drop(tag)
        )
        df = coll.one(sampled)
        return df.lazy(), df.height, True
    return lf, total, False


def profile_frame(
    frame, *, max_rows: int | None = None, settings: ProfileSettings | None = None
) -> DataProfile:
    """Profile ``frame`` (LazyFrame or DataFrame). Never raises for data reasons."""
    t0 = time.perf_counter()
    if settings is None:
        settings = (
            ProfileSettings(sample_mode="head", sample_rows=max_rows)
            if max_rows is not None
            else ProfileSettings()
        )
    lf = frame.lazy() if isinstance(frame, pl.DataFrame) else frame
    schema = lf.collect_schema()
    coll = _Collector()
    names = list(schema.names())
    if not names:
        return DataProfile(0, 0, [], False, settings, 0, time.perf_counter() - t0)
    work, rows, sampled = _prepare(lf, settings, coll)
    approx = rows > settings.approx_distinct_threshold

    exprs: list[pl.Expr] = [pl.len().alias("rows")]
    for i, name in enumerate(names):
        exprs += _aggregate_exprs(i, name, schema[name], approx)
    r = coll.one(work.select(exprs)).row(0, named=True)
    rows = int(r["rows"])

    cols: list[ColumnProfile] = []
    fams: dict[int, int] = {}
    bases: dict[int, int] = {}
    for i, name in enumerate(names):
        dt = schema[name]
        cls = dtype_class(dt)

        def g(m: str, _i: int = i):
            return r.get(f"c{_i}__{m}")

        nulls = int(g("nulls") or 0)
        cp = ColumnProfile(
            name=name,
            dtype=str(dt),
            count=rows,
            null_count=nulls,
            null_pct=_pct(nulls, rows) or 0.0,
            distinct_count=None,
            min=None,
            max=None,
            mean=None,
            sample_values=[],
            position=i + 1,
            sampled=sampled,
        )
        if g("distinct") is not None:
            cp.distinct_count = int(g("distinct"))
            cp.distinct_is_approx = approx
            cp.distinct_pct = _pct(cp.distinct_count, rows - nulls)
        if cls == "numeric":
            cp.numeric_basis = "native"
            is_float = dt.is_float()
            cp.min = _text(g("nmin") if is_float else g("min"))
            cp.max = _text(g("nmax") if is_float else g("max"))
            cp.nan_count, cp.inf_count = int(g("nan") or 0), int(g("inf") or 0)
        elif cls == "string":
            cp.min, cp.max = _text(g("min")), _text(g("max"))
            cp.empty_count, cp.blank_count = int(g("empty") or 0), int(g("blank") or 0)
            cp.whitespace_count = int(g("ws") or 0)
            cp.empty_pct = _pct(cp.empty_count, rows)
            cp.min_length, cp.max_length = g("minlen"), g("maxlen")
            cp.numeric_like_count, cp.integer_like_count = (
                int(g("num") or 0),
                int(g("int") or 0),
            )
            cp.date_like_count, cp.datetime_like_count = (
                int(g("date") or 0),
                int(g("dtm") or 0),
            )
            cp.bool_like_count = int(g("bool") or 0)
            cp.leading_zero_count = int(g("lead0") or 0)
            cp.trailing_minus_count = int(g("trail") or 0)
            cp.decimal_comma_count = int(g("deccomma") or 0)
            cp.dot_decimal_count = int(g("dotdec") or 0)
            if (g("pn") or 0) > 0:
                cp.numeric_basis = "parsed_text"
            fams[i] = (
                cp.numeric_like_count
                + cp.trailing_minus_count
                + cp.decimal_comma_count
                + int(g("grouped") or 0)
            )
            bases[i] = rows - nulls - cp.blank_count
        elif cls in ("boolean", "temporal", "duration", "categorical"):
            cp.min, cp.max = _text(g("min")), _text(g("max"))
        if cp.numeric_basis:
            cp.mean, cp.median, cp.std, cp.sum = (
                _stable(g("mean")),
                _stable(g("median")),
                _stable(g("std")),
                _stable(g("sum")),
            )
            cp.min_numeric, cp.max_numeric = g("nmin"), g("nmax")
            cp.negative_count, cp.zero_count = int(g("neg") or 0), int(g("zero") or 0)
        if cls == "string":
            cp.suggested_type, cp.suggested_confidence = _suggest(cp, bases[i], fams[i])
            # Text order of "1002.89" / "999.54" or "31-12-2024" is misleading;
            # once the column reads as numbers or dates, show the parsed range.
            # (The date range is filled in by the detail pass, which only parses
            # the columns that are actually dates.)
            if cp.suggested_type in ("Int64", "Float64") and cp.min_numeric is not None:
                cp.min, cp.max = _num_text(cp.min_numeric), _num_text(cp.max_numeric)
        else:
            cp.suggested_type, cp.suggested_confidence = cp.dtype, 1.0
        cp.flags = _flags(cp, bases.get(i, 0), fams.get(i, 0), cls != "string")
        cols.append(cp)

    _detail_pass(work, cols, schema, settings, coll)
    _histogram_pass(work, cols, schema, settings, coll)
    return DataProfile(
        rows, len(cols), cols, sampled, settings, coll.passes, time.perf_counter() - t0
    )


def _detail_pass(work, cols, schema, settings, coll) -> None:
    frames, owners = [], []
    n = max(1, int(settings.top_n))
    for i, cp in enumerate(cols):
        cls = dtype_class(schema[cp.name])
        if cls in ("duration", "binary", "null", "nested") or cp.count == cp.null_count:
            continue
        v = pl.col(cp.name).drop_nulls().cast(pl.String).alias("v")
        frames.append(
            work.select(v)
            .group_by("v")
            .agg(pl.len().alias("n"))
            .sort(["n", "v"], descending=[True, False])
            .head(n)
        )
        owners.append(("top", i))
    cand = [i for i, cp in enumerate(cols) if (cp.date_like_count or 0) > 0]
    if cand:
        ex = []
        for i in cand:
            st = pl.col(cols[i].name).cast(pl.String).str.strip_chars()
            for j, f in enumerate(DATE_FORMATS):
                ex.append(
                    st.str.to_date(f, strict=False, exact=True)
                    .is_not_null()
                    .sum()
                    .alias(f"c{i}__f{j}")
                )
            for j, f in enumerate(DATETIME_FORMATS):
                ex.append(
                    st.str.to_datetime(f, strict=False, exact=True)
                    .is_not_null()
                    .sum()
                    .alias(f"c{i}__t{j}")
                )
            # Parsed range, only for columns that read as dates (see _num_text).
            if cols[i].suggested_type == "Date":
                parsed = _parse_date(st)
                ex += [
                    parsed.min().alias(f"c{i}__dmin"),
                    parsed.max().alias(f"c{i}__dmax"),
                ]
            elif cols[i].suggested_type == "Datetime":
                parsed = _parse_datetime(st)
                ex += [
                    parsed.min().alias(f"c{i}__dmin"),
                    parsed.max().alias(f"c{i}__dmax"),
                ]
        frames.append(work.select(ex))
        owners.append(("fmt", cand))
    if not frames:
        return
    for (kind, ref), out in zip(owners, coll.many(frames)):
        if kind == "top":
            cp = cols[ref]
            cp.top_values = [(_text(a), int(b)) for a, b in out.iter_rows()]
            cp.sample_values = [a for a, _ in cp.top_values]
        else:
            row = out.row(0, named=True)
            fmts = list(DATE_FORMATS) + list(DATETIME_FORMATS)
            for i in ref:
                counts = [row[f"c{i}__f{j}"] for j in range(len(DATE_FORMATS))] + [
                    row[f"c{i}__t{j}"] for j in range(len(DATETIME_FORMATS))
                ]
                best = max(range(len(counts)), key=lambda j: (counts[j], -j))
                cols[i].date_format_hint = fmts[best] if counts[best] > 0 else ""
                low, high = row.get(f"c{i}__dmin"), row.get(f"c{i}__dmax")
                if low is not None and high is not None:
                    pattern = (
                        "%Y-%m-%d"
                        if cols[i].suggested_type == "Date"
                        else "%Y-%m-%d %H:%M:%S"
                    )
                    cols[i].min, cols[i].max = (
                        low.strftime(pattern),
                        high.strftime(pattern),
                    )


def _histogram_pass(work, cols, schema, settings, coll) -> None:
    bins = max(2, int(settings.histogram_bins))
    frames, owners = [], []
    for i, cp in enumerate(cols):
        if cp.numeric_basis == "" or cp.min_numeric is None or cp.max_numeric is None:
            continue
        lo, hi = float(cp.min_numeric), float(cp.max_numeric)
        if not hi > lo:
            continue
        if cp.numeric_basis == "native":
            x = pl.col(cp.name).cast(pl.Float64)
        else:
            st = pl.col(cp.name).cast(pl.String).str.strip_chars()
            x = pl.when(st.str.contains(NUM_RE)).then(st.cast(pl.Float64, strict=False))
        xf = x.filter(x.is_finite())
        b = ((xf - lo) / (hi - lo) * bins).floor().clip(0, bins - 1).cast(pl.Int64)
        frames.append(work.select(b.alias("b")).group_by("b").agg(pl.len().alias("n")))
        owners.append(i)
    if not frames:
        return
    for i, out in zip(owners, coll.many(frames)):
        counts = [0] * bins
        for b, n in out.iter_rows():
            counts[int(b)] = int(n)
        cols[i].histogram = counts


_ATTR = {
    "column": "name",
    "row_count": "count",
    "min_value": "min",
    "max_value": "max",
    "mean_value": "mean",
    "median_value": "median",
    "std_value": "std",
    "sum_value": "sum",
    "flags": "flags",
}


def profile_to_frame(p: DataProfile) -> pl.DataFrame:
    """One row per column, exactly ``PROFILE_SCHEMA`` (empty profile -> 0 rows)."""
    rows = []
    for c in p.columns:
        row = {n: getattr(c, _ATTR.get(n, n), None) for n in PROFILE_SCHEMA}
        row["flags"] = ",".join(c.flags)
        row["top_values"] = orjson.dumps([[v, n] for v, n in c.top_values]).decode()
        row["top_value"] = c.top_values[0][0] if c.top_values else None
        row["top_count"] = c.top_values[0][1] if c.top_values else None
        row["histogram"] = orjson.dumps(c.histogram).decode()
        rows.append(row)
    return pl.DataFrame(rows, schema=PROFILE_SCHEMA)


#: Columns that map straight onto a ``ColumnProfile`` attribute of the same name.
_DIRECT = (
    "position",
    "dtype",
    "null_count",
    "null_pct",
    "empty_count",
    "empty_pct",
    "blank_count",
    "whitespace_count",
    "distinct_count",
    "distinct_is_approx",
    "distinct_pct",
    "min_length",
    "max_length",
    "min_numeric",
    "max_numeric",
    "numeric_basis",
    "negative_count",
    "zero_count",
    "nan_count",
    "inf_count",
    "numeric_like_count",
    "integer_like_count",
    "date_like_count",
    "bool_like_count",
    "leading_zero_count",
    "trailing_minus_count",
    "decimal_comma_count",
    "suggested_type",
    "suggested_confidence",
    "sampled",
)


def profile_from_frame(
    frame: pl.DataFrame, settings: ProfileSettings | None = None
) -> DataProfile:
    """Rebuild a ``DataProfile`` from the table ``profile_to_frame`` wrote.

    The profile table carries every figure the dock and the report show, so a
    Run's output socket can be displayed without profiling the data a second
    time. ``settings`` is only used to describe the profile (sample mode, seed);
    the table itself does not record it.
    """
    settings = settings or ProfileSettings()
    columns: list[ColumnProfile] = []
    for row in frame.iter_rows(named=True):
        top = [(str(v), int(n)) for v, n in orjson.loads(row.get("top_values") or "[]")]
        cp = ColumnProfile(
            name=row["column"],
            dtype=row["dtype"],
            count=row["row_count"] or 0,
            null_count=row["null_count"] or 0,
            null_pct=row["null_pct"] or 0.0,
            distinct_count=row["distinct_count"],
            min=row["min_value"],
            max=row["max_value"],
            mean=row["mean_value"],
            sample_values=[text for text, _count in top],
        )
        for key in _DIRECT:
            setattr(cp, key, row.get(key))
        cp.numeric_basis = row.get("numeric_basis") or ""
        cp.median, cp.std, cp.sum = (
            row["median_value"],
            row["std_value"],
            row["sum_value"],
        )
        cp.top_values = top
        cp.histogram = [int(n) for n in orjson.loads(row.get("histogram") or "[]")]
        cp.flags = [flag for flag in (row.get("flags") or "").split(",") if flag]
        columns.append(cp)
    rows = columns[0].count if columns else 0
    return DataProfile(
        rows,
        len(columns),
        columns,
        any(cp.sampled for cp in columns),
        settings,
    )


def profile_table(frame, **settings) -> pl.DataFrame:
    """Entry point used by generated code: settings keys = ProfileSettings fields."""
    return profile_frame(frame, settings=ProfileSettings(**settings)).to_frame()


def profile_to_tsv(frame: pl.DataFrame) -> str:
    """Tab-separated text of a profile frame (header + rows) for the clipboard."""

    def cell(v: Any) -> str:
        if v is None:
            return ""
        return str(v).replace("\t", " ").replace("\r", " ").replace("\n", " ")

    rows = ["\t".join(frame.columns)]
    rows += ["\t".join(cell(v) for v in r) for r in frame.iter_rows()]
    return "\n".join(rows) + "\n"


def write_profile_xlsx(frame: pl.DataFrame, path: str) -> None:
    """Thin adapter over plan 06's helper; this module imports no Excel library."""
    try:
        from trigger_designer.core.excel import write_frame_xlsx
    except ImportError as exc:  # plan 06 not merged yet, or xlsxwriter missing
        raise RuntimeError(
            "Excel export is unavailable: the Excel writer (xlsxwriter) is not installed"
        ) from exc
    write_frame_xlsx(frame, path, sheet_name="Profile")


def profile_summary(p: DataProfile) -> dict[str, Any]:
    """Small JSON-safe digest for run records and workpapers."""
    return {
        "rows": p.row_count,
        "columns": p.column_count,
        "sampled": p.sampled,
        "sample_mode": p.settings.sample_mode,
        "passes": p.passes,
        "flagged": {c.name: list(c.flags) for c in p.columns if c.flags},
    }
