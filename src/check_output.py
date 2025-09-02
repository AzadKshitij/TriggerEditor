import pandas as pd
var_file_input_1534775814480 = pd.read_csv('C:/Projects/TriggerEditor/check.csv')
# Filter data into true and false results
var_t_filter_1534775816208 = var_file_input_1534775814480[var_file_input_1534775814480['Relevancy Score'] <= 95]
var_f_filter_1534775816208 = var_file_input_1534775814480[~(var_file_input_1534775814480['Relevancy Score'] <= 95)]
var_select_1533353663152 = var_file_input_1534775814480[['Keyword', 'Seed', 'Source', 'Country', 'Autocomplete Position', 'Difficulty', 'Hot Keyword', 'Relevancy Score']].copy()
var_select_1533353663152['Keyword'] = var_select_1533353663152['Keyword'].astype('object', errors='ignore')
var_select_1533353663152['Seed'] = var_select_1533353663152['Seed'].astype('object', errors='ignore')
var_select_1533353663152['Source'] = var_select_1533353663152['Source'].astype('object', errors='ignore')
var_select_1533353663152['Country'] = var_select_1533353663152['Country'].astype('object', errors='ignore')
var_select_1533353663152['Autocomplete Position'] = pd.to_numeric(var_select_1533353663152['Autocomplete Position'], errors='coerce')
var_select_1533353663152['Autocomplete Position'] = var_select_1533353663152['Autocomplete Position'].astype('float64', errors='ignore')
var_select_1533353663152['Difficulty'] = pd.to_numeric(var_select_1533353663152['Difficulty'], errors='coerce')
var_select_1533353663152['Difficulty'] = var_select_1533353663152['Difficulty'].astype('int64', errors='ignore')
var_select_1533353663152['Hot Keyword'] = var_select_1533353663152['Hot Keyword'].astype('object', errors='ignore')
var_select_1533353663152['Relevancy Score'] = pd.to_numeric(var_select_1533353663152['Relevancy Score'], errors='coerce')
var_select_1533353663152['Relevancy Score'] = var_select_1533353663152['Relevancy Score'].astype('float64', errors='ignore')
var_select_1533353663152.rename(columns={'Autocomplete Position': 'Aut'}, inplace=True)
