import pandas as pd
var_file_input_2628001385776 = pd.read_csv('C:/Projects/TriggerEditor/check.csv')
import duckdb
duck= duckdb.connect(':memory:')
duck.register('df', var_file_input_2628001385776)
# Apply formula to create/update column Category
var_formula_2628001383616 = duck.execute('''SELECT *, CASE 
    WHEN Difficulty > 7 THEN 'High'
    WHEN Difficulty > 6 THEN 'Medium'
    ELSE 'Low'
END as Category FROM df''').fetchdf()
var_formula_2628001383616.to_csv('C:/Projects/TriggerEditor/savedfiles/out_check_W_formula.csv', index=False)
