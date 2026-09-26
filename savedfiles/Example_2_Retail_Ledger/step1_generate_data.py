"""Step 1 - generate the Retail Ledger dataset.

Produces five dimension tables and one deliberately dirty fact table. The
defects are not random noise; each one is there to force a specific node type
in the workflow built by step 3:

    messy headers          -> Select (rename_mapping)
    all-text CSV           -> Select (dtype_mapping)
    padded / cased text    -> Cleansing (strip, normalize, case)
    null keys              -> Cleansing (remove null rows)
    zero / negative money  -> Filter (quantity / price gates, both outputs)
    absurd prices          -> Filter (outlier gate)
    future timestamps      -> Filter (date sanity gate)
    duplicate orders       -> Unique (both outputs)
    orphan foreign keys    -> Join (right-only output)
    mixed date renderings  -> Select (Datetime parse) + the DD-MM vs MM-DD trap
    nulls in dimensions    -> Join (left-only output)

Usage:
    python step1_generate_data.py --scale standard
    python step1_generate_data.py --scale xlarge --force
"""

from __future__ import annotations

import argparse
import time

import polars as pl

import config as cfg

# --------------------------------------------------------------------------
# Deterministic name pools
#
# Faker is deliberately not used: it is slow at multi-million-row scale and
# would make the dataset non-reproducible across versions. These pools plus
# numpy give stable output for a given seed.
# --------------------------------------------------------------------------

FIRST_NAMES = [
    "Amara", "Bruno", "Chidi", "Dalia", "Eero", "Farida", "Goran", "Hana",
    "Ibrahim", "Jana", "Kofi", "Lucia", "Mateo", "Nadia", "Omar", "Priya",
    "Qasim", "Rosa", "Sven", "Tariq", "Ulrike", "Viktor", "Wei", "Ximena",
    "Yusuf", "Zara",
]

LAST_NAMES = [
    "Abebe", "Bianchi", "Costa", "Dubois", "Eriksen", "Ferreira", "Gupta",
    "Haddad", "Iversen", "Jansen", "Kowalski", "Lindqvist", "Mensah",
    "Nakamura", "Oyelaran", "Petrov", "Quintero", "Rossi", "Silva", "Tariq",
    "Ueda", "Vasquez", "Weber", "Xu", "Yilmaz", "Zielinski",
]

PRODUCT_ADJECTIVES = [
    "Compact", "Premium", "Classic", "Rugged", "Silent", "Rapid", "Eco",
    "Pro", "Essential", "Deluxe", "Ultra", "Nano", "Max", "Mini", "Smart",
]

PRODUCT_NOUNS = [
    "Speaker", "Router", "Jacket", "Skillet", "Trainer", "Puzzle", "Serum",
    "Notebook", "Wrench", "Cable", "Lamp", "Chair", "Bottle", "Backpack",
    "Keyboard", "Monitor", "Blender", "Headset", "Projector", "Drill",
]

SUPPLIER_PREFIX = [
    "Shenzhen", "Taipei", "Pune", "Monterrey", "Hamburg", "Austin", "Izmir",
    "Milan", "Gdansk", "Kaohsiung",
]

SUPPLIER_SUFFIX = [
    "Precision", "Components", "Industries", "Manufacturing", "Works",
    "Electronics", "Textiles", "Plastics", "Logistics", "Trading",
]


def _log(message: str) -> None:
    print(f"[generate] {message}", flush=True)


# --------------------------------------------------------------------------
# Dimension tables
# --------------------------------------------------------------------------


