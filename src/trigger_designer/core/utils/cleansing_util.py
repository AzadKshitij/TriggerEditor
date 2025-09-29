import string
import re
from dataclasses import dataclass
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


@dataclass
class CleansingStats:
    """Statistics for tracking cleansing operations"""

    rows_removed: int = 0
    columns_removed: int = 0
    nulls_replaced: int = 0
    whitespace_changes: int = 0
    case_changes: int = 0
    character_removals: int = 0


class NullStrategy(Enum):
    """Enum for null handling strategies"""

    REMOVE_ALL_NULL_ROWS = "remove_all_null_rows"
    REMOVE_ANY_NULL_ROWS = "remove_any_null_rows"
    REMOVE_ALL_NULL_COLS = "remove_all_null_cols"
    REMOVE_ANY_NULL_COLS = "remove_any_null_cols"
    REPLACE_WITH_DEFAULT = "replace_with_default"


class DataCleansing:
    """
    Data cleansing class for Polars DataFrames.

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

    def __init__(self, df: Optional[pl.DataFrame] = None):
        self.df = df.clone() if df is not None else pl.DataFrame()
        self.stats = CleansingStats()
        self._validate_input()

    def _validate_input(self) -> None:
        """Validate input DataFrame"""
        if not isinstance(self.df, pl.DataFrame):
            raise TypeError("Input must be a Polars DataFrame")

    def set_data(self, df: pl.DataFrame) -> "DataCleansing":
        """Set the DataFrame to be cleaned"""
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
        original_size = len(self.df)
        original_cols = len(self.df.columns)
        original_nulls = self.df.null_count().sum_horizontal().item()

        if strategy == NullStrategy.REMOVE_ALL_NULL_ROWS:
            # Remove rows where all values are null
            self.df = self.df.filter(~pl.all_horizontal(pl.all().is_null()))
        elif strategy == NullStrategy.REMOVE_ANY_NULL_ROWS:
            # Remove rows where any value is null
            self.df = self.df.filter(~pl.any_horizontal(pl.all().is_null()))
        elif strategy == NullStrategy.REMOVE_ALL_NULL_COLS:
            # Remove columns where all values are null
            cols_to_keep = []
            for col in self.df.columns:
                if not self.df.select(pl.col(col).is_null().all()).item():
                    cols_to_keep.append(col)
            self.df = self.df.select(cols_to_keep)
        elif strategy == NullStrategy.REMOVE_ANY_NULL_COLS:
            # Remove columns where any value is null
            cols_to_keep = []
            for col in self.df.columns:
                if not self.df.select(pl.col(col).is_null().any()).item():
                    cols_to_keep.append(col)
            self.df = self.df.select(cols_to_keep)
        elif strategy == NullStrategy.REPLACE_WITH_DEFAULT:
            # Replace nulls based on column data types
            expressions = []
            for col in self.df.columns:
                dtype = self.df.select(pl.col(col)).dtypes[0]
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

            # Count nulls replaced
            current_nulls = self.df.null_count().sum_horizontal().item()
            self.stats.nulls_replaced += original_nulls - current_nulls

        self.stats.rows_removed += original_size - len(self.df)
        self.stats.columns_removed += original_cols - len(self.df.columns)

        return self

    def strip_whitespace(
        self,
        remove_all: bool = False,
        normalize_spaces: bool = True,
        fields: Optional[List[str]] = None,
    ) -> "DataCleansing":
        """Clean whitespace in string columns"""
        # Get string columns
        str_cols = []
        for col in self.df.columns:
            dtype = self.df.select(pl.col(col)).dtypes[0]
            if dtype in [pl.Utf8, pl.String]:
                str_cols.append(col)

        # Filter to selected fields if specified
        if fields is not None:
            str_cols = [col for col in str_cols if col in fields]

        expressions = []
        for col in self.df.columns:
            if col in str_cols:
                if remove_all:
                    # Remove all whitespace
                    expr = pl.col(col).str.replace_all(r"\s", "")
                else:
                    # Strip leading/trailing whitespace
                    expr = pl.col(col).str.strip_chars()
                    if normalize_spaces:
                        # Replace multiple spaces with single space
                        expr = expr.str.replace_all(r"\s+", " ")
                expressions.append(expr.alias(col))
                # Count changes (approximate)
                self.stats.whitespace_changes += len(self.df)
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
        str_cols = []
        for col in self.df.columns:
            dtype = self.df.select(pl.col(col)).dtypes[0]
            if dtype in [pl.Utf8, pl.String]:
                str_cols.append(col)

        # Filter to selected fields if specified
        if fields is not None:
            str_cols = [col for col in str_cols if col in fields]

        expressions = []
        for col in self.df.columns:
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
                # Count changes (approximate)
                self.stats.character_removals += len(self.df)
            else:
                expressions.append(pl.col(col))

        self.df = self.df.with_columns(expressions)
        return self

    def modify_case(
        self, case: str = "upper", fields: Optional[List[str]] = None
    ) -> "DataCleansing":
        """Modify string case"""
        # Get string columns
        str_cols = []
        for col in self.df.columns:
            dtype = self.df.select(pl.col(col)).dtypes[0]
            if dtype in [pl.Utf8, pl.String]:
                str_cols.append(col)

        # Filter to selected fields if specified
        if fields is not None:
            str_cols = [col for col in str_cols if col in fields]

        expressions = []
        for col in self.df.columns:
            if col in str_cols:
                expr = pl.col(col)
                if case.lower() == "upper":
                    expr = expr.str.to_uppercase()
                elif case.lower() == "lower":
                    expr = expr.str.to_lowercase()
                elif case.lower() == "title":
                    expr = expr.str.to_titlecase()

                expressions.append(expr.alias(col))
                # Count changes (approximate)
                self.stats.case_changes += len(self.df)
            else:
                expressions.append(pl.col(col))

        self.df = self.df.with_columns(expressions)
        return self

    def get_result(self) -> pl.DataFrame:
        """Get the cleansed DataFrame"""
        return self.df.clone()

    def get_stats(self) -> CleansingStats:
        """Get cleansing statistics"""
        return self.stats
