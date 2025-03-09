import pandas as pd
var_file_input_1853975185008 = pd.read_csv(
    'C:/Projects/TriggerEditor/check.csv')

var_sort_1853975187168 = var_file_input_1853975185008.sort_values(
    by=['Difficulty', 'Relevancy Score'], ascending=[True, True])

var_sort_1853975187168.to_csv(
    'C:/Projects/TriggerEditor/savedfiles/7. out_check_W_sort.csv', index=False)