def build_customers(n: int) -> pl.DataFrame:
    """Customer dimension. Clean apart from a few null loyalty tiers."""
    import numpy as np

    rng = np.random.default_rng(cfg.RANDOM_SEED)
    ids = np.arange(1, n + 1, dtype=np.int64)

    first = rng.integers(0, len(FIRST_NAMES), n)
    last = rng.integers(0, len(LAST_NAMES), n)
    # Zipf-ish tier mix: most customers are 'None' or 'Bronze'.
    tier_weights = [0.34, 0.26, 0.19, 0.13, 0.08]
    tier_idx = rng.choice(len(cfg.LOYALTY_TIERS), n, p=tier_weights)
    segment_idx = rng.choice(len(cfg.CUSTOMER_SEGMENTS), n)
    country_idx = rng.integers(0, len(cfg.COUNTRIES), n)
    country_codes = np.array([c[0] for c in cfg.COUNTRIES])
    region_names = np.array([c[1] for c in cfg.COUNTRIES])
    age_idx = rng.integers(0, len(cfg.AGE_BANDS), n)
    currency_list = list(cfg.CURRENCIES)
    currency_idx = rng.integers(0, len(currency_list), n)

    signup_offsets = rng.integers(0, 900, n)
    signup_dates = (
        np.datetime64(cfg.ANALYSIS_START) - signup_offsets.astype("timedelta64[D]")
    ).astype(str)

    # ~4% of customers have no loyalty tier recorded.
    null_tier = rng.random(n) < 0.04

    first_arr = np.array(FIRST_NAMES)[first]
    last_arr = np.array(LAST_NAMES)[last]

    return pl.DataFrame(
        {
            "customer_id": ids,
            "email": np.char.add(
                np.char.add(
                    np.char.add(np.char.lower(first_arr), "."),
                    np.char.lower(last_arr),
                ),
                np.char.add(ids.astype(str), "@example.com"),
            ),
            "full_name": np.char.add(np.char.add(first_arr, " "), last_arr),
            "signup_date": signup_dates,
            "country": country_codes[country_idx],
            # region is a real column, not something the pipeline derives. The
            # node set has no lookup/map operation, so the rollup needs it
            # materialised - which is also what a real warehouse would do.
            "region": region_names[country_idx],
            "currency": np.array(currency_list)[currency_idx],
            "segment": np.array(cfg.CUSTOMER_SEGMENTS)[segment_idx],
            "age_band": np.array(cfg.AGE_BANDS)[age_idx],
            "loyalty_tier": pl.Series(
                "loyalty_tier",
                np.array(cfg.LOYALTY_TIERS, dtype=object)[tier_idx],
                dtype=pl.String,
            ).to_frame().select(
                pl.when(pl.Series(null_tier, dtype=pl.Boolean))
                .then(pl.lit(None, dtype=pl.String))
                .otherwise(pl.col("loyalty_tier"))
                .alias("loyalty_tier")
            )["loyalty_tier"],
        }
    )


def product_price_vector(n: int):
    """Deterministic product list prices, shared by products and orders.

    The fact table prices an order off the product's list price rather than
    drawing an independent amount. Without this the transaction price and the
    unit cost are unrelated, gross margin lands at an absurd ~79%, and the
    `margin_pct < 10%` risk rule never fires for the reason it should.
    """
    import numpy as np

    rng = np.random.default_rng(cfg.RANDOM_SEED + 101)
    return np.round(4.0 * np.exp(rng.normal(1.55, 0.95, n)), 2)


