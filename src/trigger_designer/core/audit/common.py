"""Qt-free building blocks shared by the five audit tests."""

from __future__ import annotations

import copy
import dataclasses
import json
import math
from dataclasses import dataclass, field
from typing import Any

import polars as pl

ROW = "__td_row"  # 0-based input position; internal columns all start with "__td_"
SUPPORTED_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y%m%d")

#: Size value that stands for "the whole stratum" in a typed size list.
ALL_SIZE = -1


class AuditConfigError(ValueError):
    """A configuration problem with a stable code.

    ``str(exc)`` always starts with ``"TD-AUDIT-nnn: "``; the error translator
    reads the code from there and the catalogue supplies the fix text.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        field: str = "",
        columns: tuple[str, ...] = (),
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.field = field
        self.columns = columns


@dataclass
class ParamsBase:
    """Settings of one audit test: plain JSON-friendly fields with defaults."""

    @classmethod
    def from_dict(cls, data: dict | None):
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(
            **{k: copy.deepcopy(v) for k, v in (data or {}).items() if k in known}
        )

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def default_of(f: dataclasses.Field) -> Any:
    if f.default_factory is not dataclasses.MISSING:
        return f.default_factory()
    return f.default


def params_schema(cls) -> dict:
    """``serialized_state_schema`` for ``SerializableContentMixin``."""
    return {
        f.name: {"default": copy.deepcopy(default_of(f))}
        for f in dataclasses.fields(cls)
    }


def as_lazy(frame) -> pl.LazyFrame:
    return frame.lazy() if isinstance(frame, pl.DataFrame) else frame


def json_params(params: dict) -> str:
    return json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)


def join_and(items: list[str]) -> str:
    items = [str(i) for i in items]
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---- typed list parsing (used by the dock; Qt-free so it is testable) ------
def parse_number_list(text: str) -> list[float]:
    """``"1000, 10000"`` -> ``[1000.0, 10000.0]``; empty text -> ``[]``.

    Raises ``ValueError`` for any bad token, including an empty one (a half
    typed ``"1000,"``), so the dock keeps the previous value while typing.
    """
    text = (text or "").strip()
    if not text:
        return []
    values: list[float] = []
    for token in text.split(","):
        value = float(token.strip())
        if not math.isfinite(value):
            raise ValueError(f"not a finite number: {token!r}")
        values.append(value)
    return values


def parse_size_list(text: str) -> list[int]:
    """``"20, 20, all"`` -> ``[20, 20, -1]``; empty text -> ``[]``."""
    text = (text or "").strip()
    if not text:
        return []
    sizes: list[int] = []
    for token in text.split(","):
        token = token.strip()
        if token.lower() == "all":
            sizes.append(ALL_SIZE)
            continue
        value = int(token)
        if value < 0:
            raise ValueError(f"size must be 0 or more: {token!r}")
        sizes.append(value)
    return sizes


# ---- validation helpers (each raises AuditConfigError) ---------------------
def is_nested(dtype) -> bool:
    return bool(dtype.is_nested()) or dtype == pl.Object


def need(
    schema: dict,
    field_name: str,
    value: str,
    label: str,
    *,
    nested_ok: bool = False,
) -> None:
    if not value:
        raise AuditConfigError(
            "TD-AUDIT-001", f"Choose the {label} column.", field=field_name
        )
    if value not in schema:
        raise AuditConfigError(
            "TD-AUDIT-002",
            f"Column '{value}' is not in the input data. Pick it again.",
            field=field_name,
            columns=(value,),
        )
    if not nested_ok and is_nested(schema[value]):
        raise AuditConfigError(
            "TD-AUDIT-003",
            f"Column '{value}' holds nested values and cannot be used for this test.",
            field=field_name,
            columns=(value,),
        )


def need_many(schema: dict, field_name: str, values: list[str], label: str) -> None:
    if not values:
        raise AuditConfigError(
            "TD-AUDIT-001", f"Choose the {label} column.", field=field_name
        )
    for v in values:
        need(schema, field_name, v, label)


def check_range(ok: bool, field_name: str, label: str, rule: str) -> None:
    if not ok:
        raise AuditConfigError(
            "TD-AUDIT-004", f"{label} must be {rule}.", field=field_name
        )


def check_date_format(fmt: str) -> None:
    if fmt not in SUPPORTED_DATE_FORMATS:
        raise AuditConfigError(
            "TD-AUDIT-007",
            f"Date format '{fmt}' is not supported. "
            f"Use one of: {', '.join(SUPPORTED_DATE_FORMATS)}.",
            field="date_format",
        )


def check_reserved(schema: dict, names: list[str]) -> None:
    for n in names:
        if n in schema:
            raise AuditConfigError(
                "TD-AUDIT-005",
                f"The input already has a column named '{n}', which this node adds. "
                "Rename it first.",
                field=n,
                columns=(n,),
            )


# ---- value expressions ------------------------------------------------------
def amount_expr(name: str, dtype: pl.DataType) -> pl.Expr:
    """Float64 or null. Text is cleaned: ' (1,234.50) ' -> -1234.5, '$5' -> 5.0.

    Text rules, applied after trimming, removing currency symbols, spaces and
    apostrophes (``1 234,50`` and ``1'234,50`` are group separators) and turning
    ``(x)`` into ``-x``:

    * both ``,`` and ``.``: the last one is the decimal mark. ``1,234.50`` is
      US/UK; ``1.234,50`` is European and must have exact groups of three.
    * only ``,``: exact groups of three (``1,234`` / ``1,234,567``, first group
      1-3 digits, no leading zero) are thousands, so ``1,234`` is 1234. Any
      other single comma is a decimal comma (``1234,5`` -> 1234.5,
      ``0,123`` -> 0.123). ``1,2,3`` is unreadable.
    * only ``.``: a decimal point; several dots (``1.234.567``) are unreadable.

    Anything else is null, so the caller's TD-AUDIT-102 warning fires instead of
    silently producing wrong digits.
    """
    col = pl.col(name)
    if dtype == pl.String:
        s = (
            col.str.strip_chars()
            .str.replace_all(r"[\s$£€'’]", "")
            .str.replace(r"^\((.*)\)$", "-$1")
        )
        # Almost every amount has no comma. Everything after this line works on
        # ``sc`` (null for those rows), so the regexes only see the rare rows and
        # the common case costs two cheap passes (see tests/benchmarks).
        has_c = s.str.contains(",", literal=True)
        sc = pl.when(has_c).then(s)
        has_d = sc.str.contains(".", literal=True)
        rev = sc.str.reverse()
        dot_last = rev.str.find(".", literal=True) < rev.str.find(",", literal=True)
        eu_ok = sc.str.contains(r"^-?\d{1,3}(\.\d{3})*,\d+$")
        thousands = sc.str.contains(r"^-?[1-9]\d{0,2}(,\d{3})+$")
        dec_comma = sc.str.contains(r"^-?\d+,\d+$")
        unreadable_text = pl.lit(None, dtype=pl.String)
        col = (
            pl.when(~has_c)
            .then(s)
            .when(has_d & dot_last)  # 1,234.50
            .then(sc.str.replace_all(",", "", literal=True))
            .when(has_d)  # 1.234,50
            .then(
                pl.when(eu_ok)
                .then(
                    sc.str.replace_all(".", "", literal=True).str.replace(
                        ",", ".", literal=True
                    )
                )
                .otherwise(unreadable_text)
            )
            .when(thousands)  # 1,234 / 1,234,567
            .then(sc.str.replace_all(",", "", literal=True))
            .when(dec_comma)  # 1234,5
            .then(sc.str.replace(",", ".", literal=True))
            .otherwise(unreadable_text)
        )
    return col.cast(pl.Float64, strict=False)


def date_expr(name: str, dtype: pl.DataType, fmt: str) -> pl.Expr:
    """Date or null.

    A Date is used as is; a Datetime becomes the calendar date in its own time
    zone; text is parsed with ``fmt`` and trailing time text is ignored
    (``'2024-03-02 14:05:00'`` -> 2024-03-02).
    """
    col = pl.col(name)
    if dtype == pl.Date:
        return col
    if dtype == pl.Datetime:
        return col.dt.date()
    txt = col if dtype == pl.String else col.cast(pl.String)
    return txt.str.strip_chars().str.to_date(fmt, strict=False, exact=False)


def key_expr(name: str, dtype: pl.DataType, trim: bool, ignore_case: bool) -> pl.Expr:
    c = pl.col(name) if dtype == pl.String else pl.col(name).cast(pl.String)
    if trim:
        c = c.str.strip_chars()
    if ignore_case:
        c = c.str.to_lowercase()
    return c


def unreadable(name: str, parsed: pl.Expr) -> pl.Expr:
    """True where the cell is present but could not be parsed."""
    return pl.col(name).is_not_null() & parsed.is_null()


# ---- results ----------------------------------------------------------------
@dataclass
class AuditResult:
    frames: tuple  # one entry per output socket, in socket order
    summary_index: int | None = None
    log_index: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)  # eager facts for the dock

    def for_run(self) -> tuple:
        """Frames for generated code.

        The one-row summary/log is collected NOW, so a broken plan fails during
        Run rather than later in a preview; big outputs stay lazy.
        """
        out = list(self.frames)
        for i in (self.summary_index, self.log_index):
            if i is not None and isinstance(out[i], pl.LazyFrame):
                out[i] = out[i].collect(engine="streaming")
        return tuple(out)


BASE_SUMMARY = (
    "test_name",
    "criteria",
    "parameters",
    "status",
    "code",
    "message",
    "population_rows",
    "population_value",
    "exception_rows",
    "exception_value",
    "exception_rate",
)


def summary_frame(
    agg: pl.LazyFrame,
    *,
    test_name: str,
    criteria: str,
    parameters: dict,
    status: pl.Expr,
    message: pl.Expr,
    code: pl.Expr | None = None,
    extras: tuple[str, ...] = (),
) -> pl.LazyFrame:
    """The one-row Summary every audit test with a Summary socket emits.

    ``agg`` is a one-row frame with ``population_rows``, ``population_value``,
    ``exception_rows``, ``exception_value`` and every column named in
    ``extras``. ``status``/``message``/``code`` are expressions on it.
    """
    return agg.select(
        pl.lit(test_name).alias("test_name"),
        pl.lit(criteria).alias("criteria"),
        pl.lit(json_params(parameters)).alias("parameters"),
        status.alias("status"),
        (code if code is not None else pl.lit(None, dtype=pl.String)).alias("code"),
        message.alias("message"),
        pl.col("population_rows"),
        pl.col("population_value"),
        pl.col("exception_rows"),
        pl.col("exception_value"),
        pl.when(pl.col("population_rows") > 0)
        .then(pl.col("exception_rows") / pl.col("population_rows"))
        .alias("exception_rate"),
        *[pl.col(c) for c in extras],
    )


def warn_unreadable(
    status: pl.Expr,
    message: pl.Expr,
    code: pl.Expr,
    unreadable_col: str,
    kind: str,
) -> tuple[pl.Expr, pl.Expr, pl.Expr]:
    """Downgrade pass -> warn and append the TD-AUDIT-102 note when values were skipped.

    Returns ``(status, message, code)`` expressions; ``code`` is never
    overwritten when already set and a ``fail`` stays a ``fail``.
    """
    bad = pl.col(unreadable_col)
    return (
        pl.when((bad > 0) & (status == "pass")).then(pl.lit("warn")).otherwise(status),
        message
        + pl.when(bad == 1)
        .then(pl.lit(" 1 value could not be read as " + kind + " and was skipped."))
        .when(bad > 1)
        .then(
            pl.format(
                " {} values could not be read as " + kind + " and were skipped.",
                bad,
            )
        )
        .otherwise(pl.lit("")),
        pl.when(code.is_not_null())
        .then(code)
        .when(bad > 0)
        .then(pl.lit("TD-AUDIT-102"))
        .otherwise(pl.lit(None, dtype=pl.String)),
    )
