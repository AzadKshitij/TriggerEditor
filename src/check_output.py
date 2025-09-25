import polars as pl
import os
import fastexcel
reader_2460071438256 = fastexcel.read_excel(
    'C:/Amer/T2 WIP/Outputs/Final Reports/Artifact6/20250904_Artifact 6 - Flag Review AVERY DENNISON.xlsx')
pandas_df_2460071438256 = reader_2460071438256.load_sheet(
    idx_or_name='6A_Action Flags (for T2)', header_row=0)
var_file_input_2460071438256 = pl.from_pandas(pandas_df_2460071438256)