def build_products(n: int) -> pl.DataFrame:
    import numpy as np

    rng = np.random.default_rng(cfg.RANDOM_SEED + 1)
    ids = np.arange(500_001, 500_001 + n, dtype=np.int64)

    cat_idx = rng.integers(0, len(cfg.CATEGORIES), n)
    sub_idx = rng.integers(0, 4, n)
    adjective_idx = rng.integers(0, len(PRODUCT_ADJECTIVES), n)
    noun_idx = rng.integers(0, len(PRODUCT_NOUNS), n)
    brand_idx = rng.integers(0, len(cfg.BRANDS), n)

    categories = np.array([c[0] for c in cfg.CATEGORIES])[cat_idx]
    subcategories = np.array([c[1] for c in cfg.CATEGORIES], dtype=object)[
        cat_idx, sub_idx
    ]
    brands = np.array(cfg.BRANDS)[brand_idx]
    names = np.char.add(
        np.char.add(np.array(PRODUCT_ADJECTIVES)[adjective_idx], " "),
        np.array(PRODUCT_NOUNS)[noun_idx],
    )

    # Log-normal-ish prices: a long cheap tail and a short expensive head.
    # The price vector has to be reproducible on its own, because the fact
    # table prices its orders off the product's list price. See
    # product_price_vector().
    unit_price = product_price_vector(n)
    # Margin varies by product so gross margin analysis is not uniform.
    margin_factor = rng.uniform(0.28, 0.52, n)
    unit_cost = np.round(unit_price * (1.0 - margin_factor), 2)

    launch_offsets = rng.integers(0, 2000, n)
    launch_dates = (
        np.datetime64(cfg.ANALYSIS_START) - launch_offsets.astype("timedelta64[D]")
    ).astype(str)

    return pl.DataFrame(
        {
            "product_id": ids,
            "sku": np.char.add("SKU-", np.char.zfill(ids.astype(str), 8)),
            "product_name": names,
            "category": categories,
            "subcategory": subcategories,
            "brand": brands,
            "unit_price": unit_price,
            "unit_cost": unit_cost,
            "launch_date": launch_dates,
        }
    )


def build_suppliers(n: int) -> pl.DataFrame:
    import numpy as np

    rng = np.random.default_rng(cfg.RANDOM_SEED + 2)
    ids = np.arange(900_001, 900_001 + n, dtype=np.int64)
    prefixes = np.array(SUPPLIER_PREFIX)[rng.integers(0, len(SUPPLIER_PREFIX), n)]
    suffixes = np.array(SUPPLIER_SUFFIX)[rng.integers(0, len(SUPPLIER_SUFFIX), n)]
    ordinal = np.char.zfill((ids % 1000).astype(str), 3)

    return pl.DataFrame(
        {
            "supplier_id": ids,
            "supplier_name": np.char.add(
                np.char.add(np.char.add(prefixes, " "), suffixes), " " + ordinal
            ),
            "country": np.array(cfg.SUPPLIER_COUNTRIES)[
                rng.integers(0, len(cfg.SUPPLIER_COUNTRIES), n)
            ],
            "lead_time_days": rng.integers(3, 90, n),
            "reliability_score": np.round(rng.uniform(0.35, 0.99, n), 3),
        }
    )


def build_channels() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "channel_id": [c[0] for c in cfg.CHANNELS],
            "channel_name": [c[1] for c in cfg.CHANNELS],
            "channel_group": [c[2] for c in cfg.CHANNELS],
            "is_digital": [c[2] == "Digital" for c in cfg.CHANNELS],
        }
    )


def build_fx_rates() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "currency": list(cfg.CURRENCIES.keys()),
            "currency_name": [cfg.CURRENCY_NAMES[c] for c in cfg.CURRENCIES],
            "usd_rate": [float(r) for r in cfg.CURRENCIES.values()],
        }
    )


# --------------------------------------------------------------------------
# The fact table
# --------------------------------------------------------------------------


