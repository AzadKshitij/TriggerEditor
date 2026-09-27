"""Canonical dtype normalisation for node outputs.

The Select node's dtype dropdown is the application's supported type list::

    String, Int64, Float64, Boolean, Date, Datetime, List, Struct,
    Categorical, Binary, Decimal, Duration

Polars aggregations routinely emit narrower types outside that list
(``pl.len()`` and ``n_unique`` return ``UInt32``; ``sum``/``mean`` preserve a
narrow input width such as ``UInt32`` or ``Float32``). Downstream nodes then
show a dtype no dropdown offers. This module is the single place that maps
every Polars dtype back into the supported set, so live execution and
generated code cannot drift apart:

- all signed/unsigned ints narrower than 64 bit -> ``Int64``
- ``Float32`` -> ``Float64``
- ``Time`` -> ``String`` (Select has no Time entry)
- ``Enum`` -> ``Categorical``
- ``Array`` -> ``List``
- ``Null`` / ``Unknown`` -> ``String``
- ``Object`` has no representable equivalent and is left untouched
"""

import polars as pl

#: Widening map: exact Polars dtype -> supported Polars dtype.
#: Compared against ``dtype.base_type()`` so parametrised types
#: (``Datetime('ms')``, ``List(Int32)``, ...) match their generic form.
NARROW_TO_WIDE: dict[pl.DataType, pl.DataType] = {
    pl.Int8: pl.Int64,
    pl.Int16: pl.Int64,
    pl.Int32: pl.Int64,
    pl.UInt8: pl.Int64,
    pl.UInt16: pl.Int64,
    pl.UInt32: pl.Int64,
    pl.UInt64: pl.Int64,
    pl.Float32: pl.Float64,
    pl.Time: pl.String,
    pl.Enum: pl.Categorical,
    pl.Array: pl.List,
    pl.Null: pl.String,
    pl.Unknown: pl.String,
}

#: Base dtypes the Select dropdown can represent. Anything not in here and
#: not in ``NARROW_TO_WIDE`` is left alone (currently only ``Object``).
SUPPORTED_BASE_DTYPES = frozenset(
    {
        pl.String,
        pl.Int64,
        pl.Float64,
        pl.Boolean,
        pl.Date,
        pl.Datetime,
        pl.List,
        pl.Struct,
        pl.Categorical,
        pl.Binary,
        pl.Decimal,
        pl.Duration,
    }
)


def _frame_schema(frame: pl.DataFrame | pl.LazyFrame) -> pl.Schema:
    """Schema access that works on eager and lazy frames."""
    if isinstance(frame, pl.LazyFrame):
        return frame.collect_schema()
    if isinstance(frame, pl.DataFrame):
        return frame.schema
    return pl.Schema()


def normalization_casts(
    frame: pl.DataFrame | pl.LazyFrame,
) -> list[pl.Expr]:
    """Build the cast expressions that pull ``frame`` into supported dtypes.

    Pure (no I/O, no logging): safe to call from live paths, codegen, and
    tests. Returns an empty list when nothing needs normalising.
    """
    casts: list[pl.Expr] = []
    for name, dtype in _frame_schema(frame).items():
        base_fn = getattr(dtype, "base_type", None)
        if base_fn is None:
            continue
        base = base_fn()
        if base in SUPPORTED_BASE_DTYPES:
            continue
        target = NARROW_TO_WIDE.get(base)
        if target is None:
            continue
        casts.append(pl.col(name).cast(target, strict=False).alias(name))
    return casts


def normalize_to_supported_dtypes(
    frame: pl.DataFrame | pl.LazyFrame,
) -> pl.DataFrame | pl.LazyFrame:
    """Return ``frame`` with every column cast into a Select-supported dtype.

    Works on eager and lazy frames; ``with_columns`` preserves whichever kind
    it receives. A frame needing no normalisation is returned unchanged. Uses
    ``strict=False`` so an uncastable value becomes null instead of failing
    the whole node, matching the Select node's conversion contract.
    """
    casts = normalization_casts(frame)
    if not casts:
        return frame
    return frame.with_columns(casts)
