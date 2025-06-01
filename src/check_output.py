import pandas as pd
var_file_input_1987364886928 = pd.read_csv('C:/Projects/TriggerEditor/savedfiles/1. out_check.csv')
# Generate rows
values = []
current = 1
while current <= 50:
    values.append(current)
    current = current + 2

var_genrows_1987364888224 = pd.DataFrame({'counter': values})
var_genrows_1987364888224 = pd.concat([var_file_input_1987364886928, var_genrows_1987364888224], axis=1)