def build_orders(n: int, n_customers: int, n_products: int, n_suppliers: int) -> pl.DataFrame:
    import numpy as np

    rng = np.random.default_rng(cfg.RANDOM_SEED + 3)

    customer_ids = np.arange(1, n_customers + 1, dtype=np.int64)
    product_ids = np.arange(500_001, 500_001 + n_products, dtype=np.int64)
    supplier_ids = np.arange(900_001, 900_001 + n_suppliers, dtype=np.int64)
    channel_ids = [c[0] for c in cfg.CHANNELS]
    currency_list = list(cfg.CURRENCIES.keys())

    # --- keys, with a slice of orphans on purpose -------------------------
    cust_pick = customer_ids[rng.integers(0, n_customers, n)].astype(np.float64)
    orphan_customer = rng.random(n) < cfg.ORPHAN_CUSTOMER_RATE
    cust_pick[orphan_customer] = n_customers + 1 + rng.integers(1, 900, int(orphan_customer.sum()))
    null_customer = rng.random(n) < cfg.NULL_KEY_RATE
    cust_pick[null_customer] = np.nan

    base_product_idx = rng.integers(0, n_products, n)
    prod_pick = product_ids[base_product_idx].astype(np.float64)
    orphan_product = rng.random(n) < cfg.ORPHAN_PRODUCT_RATE
    prod_pick[orphan_product] = 500_001 + n_products + rng.integers(1, 500, int(orphan_product.sum()))
    null_product = rng.random(n) < cfg.NULL_PRODUCT_RATE
    prod_pick[null_product] = np.nan

    order_id_nums = rng.integers(10**10, 10**11, n)

    # --- timestamps -------------------------------------------------------
    span_days = (cfg.ANALYSIS_END - cfg.ANALYSIS_START).days
    day_offsets = rng.integers(0, span_days + 1, n)
    seconds = rng.integers(0, 86_400, n)
    base = np.datetime64(cfg.ANALYSIS_START) + day_offsets.astype("timedelta64[D]")
    stamps = base + seconds.astype("timedelta64[s]")

    # Future timestamps: a warehouse clock that was never fixed.
    future = rng.random(n) < cfg.FUTURE_DATE_RATE
    stamps[future] = np.datetime64("2099-12-31") + rng.integers(0, 86_400, int(future.sum())).astype(
        "timedelta64[s]"
    )
    null_ts = rng.random(n) < cfg.NULL_TS_RATE
    stamps[null_ts] = np.datetime64("NaT")

    # --- money -----------------------------------------------------------
    quantity = rng.integers(1, 12, n)
    zero_or_negative = rng.random(n) < cfg.ZERO_NEGATIVE_RATE
    quantity[zero_or_negative] = rng.choice([0, -1, -2, -5], int(zero_or_negative.sum()))

    # Local unit price. The USD anchor comes from the product's own list price
    # with a tight pricing noise term, so cost and revenue stay in a realistic
    # relationship. Then convert to the transaction currency.
    currency_pick = rng.integers(0, len(currency_list), n)
    rates = np.array([cfg.CURRENCIES[c] for c in currency_list])
    list_price = product_price_vector(n_products)
    usd_price = np.round(list_price[base_product_idx] * np.exp(rng.normal(0, 0.10, n)), 2)
    local_price = np.round(usd_price / rates[currency_pick], 2)

    outlier = rng.random(n) < cfg.PRICE_OUTLIER_RATE
    local_price[outlier] = np.round(rng.uniform(50_000, 900_000, int(outlier.sum())), 2)
    nonpositive = rng.random(n) < cfg.ZERO_NEGATIVE_RATE
    local_price[nonpositive] = np.round(-rng.uniform(1, 500, int(nonpositive.sum())), 2)

    discount_pct = np.round(rng.choice([0.0, 0.0, 0.05, 0.1, 0.15, 0.2, 0.3], n), 2)
    tax_local = np.round(local_price * quantity * rng.uniform(0.0, 0.2, n), 2)
    shipping_local = np.round(rng.choice([0.0, 0.0, 4.99, 9.99, 19.99, 34.99], n), 2)

    status_pick = rng.choice(len(cfg.ORDER_STATUSES), n, p=[0.78, 0.09, 0.05, 0.05, 0.03])
    payment_pick = rng.choice(len(cfg.PAYMENT_METHODS), n, p=[0.3, 0.2, 0.18, 0.15, 0.1, 0.07])
    returned = rng.random(n) < 0.06

    frame = pl.DataFrame(
        {
            "_order_num": order_id_nums,
            "_customer": cust_pick,
            "_product": prod_pick,
            "_supplier": supplier_ids[rng.integers(0, n_suppliers, n)],
            "_channel": np.array(channel_ids)[rng.integers(0, len(channel_ids), n)],
            "_currency": np.array(currency_list)[currency_pick],
            "_stamp": stamps.astype("datetime64[ms]"),
            "_quantity": quantity,
            "_price": local_price,
            "_discount": discount_pct,
            "_tax": tax_local,
            "_ship": shipping_local,
            "_status": np.array(cfg.ORDER_STATUSES)[status_pick],
            "_payment": np.array(cfg.PAYMENT_METHODS)[payment_pick],
            "_returned": returned,
        }
    )

    # --- render the deliberately dirty surface form ------------------------
    # Everything below is vectorised. A per-row Python loop here is the
    # difference between generating 10M rows in ~40s and in ~20 minutes.
    pad = pl.Series(rng.random(n) < cfg.PADDED_TEXT_RATE)
    casify = pl.Series(rng.random(n) < cfg.CASE_VARIANT_RATE)

    def dirty_text(col: str) -> pl.Expr:
        """Lowercase a share of the values, then pad a share with spaces."""
        return (
            pl.when(casify)
            .then(pl.col(col).str.to_lowercase())
            .otherwise(pl.col(col))
            .alias(col)
            .pipe(
                lambda e: pl.when(pad).then(pl.lit("  ") + e).otherwise(e)
            )
        )

    def money(col: str) -> pl.Expr:
        """Render a float the way a fixed-2dp export would, null as empty."""
        return (
            pl.when(pl.col(col).is_null())
            .then(pl.lit(""))
            .otherwise(pl.col(col).round(2).cast(pl.String))
            .alias(col)
        )

    # Timestamps get one of four renderings. The day-first bucket is the trap:
    # it is only populated for days <= 12, so the two possible readings of the
    # string differ, and the reference script gets it wrong on purpose.
    bucket = rng.random(n)
    alt_choice = rng.random(n)

    # polars only ingests ms/us/ns datetime64, so widen from seconds here.
    stamp_col = pl.Series("stamp", stamps.astype("datetime64[ms]"))
    day_first = stamp_col.dt.day().to_numpy() <= 12

    iso = stamp_col.dt.strftime("%Y-%m-%d %H:%M:%S")
    slash = stamp_col.dt.strftime("%Y/%m/%d %H:%M:%S")
    dayfirst_str = stamp_col.dt.strftime("%d-%m-%Y %H:%M:%S")
    dotted = stamp_col.dt.strftime("%Y.%m.%d %H:%M:%S")
    text_month = stamp_col.dt.strftime("%d %b %Y %H:%M:%S")

    is_alt = pl.Series(bucket < cfg.BAD_DATE_RATE)
    is_ambiguous = pl.Series(
        (bucket >= cfg.BAD_DATE_RATE)
        & (bucket < cfg.BAD_DATE_RATE + cfg.AMBIGUOUS_DATE_RATE)
        & day_first
    )
    alt_pick = pl.Series(alt_choice)

    order_ts = (
        pl.when(is_ambiguous)
        .then(dayfirst_str)
        .when(is_alt & (alt_pick < 0.30))
        .then(slash)
        .when(is_alt & (alt_pick < 0.55))
        .then(dayfirst_str)
        .when(is_alt & (alt_pick < 0.80))
        .then(dotted)
        .when(is_alt)
        .then(text_month)
        .otherwise(iso)
        .alias("Order TS")
    )

    # NaT renders as an empty string, which becomes a null on the way back in.
    order_ts = order_ts.fill_null("")

    clean = frame.with_columns(
        order_id=pl.col("_order_num").cast(pl.String),
        order_ts=order_ts,
        customer=pl.col("_customer").cast(pl.Int64, strict=False),
        product=pl.col("_product").cast(pl.Int64, strict=False),
        supplier=pl.col("_supplier").cast(pl.Int64),
        channel=pl.col("_channel").cast(pl.Int64),
        quantity=pl.col("_quantity").cast(pl.Int64),
    )

    data = clean.select(
        pl.col("order_id")
        .cast(pl.String)
        .str.replace_all(r"^", "ORD-", literal=False)
        .alias(" Order ID "),
        pl.col("customer").cast(pl.String).alias("Customer_Id"),
        pl.col("product").cast(pl.String).alias("PRODUCT_ID"),
        pl.col("supplier").cast(pl.String).alias("supplier id"),
        pl.col("channel").cast(pl.String).alias("Channel ID"),
        dirty_text("_currency").alias("Currency"),
        pl.col("order_ts").alias("Order TS"),
        pl.col("quantity").cast(pl.String).alias("Quantity"),
        money("_price").alias("unit_price_local"),
        money("_discount").alias("Discount Pct"),
        money("_tax").alias("tax_local"),
        money("_ship").alias("shipping_local"),
        dirty_text("_status").alias("Status"),
        dirty_text("_payment").alias("Payment Method"),
        pl.col("_returned")
        .cast(pl.String)
        .str.to_lowercase()
        .alias("is_returned"),
    )

    # Every column lands as text, which is exactly what the app's CSV reader
    # produces (infer_schema=False) and what makes the Select node's dtype
    # mapping load-bearing.
    dirty = pl.DataFrame(data).with_columns(pl.all().cast(pl.String))
    assert dirty.columns == cfg.RAW_ORDER_COLUMNS, dirty.columns
    return dirty


