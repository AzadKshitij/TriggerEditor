import pandas as pd
var_file_input_1972963160224 = pd.read_csv('C:/Projects/TriggerEditor/savedfiles/1. out_check.csv')
var_runtot_1972963161520 = var_file_input_1972963160224.copy()
var_runtot_1972963161520['RunTot_Autocomplete Position'] = var_runtot_1972963161520.groupby(['Keyword'])['Autocomplete Position'].cumsum()
# Create rename maps for columns
_l_rename_map = {'Keyword_left': 'Keyword', 'Seed_left': 'Seed', 'Source_left': 'Source', 'Country_left': 'Country', 'Autocomplete Position_left': 'Autocomplete Position', 'Difficulty_left': 'Difficulty', 'Hot Keyword_left': 'Hot Keyword', 'Relevancy Score_left': 'Relevancy Score'}
_r_rename_map = {'Keyword_right': 'Keyword', 'Seed_right': 'Seed', 'Source_right': 'Source', 'Country_right': 'Country', 'Autocomplete Position_right': 'Autocomplete Position', 'Difficulty_right': 'Difficulty', 'Hot Keyword_right': 'Hot Keyword', 'Relevancy Score_right': 'Relevancy Score'}

# Perform merge operation
_merge_result = pd.merge(
    var_file_input_1972963160224,
    var_file_input_1972963160224,
    left_on=['Unnamed: 0'],
    right_on=['Unnamed: 0'],
    how='outer',
    suffixes=('_left', '_right'),
    indicator=True
)

# Main join result with selected columns
var_1_1972963163104 = _merge_result[_merge_result['_merge'] == 'both'][[
    'Relevancy Score_left',
    'Hot Keyword_right',
    'Source_left',
    'Relevancy Score_right',
    'Seed_left',
    'Difficulty_left',
    'Autocomplete Position_right',
    'Country_right',
    'Keyword_right',
    'Unnamed: 0',
    'Hot Keyword_left',
    'Source_right',
    'Difficulty_right',
    'Country_left',
    'Autocomplete Position_left',
    'Seed_right',
    'Keyword_left'
]]

# Left-only data with original column names
_left_only = _merge_result[_merge_result['_merge'] == 'left_only'].rename(columns=_l_rename_map)
var_0_join_1972963163104 = _left_only[['Unnamed: 0', 'Keyword', 'Seed', 'Source', 'Country', 'Autocomplete Position', 'Difficulty', 'Hot Keyword', 'Relevancy Score']]

# Right-only data with original column names
_right_only = _merge_result[_merge_result['_merge'] == 'right_only'].rename(columns=_r_rename_map)
var_2_join_1972963163104 = _right_only[['Unnamed: 0', 'Keyword', 'Seed', 'Source', 'Country', 'Autocomplete Position', 'Difficulty', 'Hot Keyword', 'Relevancy Score']]

# Clean up temporary variables
del _merge_result, _left_only, _right_only, _l_rename_map, _r_rename_map
