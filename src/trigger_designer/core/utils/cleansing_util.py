import string
import re
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from typing import Optional, TYPE_CHECKING, Any, Dict, List, OrderedDict, Type, cast, Union


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
    Data cleansing class for pandas DataFrames.

    Example:
        >>> df = pd.DataFrame({
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

    def __init__(self, df: Optional[pd.DataFrame] = None):
        self.df = df.copy() if df is not None else pd.DataFrame()
        self.stats = CleansingStats()
        self._validate_input()

    def _validate_input(self) -> None:
        """Validate input DataFrame"""
        if not isinstance(self.df, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")

    def set_data(self, df: pd.DataFrame) -> 'DataCleansing':
        """Set the DataFrame to be cleaned"""
        self.df = df.copy()
        self._validate_input()
        return self

    def handle_nulls(self,
                     strategy: NullStrategy,
                     default_str: str = '',
                     default_num: Union[int, float] = 0) -> 'DataCleansing':
        """Handle null values according to specified strategy"""
        original_size = len(self.df)
        original_cols = len(self.df.columns)

        if strategy == NullStrategy.REMOVE_ALL_NULL_ROWS:
            self.df = self.df.dropna(how='all')
        elif strategy == NullStrategy.REMOVE_ANY_NULL_ROWS:
            self.df = self.df.dropna(how='any')
        elif strategy == NullStrategy.REMOVE_ALL_NULL_COLS:
            self.df = self.df.dropna(axis=1, how='all')
        elif strategy == NullStrategy.REMOVE_ANY_NULL_COLS:
            self.df = self.df.dropna(axis=1, how='any')
        elif strategy == NullStrategy.REPLACE_WITH_DEFAULT:
            # Replace nulls in numeric columns
            num_cols = self.df.select_dtypes(include=np.number).columns
            self.df[num_cols] = self.df[num_cols].fillna(default_num)

            # Replace nulls in string/object columns
            str_cols = self.df.select_dtypes(
                include=['object', 'string']).columns
            self.df[str_cols] = self.df[str_cols].fillna(default_str)

        self.stats.rows_removed += original_size - len(self.df)
        self.stats.columns_removed += original_cols - len(self.df.columns)

        return self

    def strip_whitespace(self,
                         remove_all: bool = False,
                         normalize_spaces: bool = True) -> 'DataCleansing':
        """Clean whitespace in string columns"""
        str_cols = self.df.select_dtypes(include=['object', 'string']).columns

        for col in str_cols:
            if remove_all:
                self.df[col] = self.df[col].str.replace(r'\s', '', regex=True)
            else:
                self.df[col] = self.df[col].str.strip()
                if normalize_spaces:
                    self.df[col] = self.df[col].str.replace(
                        r'\s+', ' ', regex=True)

            self.stats.whitespace_changes += self.df[col].notna().sum()

        return self

    def remove_characters(self,
                          remove_letters: bool = False,
                          remove_numbers: bool = False,
                          remove_punctuation: bool = False) -> 'DataCleansing':
        """Remove specified character types"""
        str_cols = self.df.select_dtypes(include=['object', 'string']).columns

        for col in str_cols:
            original = self.df[col].copy()
            if remove_letters:
                self.df[col] = self.df[col].str.replace(
                    r'[a-zA-Z]', '', regex=True)
            if remove_numbers:
                self.df[col] = self.df[col].str.replace(r'\d', '', regex=True)
            if remove_punctuation:
                self.df[col] = self.df[col].str.replace(
                    f'[{string.punctuation}]', '', regex=True)

            self.stats.character_removals += (original != self.df[col]).sum()

        return self

    def modify_case(self, case: str = 'upper') -> 'DataCleansing':
        """Modify string case"""
        str_cols = self.df.select_dtypes(include=['object', 'string']).columns

        for col in str_cols:
            original = self.df[col].copy()
            if case.lower() == 'upper':
                self.df[col] = self.df[col].str.upper()
            elif case.lower() == 'lower':
                self.df[col] = self.df[col].str.lower()
            elif case.lower() == 'title':
                self.df[col] = self.df[col].str.title()

            self.stats.case_changes += (original != self.df[col]).sum()

        return self

    def get_result(self) -> pd.DataFrame:
        """Get the cleansed DataFrame"""
        return self.df.copy()

    def get_stats(self) -> CleansingStats:
        """Get cleansing statistics"""
        return self.stats
