import pandas as pd
var_file_input_2339921249472 = pd.read_csv('C:/Projects/TriggerEditor/check.csv')
import pandas as pd
var_file_input_2339921251488 = pd.read_csv('C:/Projects/TriggerEditor/check.csv')
var_join_2339921252496 = pd.merge(
    var_file_input_2339921249472,
    var_file_input_2339921251488,
    left_on=['Keyword', 'Seed'],
    right_on=['Keyword', 'Seed'],
    how='inner',
    suffixes=('_left', '_right')
)
