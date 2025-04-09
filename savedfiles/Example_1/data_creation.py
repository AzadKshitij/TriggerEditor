import datetime
from faker import Faker
import pandas as pd
import numpy as np
import random

fake = Faker()
np.random.seed(42)

# 1. Customers
customer_ids = range(1001, 1101)
customers = [{
    "customer_id": cid,
    "name": fake.name(),
    "age": random.randint(18, 70),
    "email": fake.email(),
    "region_id": random.randint(1, 5)
} for cid in customer_ids]
pd.DataFrame(customers).to_csv("data/customers.csv", index=False)

# 2. Products
products = [{
    "product_id": pid,
    "name": fake.word().capitalize(),
    "category": random.choice(["Electronics", "Books", "Home", "Fashion"]),
    "price": round(random.uniform(10, 500), 2)
} for pid in range(501, 551)]
pd.DataFrame(products).to_csv("data/products.csv", index=False)

# 3. Regions
regions = [
    {"region_id": 1, "region_name": "North"},
    {"region_id": 2, "region_name": "South"},
    {"region_id": 3, "region_name": "East"},
    {"region_id": 4, "region_name": "West"},
    {"region_id": 5, "region_name": "Central"},
]
pd.DataFrame(regions).to_csv("data/regions.csv", index=False)

# 4. Sales
sales = []
for _ in range(2000):
    sale = {
        "order_id": fake.uuid4(),
        "customer_id": random.choice(customer_ids),
        "product_id": random.randint(501, 550),
        "order_date": fake.date_between(start_date=datetime.date(2023, 1, 1), end_date='today'),
        "order_value": round(random.uniform(20, 2000), 2),
    }
    sales.append(sale)
pd.DataFrame(sales).to_csv("data/monthly_sales_2023.csv", index=False)
