import string
import re
from enum import Enum
import polars as pl
from typing import (
    Optional,
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    OrderedDict,
    Type,
    cast,
    Union,
)

from trigger_designer.core.shaping.common import Frame, ShapingError, schema_of


class NullStrategy(Enum):
    """Enum for null handling strategies"""

    REMOVE_ALL_NULL_ROWS = "remove_all_null_rows"
    REMOVE_ANY_NULL_ROWS = "remove_any_null_rows"
    REMOVE_ALL_NULL_COLS = "remove_all_null_cols"
    REMOVE_ANY_NULL_COLS = "remove_any_null_cols"
    REPLACE_WITH_DEFAULT = "replace_with_default"


class DataCleansing:
    """
    Data cleansing class for Polars DataFrames and LazyFrames.

    A LazyFrame stays lazy: nothing is read until the result is collected, except
    the one-row summary that the REMOVE_ALL_NULL_COLS and REMOVE_ANY_NULL_COLS
    strategies need to pick the columns to keep. The result is the same kind as
    the input.

    Example:
        >>> df = pl.DataFrame({
        ...     'A': ['  Hello  ', 'World!', None],
        ...     'B': [1, None, 3],
        ...     'C': [None, None, None]
        ... })
        >>> cleaner = DataCleansing(df)
        >>> cleaned_df = (cleaner
        ...     .handle_nulls(NullStrategy.REMOVE_ALL_NULL_COLS)
        ...     .strip_whitespace()
        ...     .to_uppercase()
        ...     .get_result())
    """

    def __init__(self, df: Optional[Frame] = None):
        self.df = df.clone() if df is not None else pl.DataFrame()
        self._validate_input()

    def _validate_input(self) -> None:
        """Validate input: a DataFrame or a LazyFrame"""
        if not isinstance(self.df, (pl.DataFrame, pl.LazyFrame)):
            raise TypeError("Input must be a Polars DataFrame or LazyFrame")

    def set_data(self, df: Frame) -> "DataCleansing":
        """Set the frame to be cleaned"""
        self.df = df.clone()
        self._validate_input()
        return self

    def handle_nulls(
        self,
        strategy: NullStrategy,
        default_str: str = "",
        default_num: Union[int, float] = 0,
    ) -> "DataCleansing":
        """Handle null values according to specified strategy"""
        if strategy == NullStrategy.REMOVE_ALL_NULL_ROWS:
            # Remove rows where all values are null
            self.df = self.df.filter(~pl.all_horizontal(pl.all().is_null()))
        elif strategy == NullStrategy.REMOVE_ANY_NULL_ROWS:
            # Remove rows where any value is null
            self.df = self.df.filter(~pl.any_horizontal(pl.all().is_null()))
        elif strategy == NullStrategy.REMOVE_ALL_NULL_COLS:
            # Which columns survive depends on the data, so this one-row summary
            # is collected here. Every other step stays a lazy expression.
            summary = self.df.select(pl.all().is_null().all())
            if isinstance(summary, pl.LazyFrame):
                summary = summary.collect()
            null_mask = summary.row(0)
            cols_to_keep = [
                c for c, all_null in zip(schema_of(self.df), null_mask) if not all_null
            ]
            if not cols_to_keep:
                raise ShapingError(
                    "TD-SHAPE-005",
                    "Every column is empty; keep at least one column or turn off "
                    "Remove all-null columns",
                )
            self.df = self.df.select(cols_to_keep)
        elif strategy == NullStrategy.REMOVE_ANY_NULL_COLS:
            # Same one-row summary, for "any null".
            summary = self.df.select(pl.all().is_null().any())
            if isinstance(summary, pl.LazyFrame):
                summary = summary.collect()
            null_mask = summary.row(0)
            cols_to_keep = [
                c for c, any_null in zip(schema_of(self.df), null_mask) if not any_null
            ]
            if not cols_to_keep:
                raise ShapingError(
                    "TD-SHAPE-005",
                    "Every column has a null value; keep at least one column or "
                    "turn off Remove columns with any null",
                )
            self.df = self.df.select(cols_to_keep)
        elif strategy == NullStrategy.REPLACE_WITH_DEFAULT:
            # Replace nulls based on column data types
            expressions = []
            for col, dtype in schema_of(self.df).items():
                if dtype in [
                    pl.Int8,
                    pl.Int16,
                    pl.Int32,
                    pl.Int64,
                    pl.UInt8,
                    pl.UInt16,
                    pl.UInt32,
                    pl.UInt64,
                    pl.Float32,
                    pl.Float64,
                ]:
                    expressions.append(pl.col(col).fill_null(default_num))
                else:
                    expressions.append(pl.col(col).fill_null(default_str))

            self.df = self.df.with_columns(expressions)

        return self

    def remove_rows_with_nulls(
        self, fields: Optional[List[str]] = None
    ) -> "DataCleansing":
        """Remove rows where any selected field is null."""
        if not fields:
            return self

        names = list(schema_of(self.df))
        selected_fields = [field for field in fields if field in names]
        if not selected_fields:
            return self

        null_checks = [pl.col(field).is_null() for field in selected_fields]
        self.df = self.df.filter(~pl.any_horizontal(*null_checks))
        return self

    def replace_null_defaults(
        self,
        replace_strings: bool = True,
        replace_numbers: bool = True,
        default_str: str = "",
        default_num: Union[int, float] = 0,
    ) -> "DataCleansing":
        """Replace nulls for string and numeric columns independently."""
        if not replace_strings and not replace_numbers:
            return self

        numeric_dtypes = {
            pl.Int8,
            pl.Int16,
            pl.Int32,
            pl.Int64,
            pl.UInt8,
            pl.UInt16,
            pl.UInt32,
            pl.UInt64,
            pl.Float32,
            pl.Float64,
        }
        string_dtypes = {pl.Utf8, pl.String}

        expressions = []
        for column_name, dtype in schema_of(self.df).items():
            expr = pl.col(column_name)
            if replace_numbers and dtype in numeric_dtypes:
                expr = expr.fill_null(default_num)
            elif replace_strings and dtype in string_dtypes:
                expr = expr.fill_null(default_str)
            expressions.append(expr.alias(column_name))

        if expressions:
            self.df = self.df.with_columns(expressions)

        return self

    def strip_whitespace(
        self,
        remove_all: bool = False,
        normalize_spaces: bool = True,
        fields: Optional[List[str]] = None,
        trim: bool = True,
    ) -> "DataCleansing":
        """Clean whitespace in string columns.

        ``trim`` removes the spaces at both ends; ``normalize_spaces`` turns
        runs of whitespace into one space without touching the ends.
        """
        # Get string columns
        schema = schema_of(self.df)
        str_cols = []
        for col, dtype in schema.items():
            if dtype in [pl.Utf8, pl.String]:
                str_cols.append(col)

        # Filter to selected fields if specified
        if fields is not None:
            str_cols = [col for col in str_cols if col in fields]

        expressions = []
        for col in schema:
            if col in str_cols:
                if remove_all:
                    # Remove all whitespace
                    expr = pl.col(col).str.replace_all(r"\s", "")
                else:
                    # Strip leading/trailing whitespace
                    expr = pl.col(col)
                    if trim:
                        expr = expr.str.strip_chars()
                    if normalize_spaces:
                        # Replace multiple spaces with single space
                        expr = expr.str.replace_all(r"\s+", " ")
                expressions.append(expr.alias(col))
            else:
                expressions.append(pl.col(col))

        self.df = self.df.with_columns(expressions)
        return self

    def remove_characters(
        self,
        remove_letters: bool = False,
        remove_numbers: bool = False,
        remove_punctuation: bool = False,
        fields: Optional[List[str]] = None,
    ) -> "DataCleansing":
        """Remove specified character types"""
        # Get string columns
        schema = schema_of(self.df)
        str_cols = []
        for col, dtype in schema.items():
            if dtype in [pl.Utf8, pl.String]:
                str_cols.append(col)

        # Filter to selected fields if specified
        if fields is not None:
            str_cols = [col for col in str_cols if col in fields]

        expressions = []
        for col in schema:
            if col in str_cols:
                expr = pl.col(col)

                if remove_letters:
                    # Remove all letters including non-Latin alphabet letters
                    expr = expr.str.replace_all(r"[a-zA-ZÀ-ÿĀ-žА-я]", "")
                if remove_numbers:
                    expr = expr.str.replace_all(r"\d", "")
                if remove_punctuation:
                    # Use the exact punctuation characters specified in requirements
                    punctuation_chars = "!\"#$%&'()*+,\\-./:;<=>?@[/]^_`{|}~"
                    expr = expr.str.replace_all(f"[{re.escape(punctuation_chars)}]", "")

                expressions.append(expr.alias(col))
            else:
                expressions.append(pl.col(col))

        self.df = self.df.with_columns(expressions)
        return self

    def modify_case(
        self, case: str = "upper", fields: Optional[List[str]] = None
    ) -> "DataCleansing":
        """Modify string case"""
        # Get string columns
        schema = schema_of(self.df)
        str_cols = []
        for col, dtype in schema.items():
            if dtype in [pl.Utf8, pl.String]:
                str_cols.append(col)

        # Filter to selected fields if specified
        if fields is not None:
            str_cols = [col for col in str_cols if col in fields]

        expressions = []
        for col in schema:
            if col in str_cols:
                expr = pl.col(col)
                if case.lower() == "upper":
                    expr = expr.str.to_uppercase()
                elif case.lower() == "lower":
                    expr = expr.str.to_lowercase()
                elif case.lower() == "title":
                    expr = expr.str.to_titlecase()

                expressions.append(expr.alias(col))
            else:
                expressions.append(pl.col(col))

        self.df = self.df.with_columns(expressions)
        return self

    def get_result(self) -> Frame:
        """Get the cleansed frame (same kind as the input)"""
        return self.df.clone()