def duplicate_rows(frame: pl.DataFrame, rate: float) -> pl.DataFrame:
    """Append exact duplicates of randomly chosen rows."""
    import numpy as np

    if rate <= 0:
        return frame
    rng = np.random.default_rng(cfg.RANDOM_SEED + 4)
    extra = int(frame.height * rate)
    picks = rng.integers(0, frame.height, extra)
    dupes = frame[picks]
    combined = pl.concat([frame, dupes], how="vertical")
    # Shuffle so duplicates are not all bunched at the end.
    return combined.with_row_index("__ord").sample(fraction=1.0, shuffle=True, seed=cfg.RANDOM_SEED).drop("__ord")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def generate(scale: str) -> dict[str, Path]:
    counts = cfg.scale_for(scale)
    cfg.ensure_dirs()
    _log(f"scale={scale} orders={counts['orders']:,} customers={counts['customers']:,}")

    started = time.time()

    _log("building dimensions...")
    customers = build_customers(counts["customers"])
    products = build_products(counts["products"])
    suppliers = build_suppliers(counts["suppliers"])
    channels = build_channels()
    fx = build_fx_rates()

    _log(f"building fact table ({counts['orders']:,} rows)...")
    orders = build_orders(
        counts["orders"], counts["customers"], counts["products"], counts["suppliers"]
    )
    _log("injecting duplicates...")
    orders = duplicate_rows(orders, cfg.DUP_RATE)

    written: dict[str, Path] = {}
    targets = [
        ("orders.csv", orders),
        ("customers.csv", customers),
        ("products.csv", products),
        ("suppliers.csv", suppliers),
        ("channels.csv", channels),
        ("fx_rates.csv", fx),
    ]
    for filename, frame in targets:
        path = cfg.data_file(filename)
        frame.write_csv(path)
        size_mb = path.stat().st_size / (1024 * 1024)
        written[filename] = path
        _log(f"  {filename:<18} {frame.height:>12,} rows  {size_mb:9.1f} MB")

    elapsed = time.time() - started
    _log(f"done in {elapsed:.1f}s")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scale",
        default=cfg.DEFAULT_SCALE,
        choices=sorted(cfg.SCALE_PRESETS),
        help="dataset size preset (default: %(default)s)",
    )
    args = parser.parse_args()
    generate(args.scale)


if __name__ == "__main__":
    main()
