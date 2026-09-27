"""Step 2 - the reference pipeline.

This is the "what a competent analyst would write" version of the Retail
Ledger job, in idiomatic Pandas. It is the specification that
Retail_Ledger_Showcase.tds is expected to reproduce.

It is deliberately written the way a real script gets written, which means it
carries a few habits that turn out to matter:

  * `pd.to_datetime` is left to infer its own format, so the DD-MM-YYYY rows
    in orders.csv are read as MM-DD-YYYY and land in the wrong month.
  * Deduplication keeps whichever duplicate pandas saw first.
  * Money is rounded once, at the end, rather than per stage.

step5_compare.py quantifies what each of those costs. Nothing here is a straw
man - it is the code most people would actually ship.

Usage:
    python step2_reference_pipeline.py
"""

from __future__ import annotations

import datetime as dt
import time

import numpy as np
import pandas as pd

import config as cfg

STAGE_COUNTS: dict[str, int] = {}


def log(message: str) -> None:
    print(f"[reference] {message}", flush=True)


def record(stage: str, frame: pd.DataFrame) -> None:
    STAGE_COUNTS[stage] = len(frame)
    log(f"  {stage:<42} {len(frame):>12,} rows")


# --------------------------------------------------------------------------
# Load + normalise
# --------------------------------------------------------------------------


def load_raw() -> dict[str, pd.DataFrame]:
    """Read every CSV as text. That mirrors how the app's reader behaves."""
    raw = {}
    for name in (
        "orders",
        "customers",
        "products",
        "suppliers",
        "channels",
        "fx_rates",
    ):
        path = cfg.data_file(f"{name}.csv")
        if not path.exists():
            raise SystemExit(
                f"Missing {path}. Run step1_generate_data.py first."
            )
        raw[name] = pd.read_csv(path, dtype=str, keep_default_na=True)
        log(f"  loaded {name+'.csv':<20} {raw[name].shape[0]:>12,} rows")
    return raw


def normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Strip / lower / underscore every header.

    The workflow does the same thing, but through a Select node's rename
    mapping rather than a loop.
    """
    renamed = {col: cfg.normalise_name(col) for col in frame.columns}
    return frame.rename(columns=renamed)


# --------------------------------------------------------------------------
# Clean the fact table
# --------------------------------------------------------------------------


def clean_orders(raw: pd.DataFrame) -> pd.DataFrame:
    df = normalise_columns(raw).copy()
    record("01 raw orders", df)

    # --- types ------------------------------------------------------------
    for col in ("customer_id", "product_id", "supplier_id", "channel_id", "quantity"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in ("unit_price_local", "discount_pct", "tax_local", "shipping_local"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["is_returned"] = (
        df["is_returned"].astype(str).str.strip().str.lower().eq("true")
    )

    # --- the ambiguity that matters ---------------------------------------
    # No explicit format. pandas infers per element and reads "05-01-2024"
    # as May 1st. The app tries "%d-%m-%Y" before "%m-%d-%Y" and gets it
    # right. This single line is the showcase's best bug.
    df["order_ts"] = pd.to_datetime(df["order_ts"], format="mixed", errors="coerce")
    record("02 dates parsed", df)

    # --- text hygiene -----------------------------------------------------
    for col in cfg.ORDER_TEXT_FIELDS:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip().str.lower()
            df[col] = df[col].str.replace(r"\s+", " ", regex=True)
    record("03 text normalised", df)

    # --- gates ------------------------------------------------------------
    missing_keys = df["order_id"].isna() | df["customer_id"].isna() | df["product_id"].isna()
    df = df[~missing_keys]
    record("04 dropped null key rows", df)

    good_qty = df["quantity"].between(cfg.MIN_QUANTITY, cfg.MAX_QUANTITY, inclusive="both")
    rejected_quantity = df[~good_qty]
    df = df[good_qty]
    record("05 quantity gate", df)

    good_price = (df["unit_price_local"] > 0) & (
        df["unit_price_local"] <= cfg.MAX_UNIT_PRICE_LOCAL
    )
    rejected_price = df[~good_price]
    df = df[good_price]
    record("06 price gate", df)

    in_window = df["order_ts"].dt.year.le(cfg.MAX_VALID_YEAR)
    rejected_dates = df[~in_window]
    df = df[in_window]
    record("07 date window", df)

    before = len(df)
    # Capture the duplicates *before* dropping them, or the export is empty.
    duplicates = df[df.duplicated(subset=["order_id"], keep=False)]
    df = df.drop_duplicates(subset=["order_id"], keep="first")
    log(f"  {'08 dedupe removed':<42} {before - len(df):>12,} rows")
    STAGE_COUNTS["08 dedupe removed"] = before - len(df)
    log(f"  {'08b duplicate rows captured':<42} {len(duplicates):>12,} rows")

    return df, rejected_quantity, rejected_price, rejected_dates, duplicates


# --------------------------------------------------------------------------
# Enrich
# --------------------------------------------------------------------------


def enrich(
    df: pd.DataFrame,
    customers: pd.DataFrame,
    products: pd.DataFrame,
    suppliers: pd.DataFrame,
    channels: pd.DataFrame,
    fx: pd.DataFrame,
) -> pd.DataFrame:
    # The order's `currency` is the transaction currency and is the one that
    # drives FX conversion. The customer's own preferred currency would
    # collide with it on merge, so it is renamed rather than silently
    # suffixed into currency_x / currency_y.
    customers = customers.rename(
        columns={
            "currency": "customer_currency",
            "country": "customer_country",
            "full_name": "customer_name",
            "email": "customer_email",
            "age_band": "customer_age_band",
            "region": "region",
        }
    )
    enriched = df.merge(customers, on="customer_id", how="left")
    enriched.to_csv(cfg.reference_file("01 enriched customer_id.csv"), index=False)
    record("01 enriched customer_id", enriched)
    enriched = enriched.merge(products, on="product_id", how="left")
    enriched.to_csv(cfg.reference_file("02 enriched product_id.csv"), index=False)
    record("02 enriched product_id", enriched)
    enriched = enriched.merge(suppliers, on="supplier_id", how="left")
    enriched.to_csv(cfg.reference_file("03 enriched supplier_id.csv"), index=False)
    record("03 enriched supplier_id", enriched)
    enriched = enriched.merge(channels, on="channel_id", how="left")
    enriched.to_csv(cfg.reference_file("04 enriched channel_id.csv"), index=False)
    record("04 enriched channel_id", enriched)
    enriched = enriched.merge(fx, on="currency", how="left")
    enriched.to_csv(cfg.reference_file("05 enriched currency.csv"), index=False)
    record("05 enriched currency", enriched)

    g = enriched["quantity"] * enriched["unit_price_local"]

    enriched["gross_local"] = g
    enriched["discount_local"] = g * enriched["discount_pct"]
    enriched["net_local"] = g - enriched["discount_local"]
    enriched["total_local"] = (
        enriched["net_local"] + enriched["tax_local"] + enriched["shipping_local"]
    )

    enriched["unit_price_usd"] = enriched["unit_price_local"] * enriched["usd_rate"]
    enriched["net_revenue_usd"] = enriched["net_local"] * enriched["usd_rate"]
    enriched["tax_usd"] = enriched["tax_local"] * enriched["usd_rate"]
    enriched["shipping_usd"] = enriched["shipping_local"] * enriched["usd_rate"]
    enriched["total_usd"] = enriched["total_local"] * enriched["usd_rate"]

    print(enriched)

    # unit_cost comes from the product catalogue, which is priced in USD. It is
    # already USD, so it must NOT be multiplied by usd_rate again - that is a
    # double conversion and it silently inflates the margin on every non-USD
    # row. It looks fine on the USD rows, which is what makes it expensive to
    # notice: median margin_pct came out at 0.84 instead of 0.40.
    enriched["cogs_usd"] = enriched["quantity"] * enriched["unit_cost"]
    enriched["gross_margin_usd"] = enriched["net_revenue_usd"] - enriched["cogs_usd"]
    enriched["margin_pct"] = enriched["gross_margin_usd"] / enriched[
        "net_revenue_usd"
    ].replace(0, np.nan)

    enriched["order_year"] = enriched["order_ts"].dt.year
    enriched["order_month"] = enriched["order_ts"].dt.month
    enriched["order_year_month"] = enriched["order_ts"].dt.strftime("%Y-%m")

    enriched["is_bulk"] = enriched["quantity"] >= 6
    enriched["value_band"] = pd.cut(
        enriched["net_revenue_usd"],
        bins=[-np.inf, 250, 1000, np.inf],
        labels=["Low", "Medium", "High"],
    ).astype("string")

    bad_status = enriched["status"].isin(["refunded", "cancelled"])
    enriched["risk_score"] = (
        enriched["is_returned"].fillna(False).astype("int64") * 2
        + bad_status.fillna(False).astype("int64") * 2
        + (enriched["net_revenue_usd"] > 2000).fillna(False).astype("int64")
        + (enriched["margin_pct"] < 0.10).fillna(False).astype("int64")
        + enriched["segment"].isna().astype("int64") * 2
    )
    enriched["risk_band"] = np.select(
        [enriched["risk_score"] >= 4, enriched["risk_score"] >= 2],
        ["High", "Medium"],
        default="Low",
    )

    # One rounding pass, at the end, for every money column.
    money_cols = [
        "gross_local", "discount_local", "net_local", "total_local",
        "unit_price_usd", "net_revenue_usd", "tax_usd", "shipping_usd",
        "total_usd", "cogs_usd", "gross_margin_usd",
    ]
    enriched[money_cols] = enriched[money_cols].round(2)
    enriched["margin_pct"] = enriched["margin_pct"].round(4)

    record("20 enriched", enriched)
    return enriched


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def build_reports(enriched: pd.DataFrame) -> None:
    # Named aggregation. A bare list of (column, func) tuples is a cartesian
    # spec in pandas and silently produces one column per combination.
    agg = dict(
        revenue_usd=("net_revenue_usd", "sum"),
        margin_usd=("gross_margin_usd", "sum"),
        orders=("order_id", "nunique"),
    )

    monthly = (
        enriched.groupby("order_year_month", dropna=False)
        .agg(**agg)
        .reset_index()
        .sort_values("order_year_month")
    )
    monthly["cumulative_revenue_usd"] = monthly["revenue_usd"].cumsum()
    monthly.to_csv(cfg.reference_file("monthly_revenue.csv"), index=False)
    log(f"  monthly_revenue.csv{'':<22} {len(monthly):>12,} rows")

    # Long/tidy form, the equivalent of the workflow's Transpose node.
    monthly_long = monthly.melt(
        id_vars=["order_year_month"],
        value_vars=["revenue_usd", "margin_usd", "orders"],
        var_name="metric",
        value_name="value",
    )
    monthly_long.to_csv(cfg.reference_file("monthly_revenue_long.csv"), index=False)
    log(f"  monthly_revenue_long.csv{'':<19} {len(monthly_long):>12,} rows")

    category = (
        enriched.groupby("category", dropna=False)
        .agg(**agg)
        .reset_index()
        .sort_values("revenue_usd", ascending=False)
    )
    category.to_csv(cfg.reference_file("category_revenue.csv"), index=False)
    log(f"  category_revenue.csv{'':<21} {len(category):>12,} rows")

    region_channel = (
        enriched.groupby(["region", "channel_group"], dropna=False)
        .agg(**agg)
        .reset_index()
        .sort_values(["region", "channel_group"])
    )
    region_channel.to_csv(cfg.reference_file("region_channel_revenue.csv"), index=False)
    log(f"  region_channel_revenue.csv{'':<16} {len(region_channel):>12,} rows")

    segment = (
        enriched.groupby(["segment", "risk_band"], dropna=False)
        .agg(**agg)
        .reset_index()
        .sort_values(["segment", "risk_band"])
    )
    segment.to_csv(cfg.reference_file("segment_revenue.csv"), index=False)
    log(f"  segment_revenue.csv{'':<21} {len(segment):>12,} rows")

    # "Top customers" defined as a revenue threshold rather than a top-N cut.
    # The workflow has no limit node, so the threshold is the shared contract.
    per_customer = enriched.groupby("customer_id", dropna=False).agg(
        revenue_usd=("net_revenue_usd", "sum"),
        orders=("order_id", "nunique"),
    ).reset_index()
    top_customers = (
        per_customer[per_customer["revenue_usd"] > cfg.TOP_CUSTOMER_REVENUE_THRESHOLD]
        .sort_values("revenue_usd", ascending=False)
    )
    top_customers.to_csv(cfg.reference_file("top_customers.csv"), index=False)
    log(f"  top_customers.csv{'':<23} {len(top_customers):>12,} rows")

    suppliers = (
        enriched.groupby(["supplier_id", "supplier_name", "country"], dropna=False)
        .agg(
            revenue_usd=("net_revenue_usd", "sum"),
            orders=("order_id", "nunique"),
            lead_time_days=("lead_time_days", "first"),
            reliability_score=("reliability_score", "first"),
        )
        .reset_index()
        .sort_values("revenue_usd", ascending=False)
    )
    suppliers["revenue_per_lead_day"] = (
        suppliers["revenue_usd"] / suppliers["lead_time_days"]
    ).round(4)
    suppliers.to_csv(cfg.reference_file("supplier_performance.csv"), index=False)
    log(f"  supplier_performance.csv{'':<18} {len(suppliers):>12,} rows")

    fx_exposure = (
        enriched.groupby("currency", dropna=False)
        .agg(
            revenue_usd=("net_revenue_usd", "sum"),
            orders=("order_id", "nunique"),
            usd_rate=("usd_rate", "first"),
        )
        .reset_index()
        .sort_values("revenue_usd", ascending=False)
    )
    fx_exposure.to_csv(cfg.reference_file("fx_exposure.csv"), index=False)
    log(f"  fx_exposure.csv{'':<24} {len(fx_exposure):>12,} rows")

    kpi = pd.DataFrame(
        {
            "metric": [
                "clean_orders", "gross_revenue_usd", "net_revenue_usd",
                "gross_margin_usd", "margin_pct", "returned_orders",
                "high_risk_orders", "distinct_customers", "distinct_products",
            ],
            "value": [
                int(enriched["order_id"].nunique()),
                float(enriched["gross_local"].mul(enriched["usd_rate"]).sum().round(2)),
                float(enriched["net_revenue_usd"].sum().round(2)),
                float(enriched["gross_margin_usd"].sum().round(2)),
                float(
                    (
                        enriched["gross_margin_usd"].sum()
                        / enriched["net_revenue_usd"].sum()
                    ).round(4)
                ),
                int(enriched["is_returned"].sum()),
                int((enriched["risk_band"] == "High").sum()),
                int(enriched["customer_id"].nunique()),
                int(enriched["product_id"].nunique()),
            ],
        }
    )
    kpi.to_csv(cfg.reference_file("kpi_summary.csv"), index=False)
    log(f"  kpi_summary.csv{'':<24} {len(kpi):>12,} rows")

    enterprise = enriched[enriched["segment"] == "Enterprise"]
    enterprise.to_csv(cfg.reference_file("orders_enterprise.csv"), index=False)
    log(f"  orders_enterprise.csv{'':<20} {len(enterprise):>12,} rows")

    high_risk = enriched[enriched["risk_band"] == "High"]
    high_risk.to_csv(cfg.reference_file("orders_high_risk.csv"), index=False)
    log(f"  orders_high_risk.csv{'':<20} {len(high_risk):>12,} rows")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> None:
    cfg.ensure_dirs()
    started = time.time()
    log("loading raw CSV ...")
    raw = load_raw()

    log("cleaning the fact table ...")
    orders, rej_qty, rej_price, rej_dates, dups = clean_orders(raw["orders"])

    for frame, name in (
        (rej_qty, "rejected_quantity.csv"),
        (rej_price, "rejected_price_outliers.csv"),
        (rej_dates, "rejected_future_dates.csv"),
        (dups, "duplicate_orders.csv"),
    ):
        frame.to_csv(cfg.reference_file(name), index=False)
        log(f"  {name:<42} {len(frame):>12,} rows")

    log("normalising dimensions ...")
    customers = normalise_columns(raw["customers"])
    products = normalise_columns(raw["products"])
    suppliers = normalise_columns(raw["suppliers"])
    channels = normalise_columns(raw["channels"])
    fx = normalise_columns(raw["fx_rates"])

    products["unit_price"] = pd.to_numeric(products["unit_price"], errors="coerce")
    products["unit_cost"] = pd.to_numeric(products["unit_cost"], errors="coerce")
    suppliers["lead_time_days"] = pd.to_numeric(suppliers["lead_time_days"], errors="coerce")
    suppliers["reliability_score"] = pd.to_numeric(
        suppliers["reliability_score"], errors="coerce"
    )
    fx["usd_rate"] = pd.to_numeric(fx["usd_rate"], errors="coerce")

    # Currency codes are upper case in fx_rates.csv but the cleansing stage
    # lower-cased the order side, so the dimension needs the same treatment or
    # every FX join misses. The workflow gets this from a Cleansing node on
    # fx_rates.csv.
    fx["currency"] = fx["currency"].astype("string").str.strip().str.lower()

    # Dimension keys arrive as text from the CSV reader. The fact table's keys
    # are already Int64, so the dimensions have to match or the merge refuses.
    for frame, col in (
        (customers, "customer_id"),
        (products, "product_id"),
        (suppliers, "supplier_id"),
        (channels, "channel_id"),
    ):
        frame[col] = pd.to_numeric(frame[col], errors="coerce").astype("Int64")

    # `region` ships in customers.csv already, so both the script and the
    # workflow group the regional rollup on a real column instead of deriving
    # one - the node set has no lookup/map operation to derive it with.
    if "region" not in customers.columns:
        region_map = {code: region for code, region in cfg.COUNTRIES}
        customers["region"] = customers["country"].map(region_map)

    log("enriching ...")
    enriched = enrich(orders, customers, products, suppliers, channels, fx)

    # Orphans, the same two populations the workflow's Join node isolates.
    enriched[enriched["segment"].isna()].to_csv(
        cfg.reference_file("orphan_customers.csv"), index=False
    )
    enriched[enriched["category"].isna()].to_csv(
        cfg.reference_file("orphan_products.csv"), index=False
    )

    log("building reports ...")
    build_reports(enriched)

    # Deterministic 80/20 split, the same split the workflow's Split node makes.
    log("splitting ...")
    shuffled = enriched.sample(frac=1.0, random_state=cfg.SPLIT_RANDOM_SEED)
    cut = int(len(shuffled) * cfg.SPLIT_ESTIMATION_PERCENT / 100)
    shuffled.iloc[:cut].to_csv(cfg.reference_file("fact_estimation.csv"), index=False)
    shuffled.iloc[cut:].to_csv(cfg.reference_file("fact_validation.csv"), index=False)
    log(f"  fact_estimation.csv / fact_validation.csv  {cut:,} / {len(shuffled)-cut:,}")

    # Union of every dimension, the equivalent of the workflow's Append node.
    # pd.concat already outer-aligns the columns and fills the gaps with null,
    # which is exactly what polars' `diagonal_relaxed` concat does.
    union = pd.concat(
        [
            customers.assign(source_table="customers"),
            products.assign(source_table="products"),
            suppliers.assign(source_table="suppliers"),
            channels.assign(source_table="channels"),
            fx.assign(source_table="fx_rates"),
        ],
        ignore_index=True,
    )
    union.to_csv(cfg.reference_file("reference_data_union.csv"), index=False)
    log(f"  reference_data_union.csv{'':<17} {len(union):>12,} rows")

    # Scenario grid, the equivalent of the Dynamic Row Builder node.
    scenarios = [
        {"scenario": name, "year": year, "revenue_growth_pct": pct}
        for name, pct in (("Base", 4.0), ("Upside", 12.5), ("Downside", -7.25))
        for year in (2024, 2025)
    ]
    pd.DataFrame(scenarios).to_csv(cfg.reference_file("scenario_grid.csv"), index=False)
    log(f"  scenario_grid.csv{'':<23} {len(scenarios):>12,} rows")

    quality = pd.DataFrame(
        {"stage": list(STAGE_COUNTS), "rows": list(STAGE_COUNTS.values())}
    )
    quality.to_csv(cfg.reference_file("data_quality_report.csv"), index=False)

    master_columns = [
        "order_id", "order_ts", "order_year", "order_month", "order_year_month",
        "customer_id", "product_id", "supplier_id", "channel_id", "channel_name",
        "channel_group", "category", "subcategory", "brand", "customer_country", "region",
        "segment", "loyalty_tier", "currency", "usd_rate", "status", "status_clean",
        "quantity", "unit_price_local", "discount_pct", "net_local", "total_local",
        "net_revenue_usd", "cogs_usd", "gross_margin_usd", "margin_pct", "value_band",
        "risk_score", "risk_band", "is_returned", "is_bulk",
    ]
    master = enriched.copy()
    master["status_clean"] = master["status"].str.title()
    available = [c for c in master_columns if c in master.columns]
    master[available].to_csv(cfg.reference_file("orders_enriched.csv"), index=False)
    log(f"  orders_enriched.csv{'':<20} {len(master):>12,} rows")

    elapsed = time.time() - started
    log(f"done in {elapsed:.1f}s -> {cfg.REFERENCE_OUT}")


if __name__ == "__main__":
    main()
