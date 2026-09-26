"""Shared configuration and path helpers for the Retail Ledger showcase.

Every script in this folder imports from here so the dataset location, the
scale presets and the defect thresholds stay in exactly one place. The
reference pipeline and the generated TriggerDesigner workflow must agree on
these numbers, otherwise `step5_compare.py` is comparing two different
problems.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------

EXAMPLE_DIR = Path(__file__).resolve().parent
DATA_DIR = EXAMPLE_DIR / "data"
# Where step2 (pandas) writes its reports.
REFERENCE_OUT = EXAMPLE_DIR / "reference_output"
# Where the TriggerDesigner workflow should write the same reports. Point your
# File Output nodes at this folder so step3 can diff the two versions.
APP_OUT = EXAMPLE_DIR / "app_output"
COMPARE_OUT = EXAMPLE_DIR / "compare_report"

WORKFLOW_NAME = "Retail Ledger Showcase"

# --------------------------------------------------------------------------
# Scale presets
# --------------------------------------------------------------------------
# "demo" exists so the whole showcase runs in well under a minute while you are
# editing it. "xlarge" is the answer to "how much can it actually handle?".

SCALE_PRESETS: dict[str, dict[str, int]] = {
    "demo": {"orders": 40_000, "customers": 4_000, "products": 400, "suppliers": 60},
    "standard": {"orders": 500_000, "customers": 50_000, "products": 1_200, "suppliers": 300},
    "large": {"orders": 2_000_000, "customers": 200_000, "products": 2_000, "suppliers": 500},
    "xlarge": {"orders": 10_000_000, "customers": 500_000, "products": 5_000, "suppliers": 800},
}

DEFAULT_SCALE = "demo"
RANDOM_SEED = 20260926

# --------------------------------------------------------------------------
# Business calendar
# --------------------------------------------------------------------------

ANALYSIS_START = dt.date(2024, 1, 1)
ANALYSIS_END = dt.date(2025, 12, 31)
MAX_VALID_YEAR = 2025

CURRENCIES = {
    "USD": 1.000000,
    "EUR": 1.082000,
    "GBP": 1.271000,
    "JPY": 0.006400,
    "CAD": 0.734000,
    "AUD": 0.658000,
    "CHF": 1.132000,
    "SEK": 0.095000,
    "INR": 0.012000,
    "BRL": 0.181000,
    "ZAR": 0.054000,
    "SGD": 0.741000,
    "MXN": 0.058000,
    "CNY": 0.138000,
    "NZD": 0.605000,
    "NOK": 0.093000,
    "PLN": 0.251000,
    "TRY": 0.029000,
    "AED": 0.272000,
    "KRW": 0.000730,
}

CURRENCY_NAMES = {
    "USD": "US Dollar",
    "EUR": "Euro",
    "GBP": "Pound Sterling",
    "JPY": "Japanese Yen",
    "CAD": "Canadian Dollar",
    "AUD": "Australian Dollar",
    "CHF": "Swiss Franc",
    "SEK": "Swedish Krona",
    "INR": "Indian Rupee",
    "BRL": "Brazilian Real",
    "ZAR": "South African Rand",
    "SGD": "Singapore Dollar",
    "MXN": "Mexican Peso",
    "CNY": "Chinese Yuan",
    "NZD": "New Zealand Dollar",
    "NOK": "Norwegian Krone",
    "PLN": "Polish Zloty",
    "TRY": "Turkish Lira",
    "AED": "UAE Dirham",
    "KRW": "South Korean Won",
}

COUNTRIES = [
    ("US", "North America"),
    ("CA", "North America"),
    ("MX", "North America"),
    ("GB", "Europe"),
    ("DE", "Europe"),
    ("FR", "Europe"),
    ("ES", "Europe"),
    ("IT", "Europe"),
    ("SE", "Europe"),
    ("PL", "Europe"),
    ("TR", "Europe"),
    ("JP", "Asia Pacific"),
    ("CN", "Asia Pacific"),
    ("IN", "Asia Pacific"),
    ("SG", "Asia Pacific"),
    ("KR", "Asia Pacific"),
    ("AU", "Oceania"),
    ("NZ", "Oceania"),
    ("BR", "Latin America"),
    ("ZA", "Latin America"),
    ("AE", "Middle East & Africa"),
]

CATEGORIES = [
    ("Electronics", ["Audio", "Computing", "Mobile", "Wearables"]),
    ("Home & Kitchen", ["Cookware", "Furniture", "Decor", "Storage"]),
    ("Apparel", ["Outerwear", "Footwear", "Accessories", "Kids"]),
    ("Sports & Outdoors", ["Fitness", "Camping", "Cycling", "Team Sports"]),
    ("Toys & Games", ["Board Games", "Building Sets", "Outdoor Play", "Puzzles"]),
    ("Beauty & Health", ["Skincare", "Fragrance", "Wellness", "Personal Care"]),
    ("Office & Stationery", ["Paper", "Writing", "Desk", "Organisation"]),
    ("Automotive", ["Car Care", "Tools", "Accessories", "Components"]),
]

BRANDS = [
    "Northwind",
    "Contoso",
    "Fabrikam",
    "Litware",
    "Proseware",
    "Adventure Works",
    "Tailspin",
    "Wide World",
    "Woodgrove",
    "Relecloud",
]

CHANNELS = [
    (1, "Online Store", "Digital"),
    (2, "Mobile App", "Digital"),
    (3, "Marketplace", "Digital"),
    (4, "Retail Store", "Physical"),
    (5, "Wholesale", "Physical"),
    (6, "Reseller", "Partner"),
    (7, "Direct Sales", "Partner"),
    (8, "Field Sales", "Partner"),
]

ORDER_STATUSES = ["Paid", "Pending", "Refunded", "Cancelled", "Partially Refunded"]
PAYMENT_METHODS = ["Credit Card", "Debit Card", "PayPal", "Bank Transfer", "COD", "Gift Card"]
LOYALTY_TIERS = ["None", "Bronze", "Silver", "Gold", "Platinum"]
CUSTOMER_SEGMENTS = ["Enterprise", "Mid-Market", "SMB", "Consumer"]
AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
SUPPLIER_COUNTRIES = ["CN", "VN", "IN", "MX", "DE", "US", "TR", "IT", "PL", "TW"]

# --------------------------------------------------------------------------
# Injected data-quality defects
# --------------------------------------------------------------------------
# These are the levers the showcase is built around. Both the reference
# pipeline and the workflow have to survive them, and step5_compare.py reports
# how many rows each defect actually moved.

DUP_RATE = 0.02  # exact duplicate order rows
NULL_KEY_RATE = 0.015  # missing customer_id
NULL_PRODUCT_RATE = 0.010  # missing product_id
NULL_TS_RATE = 0.005  # missing order_ts
PADDED_TEXT_RATE = 0.35  # leading/trailing whitespace on text columns
CASE_VARIANT_RATE = 0.25  # STATUS -> "  pAiD  " style noise
BAD_DATE_RATE = 0.08  # non-ISO date rendering
AMBIGUOUS_DATE_RATE = 0.03  # DD-MM-YYYY dates that pandas reads as MM-DD-YYYY
FUTURE_DATE_RATE = 0.004  # timestamps past MAX_VALID_YEAR
ZERO_NEGATIVE_RATE = 0.02  # quantity <= 0 or unit_price_local <= 0
PRICE_OUTLIER_RATE = 0.003  # absurd unit prices
ORPHAN_CUSTOMER_RATE = 0.008  # customer_id absent from customers.csv
ORPHAN_PRODUCT_RATE = 0.004  # product_id absent from products.csv

# Business cleaning thresholds (shared by the script AND the workflow).
MIN_QUANTITY = 1
MAX_QUANTITY = 500
MAX_UNIT_PRICE_LOCAL = 5_000.0
TOP_CUSTOMER_REVENUE_THRESHOLD = 4_000.0
SPLIT_ESTIMATION_PERCENT = 80
SPLIT_RANDOM_SEED = 42
FLOAT_TOLERANCE = 1e-6

# Raw CSV headers for the fact table, deliberately messy. The workflow's first
# Select node exists purely to rename these into snake_case.
RAW_ORDER_COLUMNS = [
    " Order ID ",
    "Customer_Id",
    "PRODUCT_ID",
    "supplier id",
    "Channel ID",
    "Currency",
    "Order TS",
    "Quantity",
    "unit_price_local",
    "Discount Pct",
    "tax_local",
    "shipping_local",
    "Status",
    "Payment Method",
    "is_returned",
]

# The cleaned names the Select node renames them to, in order.
CLEAN_ORDER_COLUMNS = [
    "order_id",
    "customer_id",
    "product_id",
    "supplier_id",
    "channel_id",
    "currency",
    "order_ts",
    "quantity",
    "unit_price_local",
    "discount_pct",
    "tax_local",
    "shipping_local",
    "status",
    "payment_method",
    "is_returned",
]

ORDER_DTYPES: dict[str, str] = {
    "order_id": "String",
    "customer_id": "Int64",
    "product_id": "Int64",
    "supplier_id": "Int64",
    "channel_id": "Int64",
    "currency": "String",
    "order_ts": "Datetime",
    "quantity": "Int64",
    "unit_price_local": "Float64",
    "discount_pct": "Float64",
    "tax_local": "Float64",
    "shipping_local": "Float64",
    "status": "String",
    "payment_method": "String",
    "is_returned": "Boolean",
}

# Text columns that get whitespace / case normalisation from the Cleansing node.
ORDER_TEXT_FIELDS = ["order_id", "currency", "status", "payment_method"]

# Semantic statuses after cleansing. The cleansing node lowercases; the formula
# node maps them back to the canonical Title Case labels used downstream.
CLEAN_STATUSES = ["paid", "pending", "refunded", "cancelled", "partially refunded"]

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def scale_for(name: str) -> dict[str, int]:
    """Return the row-count mapping for a named scale preset."""
    if name not in SCALE_PRESETS:
        valid = ", ".join(sorted(SCALE_PRESETS))
        raise SystemExit(f"Unknown scale '{name}'. Choose one of: {valid}")
    return dict(SCALE_PRESETS[name])


def ensure_dirs() -> None:
    """Create every directory the showcase writes to."""
    for directory in (DATA_DIR, REFERENCE_OUT, APP_OUT, COMPARE_OUT):
        directory.mkdir(parents=True, exist_ok=True)


def data_file(name: str) -> Path:
    return DATA_DIR / name


def app_file(name: str) -> Path:
    return APP_OUT / name


def reference_file(name: str) -> Path:
    return REFERENCE_OUT / name


def normalise_name(raw: str) -> str:
    """The single definition of "clean column name" used by the reference script.

    Mirrors what the workflow's Select node does with its rename mapping.
    """
    return raw.strip().lower().replace(" ", "_")
