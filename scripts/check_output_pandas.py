import duckdb
import pandas as pd

var_file_input_1837005836720 = pd.read_csv(
    "C:/Projects/TriggerEditor/examples/BL-Flickr-Images-Book.csv"
)
var_select_1837005840320 = var_file_input_1837005836720[
    [
        "Identifier",
        "Place of Publication",
        "Date of Publication",
        "Publisher",
        "Title",
        "Author",
        "Flickr URL",
    ]
].copy()
var_select_1837005840320["Identifier"] = pd.to_numeric(
    var_select_1837005840320["Identifier"], errors="coerce"
)
var_select_1837005840320["Identifier"] = var_select_1837005840320["Identifier"].astype(
    "int64", errors="ignore"
)
var_select_1837005840320["Place of Publication"] = var_select_1837005840320[
    "Place of Publication"
].astype("object", errors="ignore")
var_select_1837005840320["Date of Publication"] = var_select_1837005840320[
    "Date of Publication"
].astype("object", errors="ignore")
var_select_1837005840320["Publisher"] = var_select_1837005840320["Publisher"].astype(
    "object", errors="ignore"
)
var_select_1837005840320["Title"] = var_select_1837005840320["Title"].astype(
    "object", errors="ignore"
)
var_select_1837005840320["Author"] = var_select_1837005840320["Author"].astype(
    "object", errors="ignore"
)
var_select_1837005840320["Flickr URL"] = var_select_1837005840320["Flickr URL"].astype(
    "object", errors="ignore"
)

duck = duckdb.connect(":memory:")
duck.register("df", var_select_1837005840320)
# save original columns
original_columns = var_select_1837005840320.columns
# Apply formula to create/update column
var_formula_1837005841472 = duck.execute("""SELECT *, CASE 
WHEN "Place of Publication" LIKE '%London%' THEN 'London' 
WHEN "Place of Publication" LIKE '%Oxford%' THEN 'Oxford' 
ELSE REPLACE("Place of Publication", '-', ' ') 
END as "Place of Publication" FROM df""").fetchdf()

# Restore original columns
new_columns = var_formula_1837005841472.columns
new_column_name = list(set(new_columns) - set(original_columns))[0]
# Rename it to the original column name
var_formula_1837005841472["Place of Publication"] = var_formula_1837005841472[
    new_column_name
]
var_formula_1837005841472.to_csv(
    "C:/Projects/TriggerEditor/examples/Updated-wWorkflow-BL-Flickr-Images-Book.csv",
    index=False,
)
