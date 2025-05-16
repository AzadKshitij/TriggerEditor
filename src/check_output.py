import pandas as pd
from trigger_designer.core.utils.cleansing_util import DataCleansing, CleansingStats, NullStrategy
var_file_input_2192003776176 = pd.read_csv(
    'C:/Projects/TriggerEditor/check_1.csv')
cleaner = DataCleansing(var_file_input_2192003776176)
cleaner.handle_nulls(NullStrategy.REMOVE_ANY_NULL_ROWS)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True)
var_cleansing_2192003875600 = cleaner.get_result()
var_cleansing_2192003875600.to_csv(
    'C:/Projects/TriggerEditor/check_1_cleansed.csv', index=False)
