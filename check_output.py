import pandas as pd
var_file_input_2898034804192 = pd.read_csv('C:/Projects/TriggerEditor/check.csv')
import pandas as pd
var_file_input_2898034806208 = pd.read_csv('C:/Projects/TriggerEditor/check_1.csv')
# Create rename maps for columns
_l_rename_map = {'Source_left': 'Source', 'Country_left': 'Country', 'Autocomplete Position_left': 'Autocomplete Position', 'Difficulty_left': 'Difficulty', 'Hot Keyword_left': 'Hot Keyword', 'Relevancy Score_left': 'Relevancy Score'}
_r_rename_map = {'Source_right': 'Source', 'Country_right': 'Country', 'Autocomplete Position_right': 'Autocomplete Position', 'Difficulty_right': 'Difficulty', 'Hot Keyword_right': 'Hot Keyword', 'Relevancy Score_right': 'Relevancy Score'}

# Perform merge operation
_merge_result = pd.merge(
    var_file_input_2898034804192,
    var_file_input_2898034806208,
    left_on=['Keyword', 'Seed'],
    right_on=['Keyword', 'Seed'],
    how='outer',
    suffixes=('_left', '_right'),
    indicator=True
)

# Main join result with selected columns
var_join_2898034807216 = _merge_result[_merge_result['_merge'] == 'both'][[
    'Difficulty_right',
    'Difficulty_left',
    'Seed',
    'Hot Keyword_left',
    'Source_right',
    'Relevancy Score_right',
    'Relevancy Score_left',
    'Keyword',
    'Country_left',
    'Hot Keyword_right',
    'Source_left',
    'Country_right'
]]

# Left-only data with original column names
_left_only = _merge_result[_merge_result['_merge'] == 'left_only'].rename(columns=_l_rename_map)
var_l_join_2898034807216 = _left_only[['Keyword', 'Seed', 'Source', 'Country', 'Autocomplete Position', 'Difficulty', 'Hot Keyword', 'Relevancy Score']]

# Right-only data with original column names
_right_only = _merge_result[_merge_result['_merge'] == 'right_only'].rename(columns=_r_rename_map)
var_r_join_2898034807216 = _right_only[['Keyword', 'Seed', 'Source', 'Country', 'Autocomplete Position', 'Difficulty', 'Hot Keyword', 'Relevancy Score']]

# Clean up temporary variables
del _merge_result, _left_only, _right_only, _l_rename_map, _r_rename_map
var_l_join_2898034807216.to_csv('C:/Projects/TriggerEditor/savedfiles/out_check_W_left-join.csv', index=False)
var_join_2898034807216.to_csv('C:/Projects/TriggerEditor/savedfiles/out_check_W_join.csv', index=False)
var_r_join_2898034807216.to_csv('C:/Projects/TriggerEditor/savedfiles/out_check_W_right-join.csv', index=False)
