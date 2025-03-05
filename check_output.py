import pandas as pd
var_file_input_2062101477648 = pd.read_csv('C:/Projects/TriggerEditor/check.csv')
import pandas as pd
var_file_input_2062101528928 = pd.read_csv('C:/Projects/TriggerEditor/check_1.csv')
var_join_2062101529936 = pd.merge(
    var_file_input_2062101477648,
    var_file_input_2062101528928,
    left_on=['Keyword', 'Seed'],
    right_on=['Keyword', 'Seed'],
    how='inner',
    suffixes=('_left', '_right')
)

# Select specific columns
var_join_2062101529936 = var_join_2062101529936[[
    'Country_left',
    'Difficulty_left',
    'Hot Keyword_left',
    'Keyword',
    'Relevancy Score_left',
    'Seed',
    'Source_left',
    'Country_right',
    'Difficulty_right',
    'Hot Keyword_right',
    'Keyword',
    'Relevancy Score_right',
    'Seed',
    'Source_right'
]]var_file_input_2062101477648.to_csv('C:/Projects/TriggerEditor/savedfiles/out_check_W_left-join.csv', index=False)
var_join_2062101529936.to_csv('C:/Projects/TriggerEditor/savedfiles/out_check_W_join.csv', index=False)
var_file_input_2062101528928.to_csv('C:/Projects/TriggerEditor/savedfiles/out_check_W_right-join.csv', index=False)
