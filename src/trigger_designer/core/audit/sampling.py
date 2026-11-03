"""Sample: a draw a reviewer can redraw (Qt-free).

Same rows + same settings + same seed give the identical sample, whatever order
the rows arrive in (docs/plan/04-audit-test-nodes.md section 4.4). Two things
make that true:

* the population is put in a **canonical order** first (sorted by the stable
  key, nulls last, the remaining columns breaking ties), and every draw is a set
  of positions in that order;
* randomness comes from the SplitMix64 generator below, never from Polars or
  NumPy, so a library upgrade cannot change a sample.

The algorithm id ``td-sample-1`` is written to every Selection log. Changing any
step of a draw requires a new id.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np
import polars as pl

from trigger_designer.core.audit.common import (
    ALL_SIZE,
    ROW,
    AuditConfigError,
    AuditResult,
    ParamsBase,
    amount_expr,
    as_lazy,
    check_range,
    check_reserved,
    is_nested,
    json_params,
    need,
)
from trigger_designer.core.audit.test_summary import TestSummary

ALGORITHM = "td-sample-1"
OP = "audit.sample"
TEST_NAME = "Sample"
METHODS = ("random", "systematic", "mus", "stratified")
METHOD_TEXT = {
    "random": "random",
    "systematic": "systematic",
    "mus": "monetary unit",
    "stratified": "stratified",
}
SIZE_KINDS = ("count", "percent")

#: Above this many rows live evaluation does not draw (it runs on the GUI
#: thread and the draw sorts the population); Run always draws.
LIVE_ROW_LIMIT = 200_000

SEED_MAX = (1 << 63) - 1
AMT = "__td_amt"
SEQ, STRATUM, BASIS = "sample_seq", "sample_stratum", "sample_basis"
RESERVED = (SEQ, STRATUM, BASIS)
ALL_COLUMNS_TEXT = "(all columns)"

LOG_SCHEMA: dict[str, pl.DataType] = {
    "scope": pl.String,
    "stratum": pl.Int64,
    "method": pl.String,
    "seed": pl.Int64,
    "algorithm": pl.String,
    "population_rows": pl.Int64,
    "population_value": pl.Float64,
    "requested_size": pl.Int64,
    "sample_size": pl.Int64,
    "sample_value": pl.Float64,
    "interval": pl.Float64,
    "start": pl.Float64,
    "high_value_items": pl.Int64,
    "lower_bound": pl.Float64,
    "upper_bound": pl.Float64,
    "key_columns": pl.String,
    "amount_column": pl.String,
    "parameters": pl.String,
    "note": pl.String,
}
LOG_COLUMNS = tuple(LOG_SCHEMA)

KEY_TIP = (
    "Rows are put in a fixed order by these columns before the draw, so the "
    "same sample comes back whatever order the data arrives in. Choose a column "
    "that is unique per row (for example the journal number) to keep memory "
    "small. Leave empty to use every column."
)


@dataclass
class SamplingParams(ParamsBase):
    method: str = "random"  # random | systematic | mus | stratified
    seed: int = 42  # any non-negative int; the dock spins 0 .. 2**31-1
    size_kind: str = "count"  # count | percent (ignored by stratified)
    sample_size: int = 100
    sample_percent: float = 10.0
    key_columns: list = field(default_factory=list)  # [] = all columns
    amount_column: str = ""  # required for mus / stratified
    band_edges: list = field(default_factory=list)  # ascending; |x| < edge[0] ...
    band_sizes: list = field(default_factory=list)  # len(edges)+1; -1 = every row


# ---- SplitMix64 ------------------------------------------------------------
_MASK = (1 << 64) - 1


def _mix(z: int) -> int:
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
    return z ^ (z >> 31)


class SplitMix64:
    """The published SplitMix64 generator (``SplitMix64(0)`` starts ``0xe220a839...``)."""

    def __init__(self, seed: int) -> None:
        self.state = seed & _MASK

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        return _mix(self.state)

    def unit(self) -> float:
        """Uniform in [0, 1) from the top 53 bits."""
        return (self.next_u64() >> 11) / float(1 << 53)


def derive_seed(seed: int, tag: int) -> int:
    """An independent stream per stratum: ``derive_seed(seed, stratum_number)``."""
    return _mix((seed & _MASK) ^ _mix((tag + 1) & _MASK))


def floyd_positions(rng: SplitMix64, population: int, size: int) -> list[int]:
    """A uniform subset of ``range(population)`` without replacement, sorted.

    Robert Floyd's algorithm: O(size) time and memory. The modulo bias is below
    1e-9 for populations under 1e10, which is accepted.
    """
    if size >= population:
        return list(range(population))
    chosen: set[int] = set()
    for j in range(population - size, population):
        t = rng.next_u64() % (j + 1)
        chosen.add(j if t in chosen else t)
    return sorted(chosen)


def systematic_positions(
    rng: SplitMix64, population: int, size: int
) -> tuple[list[int], float, float]:
    """Every ``population / size``-th row from a random start: ``(positions, interval, start)``."""
    if size >= population:
        return list(range(population)), 1.0, 0.0
    interval = population / size
    start = rng.unit() * interval
    return [math.floor(start + i * interval) for i in range(size)], interval, start


# ---- settings --------------------------------------------------------------
def requested_size(params: SamplingParams, available: int) -> int:
    """The size rule: a count as typed, or a percent of ``available`` rounded up."""
    if params.size_kind == "percent":
        if available <= 0:
            return 0
        exact = Fraction(repr(float(params.sample_percent))) * available / 100
        return max(1, math.ceil(exact))
    return int(params.sample_size)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _strata_error(label: str, detail: str) -> AuditConfigError:
    return AuditConfigError("TD-AUDIT-009", f"{label}: {detail}.", field=label)


def validate_params(params: SamplingParams, schema: dict) -> list[str]:
    """Raise ``AuditConfigError`` for a bad setting; return the key columns."""
    check_range(
        params.method in METHODS,
        "method",
        "Sample method",
        "random, systematic, mus or stratified",
    )
    check_range(
        isinstance(params.seed, int)
        and not isinstance(params.seed, bool)
        and 0 <= params.seed <= SEED_MAX,
        "seed",
        "Seed",
        f"a whole number from 0 to {SEED_MAX:,}",
    )
    check_range(
        params.size_kind in SIZE_KINDS,
        "size_kind",
        "Sample size kind",
        "count or percent",
    )
    keys = list(dict.fromkeys(params.key_columns))
    for key in keys:
        need(schema, "key_columns", key, "key")
    if params.method != "stratified":
        if params.size_kind == "count":
            check_range(
                _is_number(params.sample_size) and params.sample_size >= 1,
                "sample_size",
                "Sample size",
                "1 or more",
            )
        else:
            check_range(
                _is_number(params.sample_percent)
                and math.isfinite(params.sample_percent)
                and 0 < params.sample_percent <= 100,
                "sample_percent",
                "Sample percent",
                "above 0 and at most 100",
            )
    if params.method in ("mus", "stratified") or params.amount_column:
        need(schema, "amount_column", params.amount_column, "amount")
    if params.method == "stratified":
        edges = list(params.band_edges)
        if not all(_is_number(e) and math.isfinite(e) and e >= 0 for e in edges) or any(
            b <= a for a, b in itertools.pairwise(edges)
        ):
            raise _strata_error(
                "Strata edges", "values must be 0 or more and strictly increasing"
            )
        sizes = list(params.band_sizes)
        if len(sizes) != len(edges) + 1:
            raise _strata_error(
                "Strata sizes", f"expected {len(edges) + 1} values, found {len(sizes)}"
            )
        if any(
            not isinstance(s, int) or isinstance(s, bool) or (s < 1 and s != ALL_SIZE)
            for s in sizes
        ):
            raise _strata_error("Strata sizes", "each size must be 1 or more, or all")
    check_reserved(schema, [*RESERVED, ROW, AMT])
    return keys


# ---- canonical order -------------------------------------------------------
def _sort_expr(name: str, dtype: pl.DataType) -> pl.Expr:
    # A Categorical sorts by arrival order in some versions; text never does.
    if dtype == pl.Categorical:
        return pl.col(name).cast(pl.String)
    return pl.col(name)


def _reject_nested(schema: dict, names: list[str]) -> None:
    for name in names:
        if is_nested(schema[name]):
            raise AuditConfigError(
                "TD-AUDIT-003",
                f"Column '{name}' holds nested values and cannot be used for this "
                "test. Choose a key column so it is not needed to order the rows.",
                field="key_columns",
                columns=(name,),
            )


def canonical_order(
    lf: pl.LazyFrame, schema: dict, keys: list[str], amount_column: str = ""
) -> pl.DataFrame:
    """The population in canonical order: ``ROW`` (input position) and, with an
    amount column, ``AMT`` (Float64 or null).

    Sorted by ``keys`` (every column when empty), nulls last; when the key is not
    unique the remaining columns break the tie, so the order is total up to
    identical rows (which are interchangeable). With a unique key only the key
    columns and the row index are held; with a tied or empty key the whole frame.
    """
    all_cols = list(schema)
    base = lf.with_row_index(ROW)
    if amount_column:
        parsed = amount_expr(amount_column, schema[amount_column])
        base = base.with_columns(pl.when(parsed.is_finite()).then(parsed).alias(AMT))
    if not all_cols:
        return base.select(ROW).collect()
    if not keys:
        _reject_nested(schema, all_cols)
        sort_cols = all_cols
    else:
        stats = base.select(
            pl.struct([_sort_expr(k, schema[k]) for k in keys]).n_unique().alias("u"),
            pl.len().alias("n"),
        ).collect(engine="streaming")
        if stats["u"][0] == stats["n"][0]:
            sort_cols = keys
        else:
            rest = [c for c in all_cols if c not in keys]
            _reject_nested(schema, rest)
            sort_cols = keys + rest
    carried = [ROW] + ([AMT] if amount_column else [])
    # Sort columns first (renamed so a user column cannot clash), then the payload.
    order_names = [f"__td_k{i}" for i in range(len(sort_cols))]
    staged = base.select(
        *[_sort_expr(c, schema[c]).alias(n) for c, n in zip(sort_cols, order_names)],
        *[pl.col(c) for c in carried],
    )
    return (
        staged.sort(order_names, nulls_last=True, maintain_order=True)
        .select(carried)
        .collect()
    )


# ---- draws -----------------------------------------------------------------
@dataclass
class _Draw:
    """The outcome of one draw, in canonical positions."""

    positions: list[int]
    requested: int
    available: int
    notes: list[str] = field(default_factory=list)
    interval: float | None = None
    start: float | None = None
    high_value: int | None = None
    basis: list[str] | None = None  # MUS, parallel to positions
    strata: list[int] | None = None  # stratified, parallel to positions
    strata_rows: list[dict] = field(default_factory=list)
    capped: bool = False


def _note_103(requested: int, available: int) -> str:
    return (
        f"TD-AUDIT-103: Requested {requested:,} but only {available:,} rows exist; "
        "the whole population was selected."
    )


def _fsum(values: np.ndarray) -> float:
    """Order-independent, correctly rounded sum (a log value must not drift)."""
    return math.fsum(values.tolist())


def _abs_amounts(canon: pl.DataFrame) -> np.ndarray:
    """|amount| per canonical position; NaN where the amount is unreadable."""
    return canon[AMT].abs().cast(pl.Float64).to_numpy().astype(np.float64)


def _draw_plain(params: SamplingParams, n_rows: int) -> _Draw:
    requested = requested_size(params, n_rows)
    n = min(requested, n_rows)
    draw = _Draw([], requested, n_rows)
    if requested > n_rows:
        draw.capped = True
        draw.notes.append(_note_103(requested, n_rows))
    rng = SplitMix64(params.seed)
    if params.method == "random":
        draw.positions = floyd_positions(rng, n_rows, n)
    else:
        draw.positions, draw.interval, draw.start = systematic_positions(rng, n_rows, n)
        if n == 0:
            draw.interval = draw.start = None
    return draw


def _draw_mus(params: SamplingParams, canon: pl.DataFrame) -> _Draw:
    amounts = _abs_amounts(canon)
    eligible = np.flatnonzero(np.isfinite(amounts) & (amounts > 0))
    skipped = len(amounts) - len(eligible)
    if len(amounts) and not len(eligible):
        raise AuditConfigError(
            "TD-AUDIT-010",
            f"No row has a readable amount in '{params.amount_column}', so a "
            "value-based sample cannot be drawn.",
            field="amount_column",
            columns=(params.amount_column,),
        )
    a = amounts[eligible]
    requested = requested_size(params, len(eligible))
    n = min(requested, len(eligible))
    draw = _Draw([], requested, len(eligible), high_value=0)
    if requested > len(eligible):
        draw.capped = True
        draw.notes.append(_note_103(requested, len(eligible)))
    if skipped:
        draw.notes.append(
            f"{skipped:,} rows have a zero or unreadable amount and cannot be selected."
        )
    if n == 0:
        return draw

    # Items at least as large as the interval are audited for certain.
    order = np.argsort(-a, kind="stable")  # largest first, ties by canonical order
    remaining_value, remaining_n = math.fsum(a.tolist()), n
    certain: list[int] = []
    for j in order[:n]:
        if a[j] >= remaining_value / remaining_n:
            certain.append(int(j))
            remaining_value -= float(a[j])
            remaining_n -= 1
        else:
            break
    picks = {j: "high_value" for j in certain}
    draw.high_value = len(certain)

    if remaining_n:
        rest_mask = np.ones(len(a), dtype=bool)
        rest_mask[certain] = False
        rest = np.flatnonzero(rest_mask)  # canonical order
        cumulative = np.cumsum(a[rest])
        draw.interval = float(cumulative[-1]) / remaining_n
        draw.start = SplitMix64(params.seed).unit() * draw.interval
        points = draw.start + np.arange(remaining_n) * draw.interval
        hits = np.minimum(
            np.searchsorted(cumulative, points, side="right"), len(rest) - 1
        )
        taken: set[int] = set()
        for hit in hits.tolist():
            # Float rounding at an interval boundary could repeat an item;
            # the next free item stands in so the sample keeps its size.
            while hit in taken:
                hit = (hit + 1) % len(rest)
            taken.add(hit)
            picks[int(rest[hit])] = "interval"

    chosen = sorted(picks)
    draw.positions = [int(eligible[j]) for j in chosen]
    draw.basis = [picks[j] for j in chosen]
    return draw


def _draw_stratified(params: SamplingParams, canon: pl.DataFrame) -> _Draw:
    amounts = _abs_amounts(canon)
    readable = np.isfinite(amounts)
    if len(amounts) and not readable.any():
        raise AuditConfigError(
            "TD-AUDIT-010",
            f"No row has a readable amount in '{params.amount_column}', so a "
            "value-based sample cannot be drawn.",
            field="amount_column",
            columns=(params.amount_column,),
        )
    edges = [float(e) for e in params.band_edges]
    count = len(edges) + 1
    stratum_of = np.zeros(len(amounts), dtype=np.int64)  # 0 = in no stratum
    stratum_of[readable] = (
        np.searchsorted(np.array(edges, dtype=np.float64), amounts[readable], "right")
        + 1
    )
    draw = _Draw([], 0, int(readable.sum()), strata=[])
    unreadable = len(amounts) - int(readable.sum())
    short: list[int] = []
    for s in range(1, count + 1):
        members = np.flatnonzero(stratum_of == s)
        asked = int(params.band_sizes[s - 1])
        want = len(members) if asked == ALL_SIZE else asked
        take = min(want, len(members))
        note = ""
        if want > len(members):
            note = _note_103(want, len(members))
            short.append(s)
        picked = floyd_positions(
            SplitMix64(derive_seed(params.seed, s - 1)), len(members), take
        )
        positions = [int(members[p]) for p in picked]
        draw.positions += positions
        draw.strata += [s] * len(positions)
        draw.requested += want
        draw.strata_rows.append(
            {
                "stratum": s,
                "population_rows": len(members),
                "population_value": _fsum(amounts[members]),
                "requested_size": want,
                "sample_size": len(positions),
                "sample_value": _fsum(amounts[positions]) if positions else 0.0,
                "lower_bound": edges[s - 2] if s > 1 else None,
                "upper_bound": edges[s - 1] if s <= len(edges) else None,
                "note": note,
            }
        )
    order = sorted(range(len(draw.positions)), key=draw.positions.__getitem__)
    draw.positions = [draw.positions[i] for i in order]
    draw.strata = [draw.strata[i] for i in order]
    if short:
        draw.capped = True
        which = ", ".join(str(s) for s in short)
        draw.notes.append(
            "TD-AUDIT-103: Some strata have fewer rows than requested "
            f"(stratum {which}); all their rows were selected."
        )
    if unreadable:
        draw.notes.append(
            f"{unreadable:,} rows have an unreadable amount and are in no stratum."
        )
    return draw


# ---- outputs ---------------------------------------------------------------
def _selection(canon: pl.DataFrame, draw: _Draw) -> pl.DataFrame:
    """One row per selected item: its input position and its sampling facts."""
    columns: dict[str, pl.Series] = {
        ROW: canon[ROW].gather(draw.positions)
        if draw.positions
        else pl.Series(ROW, [], pl.UInt32),
        SEQ: pl.Series(SEQ, [p + 1 for p in draw.positions], pl.Int64),
    }
    if draw.basis is not None:
        columns[BASIS] = pl.Series(BASIS, draw.basis, pl.String)
    if draw.strata is not None:
        columns[STRATUM] = pl.Series(STRATUM, draw.strata, pl.Int64)
    return pl.DataFrame(columns)


def _empty_selection(method: str) -> pl.DataFrame:
    columns = {ROW: pl.Series(ROW, [], pl.UInt32), SEQ: pl.Series(SEQ, [], pl.Int64)}
    if method == "mus":
        columns[BASIS] = pl.Series(BASIS, [], pl.String)
    if method == "stratified":
        columns[STRATUM] = pl.Series(STRATUM, [], pl.Int64)
    return pl.DataFrame(columns)


def _split(lf: pl.LazyFrame, originals: list[str], selection: pl.DataFrame):
    base = lf.with_row_index(ROW)
    extras = [c for c in selection.columns if c != ROW]
    sample = base.join(
        selection.lazy(), on=ROW, how="inner", maintain_order="left"
    ).select(originals + extras)
    not_sampled = base.join(
        selection.lazy().select(ROW), on=ROW, how="anti", maintain_order="left"
    ).select(originals)
    return sample, not_sampled


def _log_row(**values) -> dict:
    row = dict.fromkeys(LOG_COLUMNS)
    row.update(values)
    return row


def _log_frame(
    params: SamplingParams,
    keys: list[str],
    *,
    population: int,
    population_value: float | None,
    draw: _Draw | None,
    sample_value: float | None,
    note: str = "",
) -> pl.DataFrame:
    common = {
        "method": params.method,
        "seed": params.seed,
        "algorithm": ALGORITHM,
        "key_columns": ", ".join(keys) if keys else ALL_COLUMNS_TEXT,
        "amount_column": params.amount_column,
        "parameters": json_params(params.to_dict()),
    }
    rows = [
        _log_row(
            scope="overall",
            population_rows=population,
            population_value=population_value,
            requested_size=draw.requested if draw else 0,
            sample_size=len(draw.positions) if draw else 0,
            sample_value=sample_value,
            interval=draw.interval if draw else None,
            start=draw.start if draw else None,
            high_value_items=draw.high_value if draw else None,
            note=note,
            **common,
        )
    ]
    if draw is not None:
        rows += [
            _log_row(scope="stratum", **entry, **common) for entry in draw.strata_rows
        ]
    return pl.DataFrame(rows, schema=LOG_SCHEMA)


def _values(canon: pl.DataFrame, params: SamplingParams, draw: _Draw):
    """``(population_value, sample_value)``: gross |amount|, or None without a column."""
    if not params.amount_column:
        return None, None
    amounts = _abs_amounts(canon)
    readable = amounts[np.isfinite(amounts)]
    chosen = amounts[draw.positions] if draw.positions else amounts[:0]
    return _fsum(readable), _fsum(chosen[np.isfinite(chosen)])


def _count_up_to(lf: pl.LazyFrame, limit: int) -> int:
    """Rows of ``lf`` up to ``limit`` (reads no more than ``limit`` of them)."""
    return int(lf.head(limit).select(pl.len()).collect(engine="streaming").item())


def run_sample(frame, params: SamplingParams, *, live: bool = False) -> AuditResult:
    """Outputs: ``Sample``, ``Not sampled`` (both in input order) and the Selection log.

    ``live=True`` (the node's evaluation while editing) skips the draw for an
    input above ``LIVE_ROW_LIMIT`` rows and returns empty frames; Run never does.
    """
    lf = as_lazy(frame)
    schema = lf.collect_schema()
    keys = validate_params(params, schema)
    originals = list(schema)

    if live:
        seen = _count_up_to(lf, LIVE_ROW_LIMIT + 1)
        if seen > LIVE_ROW_LIMIT:
            if isinstance(frame, pl.DataFrame):
                text = f"Population has {frame.height:,} rows"
            else:
                text = f"Population has more than {LIVE_ROW_LIMIT:,} rows"
            message = f"{text}: the sample is drawn when you Run."
            sample, _all = _split(lf, originals, _empty_selection(params.method))
            not_sampled = lf.head(0)  # empty, like the sample: nothing was drawn
            log = _log_frame(
                params,
                keys,
                population=0,
                population_value=None,
                draw=None,
                sample_value=None,
                note=message,
            )
            return AuditResult(
                frames=(sample, not_sampled, log),
                log_index=2,
                extras={"log": log, "live_skipped": True, "message": message},
            )

    canon = canonical_order(lf, schema, keys, params.amount_column)
    n_rows = canon.height
    if params.method == "mus":
        draw = _draw_mus(params, canon)
    elif params.method == "stratified":
        draw = _draw_stratified(params, canon)
    else:
        draw = _draw_plain(params, n_rows)

    population_value, sample_value = _values(canon, params, draw)
    if params.amount_column and params.method in ("random", "systematic"):
        bad = n_rows - int(np.isfinite(_abs_amounts(canon)).sum())
        if bad:
            draw.notes.append(
                f"{bad:,} amounts could not be read and are left out of the values."
            )
    log = _log_frame(
        params,
        keys,
        population=n_rows,
        population_value=population_value,
        draw=draw,
        sample_value=sample_value,
        note=" ".join(draw.notes),
    )
    sample, not_sampled = _split(lf, originals, _selection(canon, draw))
    return AuditResult(
        frames=(sample, not_sampled, log),
        log_index=2,
        extras={"log": log, "live_skipped": False},
    )


# ---- TestSummary -----------------------------------------------------------
def criteria(params: SamplingParams, population_rows: int | None = None) -> str:
    """One sentence that says what was asked for."""
    method = params.method
    if method == "stratified":
        sizes = ", ".join(
            "all" if s == ALL_SIZE else f"{s:,}" for s in params.band_sizes
        )
        edges = ", ".join(f"{e:g}" for e in params.band_edges)
        what = f"stratified sample of {sizes} rows by |{params.amount_column}|"
        if edges:
            what += f" (edges {edges})"
    else:
        if params.size_kind == "percent":
            size = f"{params.sample_percent:g} % of the rows"
            if population_rows is not None:
                size += f" ({requested_size(params, population_rows):,} of {population_rows:,})"
        else:
            size = f"{int(params.sample_size):,} rows"
        what = f"{METHOD_TEXT[method]} sample of {size}"
        if method == "mus":
            what += f" weighted by |{params.amount_column}|"
    return f"{what[0].upper()}{what[1:]}, seed {params.seed}."


def sample_test_summary(
    log: pl.DataFrame,
    params: SamplingParams,
    *,
    node_id: int | None,
    sample_var: str | None,
) -> TestSummary:
    """The ``TestSummary`` of one draw, built from its Selection log."""
    overall = log.filter(pl.col("scope") == "overall").row(0, named=True)
    population = overall["population_rows"]
    n = overall["sample_size"]
    note = overall["note"] or ""
    return TestSummary(
        test_id=f"{OP}#{node_id}",
        test_name=TEST_NAME,
        node_id=node_id,
        status="pass",
        population_rows=population,
        exception_rows=n,
        exception_rate=(n / population) if population else None,
        criteria=criteria(params, population),
        parameters=params.to_dict(),
        message=(
            f"Selected {n:,} of {population:,} rows "
            f"({METHOD_TEXT[params.method]}, seed {params.seed})."
        ),
        exceptions_var=sample_var,
        population_value=overall["population_value"],
        exception_value=overall["sample_value"],
        code="TD-AUDIT-103" if note.startswith("TD-AUDIT-103") else None,
        details={
            "selection_log": log.to_dicts(),
            "seed": params.seed,
            "interval": overall["interval"],
            "start": overall["start"],
        },
    )
