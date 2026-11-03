"""Read amounts the way an auditor means them (Qt-free, shared by Audit and Reconcile).

One parser for text amounts so a decimal comma means the same thing in every
node: ``1,50`` is 1.5, not 150. See ``amount_expr``.
"""

from __future__ import annotations

import polars as pl


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
