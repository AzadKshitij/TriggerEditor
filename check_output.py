import pandas as pd
var_file_input_2355067304640 = pd.read_csv('C:/Projects/TriggerEditor/check.csv')
import duckdb
duck= duckdb.connect(':memory:')
duck.register('df', var_file_input_2355067304640)
# Apply formula to create/update column Category
var_formula_2355067302480 = duck.execute('''SELECT *, CASE 
    WHEN Difficulty > 7 THEN 'High'
    WHEN Difficulty > 6 THEN 'Medium'
    ELSE 'Low'
END as Category FROM df''').fetchdf()
var_formula_2355067302480.to_csv('C:/Projects/TriggerEditor/savedfiles/out_check_W_formula.csv', index=False)
