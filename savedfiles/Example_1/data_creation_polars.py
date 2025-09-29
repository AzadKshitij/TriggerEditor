import datetime
from faker import Faker
import polars as pl
import numpy as np
import random
import os

fake = Faker()
np.random.seed(42)

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# 1. Customers
customer_ids = range(1001, 1101)
customers = [{
    "customer_id": cid,
    "name": fake.name(),
    "age": random.randint(18, 70),
    "email": fake.email(),
    "region_id": random.randint(1, 5)
} for cid in customer_ids]
pl.DataFrame(customers).write_csv("data/customers.csv")

# 2. Products
products = [{
    "product_id": pid,
    "name": fake.word().capitalize(),
    "category": random.choice(["Electronics", "Books", "Home", "Fashion"]),
    "price": round(random.uniform(10, 500), 2)
} for pid in range(501, 551)]
pl.DataFrame(products).write_csv("data/products.csv")

# 3. Regions
regions = [
    {"region_id": 1, "region_name": "North"},
    {"region_id": 2, "region_name": "South"},
    {"region_id": 3, "region_name": "East"},
    {"region_id": 4, "region_name": "West"},
    {"region_id": 5, "region_name": "Central"},
]
pl.DataFrame(regions).write_csv("data/regions.csv")

# 4. Sales
# sales = []
# for _ in range(2000000):
#     sale = {
#         "order_id": fake.uuid4(),
#         "customer_id": random.choice(customer_ids),
#         "product_id": random.randint(501, 550),
#         "order_date": fake.date_between(start_date=datetime.date(2023, 1, 1), end_date='today'),
#         "order_value": round(random.uniform(20, 2000), 2),
#     }
#     sales.append(sale)
#     if _ % 100000 == 0:
#         print(f"Generated {_} sales records...")
# pl.DataFrame(sales).write_csv(
#     "data/monthly_sales_2023_2000000_polars.csv")


num_rows = 5_000_000
customer_ids = np.random.choice(np.arange(1001, 1101), num_rows)
product_ids = np.random.randint(501, 551, num_rows)
order_values = np.round(np.random.uniform(20, 2000, num_rows), 2)

# UUIDs: vectorized generation is not built-in; use list comprehension
order_ids = [fake.uuid4() for _ in range(num_rows)]

# Vectorized dates: Faker doesn't natively support, but you can randomize integers and convert.
start_date = np.datetime64('2023-01-01')
end_date = np.datetime64('2025-09-04')
order_dates = start_date + np.random.randint(
    0, (end_date - start_date).astype(int), num_rows
)
order_dates = order_dates.astype(str)  # Convert to string for CSV

sales_df = pl.DataFrame({
    "order_id": order_ids,
    "customer_id": customer_ids,
    "product_id": product_ids,
    "order_date": order_dates,
    "order_value": order_values
})

sales_df.write_csv("data/monthly_sales_2023_5000000_new.csv")
