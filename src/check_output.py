import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2301039155856 = pl.scan_csv('C:/Amer/Product Engine/Inputs/20250924_BOM_Placement.csv', infer_schema=False)

# var_file_input_2301039155856 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_2301039160656 = var_file_input_2301039155856.select(['_id_', 'Collection', 'Season', 'LOM Assignment', 'Ams_SecondaryLOMAssignment_Ref', 'Current FG Supplier', 'Model #', 'arcModelGenericCodeSAP', 'Description', 'Sku Id', 'Product Line', 'Product Group', 'Product Type', 'ProductLineNew', 'ProductGroupNew', 'ProductAttribute', 'RM#', 'Product', 'Product Code', 'Product Description', 'Product Amer Material Type', 'Product Material Sub Type', 'amsConstruction', 'Product Status', 'Supplier Quote Price (src curr)', 'Supplier Quote Total Price (src curr)', 'Supplier Quote Amer Currency', 'Supplier Quote UOM (Sourcing)', 'Supplier Quote USD/M2', 'Placement Product Cut Width', 'Supplier Quote Supplier', 'Supplier Quote', 'Placement', 'Supplier Quote Is Current', 'BOM Revision Parent', 'BOMLineBOM', 'Placement Product Material Character', 'Tool Type', 'SysID', 'Supplier Quote Seasonal BOM Quote', 'Supplier Quote Seasonal Standard Cost', 'Model Forecast (Current)', 'Ams_TargetNoArticlesNew_Int', 'Ams_TargetNoArticles_Integer', 'Supplier Quote Order MOQ', 'Supplier Quote MCQ', 'Factory MOQ', 'Re-order MCQ', 'Re-order MOQ', 'Model Product Status', 'GenderNew', 'Model Gender', 'UOM (Inventory)', 'UOM Conversion', 'Supplier Quote Country of Origin', 'QuoteShippingPort', '__StyleColor', '__StyleSize', '__MaterialHidden', '__MaterialColor', '__MaterialSize', '__MaterialQuantity', '__MaterialQuote', '__MaterialUnitPrice', '__MaterialColorStatus', '__MaterialSizeSpec', '__MaterialStart', '__MaterialEnd', 'Global Purchaser', 'SAP Supplier Code', 'Greige Lead Time (days)', 'Dye & Finish Lead Time (days)', 'Greige MOQ', 'Manufacturing Lead Time (days)', 'Primary Activity', 'PrimaryActivityNew', 'Cut Qty', 'TAS Sized RM #', 'Size (Common)', 'IsCurrent', 'Product Authority BOM', 'Yield (Common)', 'Waste %', 'arcOnlyForProductAlternativesString', 'Default Colour', 'Sample MCQ', 'Color Card/DTM', 'Colour Notes', 'Material Season', 'Primary Season', 'CarryOver', 'amsGlobalPurchaser', 'Ams_ProductDeveloper', 'Ams_Colourist', 'Active', 'Ams_BOMStatus_enum', 'Ams_CopyCreated_Boolean', 'IsSampleBOM', 'ModelBaseSize', 'SupplierQuoteSeason', 'MajorRMCountryOrigin', 'FiberCountryOrigin', 'MaterialComposition', 'Composition', '_ExportedDate_', 'Id', 'RM#Cleaned', 'AltProducts#Cleaned', 'StyleSize#Cleaned', 'StyleSize#BaseDefault', 'StyleColor#Cleaned', 'IsActiveNonSampleNonCopy'])
import polars as pl
# Remove duplicates based on column: Season
var_unique_2301039158896 = var_select_2301039160656.unique(subset=["Season"])
# Ensure we're working with a LazyFrame for memory efficiency
if var_unique_2301039158896 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_unique_2301039158896, pl.DataFrame):
        var_unique_2301039158896_lazy = var_unique_2301039158896.lazy()
    elif isinstance(var_unique_2301039158896, pl.LazyFrame):
        var_unique_2301039158896_lazy = var_unique_2301039158896
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_unique_2301039158896)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_unique_2301039158896_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_Data_unique.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_Data_unique.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
