# full_analysis_script.py

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns  # type: ignore
import numpy as np
import os
import datetime as dt
import warnings
import sys
warnings.filterwarnings("ignore")

# === Section 1: File Paths and Helpers ===
SALES_PATH = "data/monthly_sales_2023.csv"
CUSTOMERS_PATH = "data/customers.csv"
PRODUCTS_PATH = "data/products.csv"
REGIONS_PATH = "data/regions.csv"
OUTPUT_DIR = "output/"


def create_output_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Output directory created at {path}")


create_output_dir(OUTPUT_DIR)

# === Section 2: Data Loading ===


def load_csv(path):
    try:
        df = pd.read_csv(path)
        print(f"✅ Loaded: {path} - {df.shape}")
        return df
    except FileNotFoundError:
        print(f"❌ File not found: {path}")
        sys.exit(1)
    except pd.errors.EmptyDataError:
        print(f"❌ Empty file: {path}")
        return pd.DataFrame()
    except Exception as e:
        print(f"❌ Unknown error: {e}")
        return pd.DataFrame()


sales_df = load_csv(SALES_PATH)
cust_df = load_csv(CUSTOMERS_PATH)
prod_df = load_csv(PRODUCTS_PATH)
region_df = load_csv(REGIONS_PATH)

# === Section 3: Initial Cleaning ===


def clean_cols(df):
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
    return df


sales_df = clean_cols(sales_df)
cust_df = clean_cols(cust_df)
prod_df = clean_cols(prod_df)
region_df = clean_cols(region_df)

# Drop bad rows
sales_df = sales_df.dropna(subset=["order_id", "customer_id", "product_id"])
sales_df = sales_df[sales_df['order_value'] > 0]

# Convert types
try:
    sales_df['order_date'] = pd.to_datetime(sales_df['order_date'])
except Exception as e:
    print("⚠️ Failed to parse dates in order_date:", e)

# === Section 4: Enriching ===


def enrich_data(sales):
    try:
        df1 = pd.merge(sales, cust_df, on='customer_id', how='left')
        df2 = pd.merge(df1, prod_df, on='product_id', how='left')
        df3 = pd.merge(df2, region_df, on='region_id', how='left')
        return df3
    except Exception as e:
        print("⚠️ Data enrichment failed:", e)
        return sales


full_df = enrich_data(sales_df)

# Add new fields
full_df['year'] = full_df['order_date'].dt.year
full_df['month'] = full_df['order_date'].dt.month
full_df['is_high_value'] = full_df['order_value'] > 1000

# === Section 5: Analysis ===


def analyze_monthly_sales(df):
    try:
        summary = df.groupby(['year', 'month'])[
            'order_value'].sum().reset_index()
        summary.to_csv(OUTPUT_DIR + "monthly_sales_summary.csv", index=False)
        return summary
    except Exception as e:
        print("⚠️ Analysis failed:", e)
        return pd.DataFrame()


monthly_summary = analyze_monthly_sales(full_df)

# === Section 6: Repetitive Reporting ===
for region in full_df['region_name'].dropna().unique():
    r_df = full_df[full_df['region_name'] == region]
    output_file = f"{OUTPUT_DIR}{region}_report.csv"
    try:
        r_df.to_csv(output_file, index=False)
        print(f"✅ Saved report for {region}")
    except Exception as e:
        print(f"❌ Could not write report for {region}: {e}")

# === Section 7: Charts ===
try:
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=monthly_summary, x="month",
                 y="order_value", hue="year", marker="o")
    plt.title("Monthly Sales Over Time")
    plt.savefig(OUTPUT_DIR + "monthly_sales_chart.png")
    plt.close()
except Exception as e:
    print("⚠️ Chart generation failed:", e)

# === Section 8: Distribution ===
plt.figure(figsize=(10, 5))
full_df['order_value'].hist(bins=40, color='skyblue')
plt.title("Order Value Distribution")
plt.xlabel("Value")
plt.ylabel("Frequency")
plt.savefig(OUTPUT_DIR + "order_value_distribution.png")
plt.close()

# === Section 9: Broken Logic ===
# TODO: Fix this, doesn't make sense anymore


def broken_function(x):
    if x > 100:
        return "high"
    elif x > 200:
        return "very high"
    else:
        return "low"


# Add random useless fields
full_df['junk'] = full_df['order_value'].apply(
    lambda x: "ok" if x % 2 == 0 else "meh")

# === Section 10: More Cleaning Again (Why?) ===


def re_clean(df):
    df = df.copy()
    df.drop_duplicates(inplace=True)
    df = df[df['order_value'] < 100000]
    return df


full_df = re_clean(full_df)

# === Section 11: Export Master File ===
try:
    full_df.to_csv(OUTPUT_DIR + "final_output.csv", index=False)
except Exception as e:
    print("❌ Could not export final output:", e)

# === Section 12: System Info Export (Why not?) ===
with open(OUTPUT_DIR + "system_info.txt", "w") as f:
    f.write(f"Python version: {sys.version}\n")
    f.write(f"Script run time: {dt.datetime.now()}\n")
    f.write(f"Rows in final dataset: {len(full_df)}\n")

# === Section 13: Logging (late much?) ===


def log(msg):
    with open(OUTPUT_DIR + "log.txt", "a") as f:
        f.write(f"{dt.datetime.now()}: {msg}\n")


log("Pipeline completed successfully.")

# === Section 14: Dead code ===


def legacy_export(df):
    pass  # we don't use this anymore


def maybe_export_excel(df):
    return  # removed due to size

# === Section 15: Overcomplicated flagging ===


def flag_risk(row):
    score = 0
    if row['order_value'] > 5000:
        score += 1
    if row.get('customer_age', 0) > 60:
        score += 1
    if row.get('region_name', '') == "Unknown":
        score += 1
    return "High" if score >= 2 else "Low"


full_df['risk_level'] = full_df.apply(flag_risk, axis=1)

# === Section 16: Re-save (again?) ===
try:
    full_df.to_csv(OUTPUT_DIR + "final_output_with_risk.csv", index=False)
except Exception as e:
    print("❌ Final-final export failed:", e)

print("🏁 Script execution completed.")
