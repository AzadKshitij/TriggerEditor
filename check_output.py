import pandas as pd
var_file_input_3028048003280 = pd.read_csv('C:/Projects/TriggerEditor/check.csv')
# Filter data into true and false results
var_t_filter_3028048005296 = var_file_input_3028048003280[var_file_input_3028048003280['Difficulty'] >= 7]
var_f_filter_3028048005296 = var_file_input_3028048003280[~(var_file_input_3028048003280['Difficulty'] >= 7)]
var_t_filter_3028048005296.to_csv('C:/Projects/TriggerEditor/savedfiles/6. out_check_W_filter.csv', index=False)
var_f_filter_3028048005296.to_csv('C:/Projects/TriggerEditor/savedfiles/6.1. out_check_W_false-filter.csv', index=False)
