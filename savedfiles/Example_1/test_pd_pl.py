import polars as pl
import pandas as pd
import time

start = time.time()
sales = pd.read_csv('data/monthly_sales_2023_5000000.csv')
customers = pd.read_csv('data/customers.csv')
regions = pd.read_csv('data/regions.csv')
products = pd.read_csv('data/products.csv')

# Chain transforms (basic chaining)
df = (sales
      .merge(customers, on="customer_id", how="left")
      .merge(regions, on="region_id", how="left")
      .merge(products, on="product_id", how="left")
      )
# Add total price after discount, filter, and aggregate
df["total_after_discount"] = df["order_value"] * 0.9
df = df[df["total_after_discount"] > 500]
result = df.groupby("region_name")["total_after_discount"].mean().reset_index()

end = time.time()
print("Pandas chained time:", end - start)


start = time.time()
sales = pl.scan_csv('data/monthly_sales_2023_5000000.csv')
customers = pl.scan_csv('data/customers.csv')
regions = pl.scan_csv('data/regions.csv')
products = pl.scan_csv('data/products.csv')

# Chained transforms in lazy mode
result = (sales
          .join(customers, on="customer_id")
          .join(regions, on="region_id")
          .join(products, on="product_id")
          .with_columns([
              (pl.col("order_value") * 0.9).alias("total_after_discount")
          ])
          .filter(pl.col("total_after_discount") > 500)
          .group_by("region_name")
          .agg(pl.col("total_after_discount").mean())
          .collect()
          )

end = time.time()
print("Polars chained time:", end - start)

'''
Pandas chained time: 11.800550699234009
Polars chained time: 0.7993500232696533
'''
