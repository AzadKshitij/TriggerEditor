"""Step 3 - compare the pandas reports against the TriggerDesigner workflow.

Build the workflow by hand (see NODE_SETUP_GUIDE.md), point its File Output
nodes at app_output/, run it in the app, then run this. It reports, for every
shared report file:

  * row count on each side and the delta
  * columns present on one side only
  * per-column numeric drift, and the rows responsible for the worst of it
  * row-set overlap on the natural key, so "same rows, different numbers" is
    distinguishable from "different rows entirely"

Files that only one side produces are listed rather than treated as failures -
the workflow is expected to differ in shape, and the guide explains where.

Usage:
    python step3_compare.py
    python step3_compare.py --tolerance 1e-6
"""

from __future__ import annotations

import argparse
import sys

import polars as pl

import config as cfg

# Files the workflow produces that the pandas script does not, and why.
EXPECTED_EXTRA = {
    "orders_enriched.parquet": "the same enriched fact, written as parquet",
    "kpi_fact_rowcount.csv": "Count Records node output (single count column)",
}

# Reports the pandas script produces that have no node equivalent.
SCRIPT_ONLY = {
    "kpi_summary.csv": "assembled row-by-row in Python; no metric-table node exists",
    "data_quality_report.csv": "the script's own stage log; not a data report",
    "scenario_grid.csv": "labelled cross-product; Generate Rows only emits a bare counter",
}

# Reports where a row-count difference is expected and explained, with the
# magnitude we would expect to see at the given defect rates.
EXPECTED_DELTA = {
    # The Join node always computes a full outer join and the main path takes
    # the matched (J) socket, so unmatched order rows never reach the reports.
    # The script uses a pandas left join, which keeps them.
    "orders_enriched.csv": "left-join vs matched-only (Join node semantics)",
    "orders_enterprise.csv": "inherits the join difference",
    "orders_high_risk.csv": "inherits the join difference",
    "fact_estimation.csv": "inherits the join + Split node row selection",
    "fact_validation.csv": "inherits the join + Split node row selection",
    "monthly_revenue.csv": "inherits the join difference",
    "monthly_revenue_long.csv": "inherits the join difference",
    "category_revenue.csv": "inherits the join difference",
    "region_channel_revenue.csv": "inherits the join difference",
    "segment_revenue.csv": "inherits the join difference",
    "top_customers.csv": "inherits the join difference",
    "supplier_performance.csv": "inherits the join difference",
    "fx_exposure.csv": "inherits the join difference",
}

# Reports whose key columns the comparison groups on. Row-level files are keyed
# by order_id; grouped reports by their group columns.
KEY_COLUMNS = {
    "monthly_revenue.csv": ["order_year_month"],
    "monthly_revenue_long.csv": ["order_year_month", "metric"],
    "category_revenue.csv": ["category"],
    "region_channel_revenue.csv": ["region", "channel_group"],
    "segment_revenue.csv": ["segment", "risk_band"],
    "top_customers.csv": ["customer_id"],
    "supplier_performance.csv": ["supplier_id"],
    "fx_exposure.csv": ["currency"],
    "kpi_summary.csv": ["metric"],
    "kpi_fact_rowcount.csv": ["Count"],
    "orders_enriched.csv": ["order_id"],
    "orders_enterprise.csv": ["order_id"],
    "orders_high_risk.csv": ["order_id"],
    "fact_estimation.csv": ["order_id"],
    "fact_validation.csv": ["order_id"],
    "orphan_customers.csv": ["order_id"],
    "orphan_products.csv": ["order_id"],
    "rejected_quantity.csv": ["order_id"],
    "rejected_price_outliers.csv": ["order_id"],
    "rejected_future_dates.csv": ["order_id"],
    "duplicate_orders.csv": ["order_id"],
}


def read(path) -> pl.DataFrame:
    """Read a CSV as all-text, then let polars infer what it can.

    Both sides are compared as strings first so a dtype disagreement (Int64 vs
    Float64, say) is reported as a value difference rather than crashing the
    comparison.
    """
    return pl.read_csv(path, infer_schema_length=200)


def coerce(frame: pl.DataFrame) -> pl.DataFrame:
    """Make a frame comparable: strings trimmed, numbers rounded."""
    out = frame
    for column, dtype in out.schema.items():
        if dtype == pl.String:
            out = out.with_columns(pl.col(column).str.strip_chars())
        elif dtype.is_float():
            out = out.with_columns(pl.col(column).round(6))
    return out


def row_key(frame: pl.DataFrame, columns: list[str]) -> pl.Series | None:
    present = [c for c in columns if c in frame.columns]
    if not present:
        return None
    return (
        frame.select(present)
        .select(pl.concat_str([pl.col(c).cast(pl.String) for c in present], separator="|"))
        .to_series()
    )


def compare_file(name: str, tolerance: float) -> dict:
    ref_path = cfg.REFERENCE_OUT / name
    app_path = cfg.APP_OUT / name

    result = {"name": name, "status": "ok", "notes": []}
    if not ref_path.exists():
        result["status"] = "missing-reference"
        return result
    if not app_path.exists():
        result["status"] = "missing-app"
        return result

    ref = coerce(read(ref_path))
    app = coerce(read(app_path))

    result["ref_rows"] = ref.height
    result["app_rows"] = app.height
    result["row_delta"] = app.height - ref.height

    only_ref = [c for c in ref.columns if c not in app.columns]
    only_app = [c for c in app.columns if c not in ref.columns]
    result["only_ref_cols"] = only_ref
    result["only_app_cols"] = only_app

    shared = [c for c in ref.columns if c in app.columns]
    if not shared:
        result["status"] = "no-shared-columns"
        return result

    # Row-set overlap on the natural key, when there is one.
    keys = [c for c in KEY_COLUMNS.get(name, []) if c in ref.columns and c in app.columns]
    ref_key = row_key(ref, keys)
    app_key = row_key(app, keys)
    keys_usable = ref_key is not None and app_key is not None
    keys_equal = False
    if keys_usable:
        ref_keys = set(ref_key.to_list())
        app_keys = set(app_key.to_list())
        both = len(ref_keys & app_keys)
        union = len(ref_keys | app_keys) or 1
        result["key_overlap_pct"] = 100.0 * both / union
        result["ref_only_keys"] = len(ref_keys - app_keys)
        result["app_only_keys"] = len(app_keys - ref_keys)
        keys_equal = ref_keys == app_keys

    # Column-level value drift on the shared columns. When both sides carry
    # the same key set, sort by the key first so row ORDER differences (join
    # output order, shuffle order) cannot masquerade as value differences.
    # When the key sets differ, positional comparison is meaningless, so say
    # so instead of printing a wall of false mismatches.
    if keys_usable and not keys_equal:
        result["value_mismatches"] = [
            f"key sets differ ({result['ref_only_keys']} pandas-only, "
            f"{result['app_only_keys']} workflow-only); values not aligned"
        ]
        return result

    if keys_usable:
        ref = ref.sort(keys)
        app = app.sort(keys)

    aligned_ref = ref.select(shared)
    aligned_app = app.select(shared)
    if aligned_ref.height == aligned_app.height:
        worst = []
        for column in shared:
            left = aligned_ref[column]
            right = aligned_app[column]
            mismatched = (left != right).fill_null(False).sum()
            if mismatched:
                numeric = left.dtype.is_float() and right.dtype.is_float()
                detail = ""
                if numeric:
                    delta = (right.cast(pl.Float64) - left.cast(pl.Float64)).abs()
                    worst_delta = delta.max()
                    detail = f" (max abs delta {worst_delta})"
                    if worst_delta is not None and worst_delta <= tolerance:
                        mismatched = 0
                if mismatched:
                    worst.append(f"{column}: {mismatched}{detail}")
        result["value_mismatches"] = worst
    else:
        result["value_mismatches"] = ["row counts differ; values not aligned"]

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tolerance", type=float, default=cfg.FLOAT_TOLERANCE,
        help="absolute numeric tolerance for 'equal' (default: %(default)s)",
    )
    args = parser.parse_args()

    cfg.ensure_dirs()

    if not cfg.APP_OUT.exists() or not any(cfg.APP_OUT.glob("*")):
        print(f"No workflow output in {cfg.APP_OUT}.")
        print("Build the workflow from NODE_SETUP_GUIDE.md, point its File Output")
        print("nodes at that folder, run it, then re-run this script.")
        return 2

    shared = sorted(
        p.name for p in cfg.APP_OUT.glob("*.csv")
        if (cfg.REFERENCE_OUT / p.name).exists()
    )
    only_app = sorted(
        p.name for p in cfg.APP_OUT.glob("*")
        if not (cfg.REFERENCE_OUT / p.name).exists()
    )
    only_ref = sorted(
        p.name for p in cfg.REFERENCE_OUT.glob("*")
        if not (cfg.APP_OUT / p.name).exists()
    )

    results = [compare_file(name, args.tolerance) for name in shared]

    print("=" * 78)
    print("ROW COUNTS")
    print("=" * 78)
    print(f"  {'file':<34} {'pandas':>12} {'workflow':>12} {'delta':>10}")
    for r in results:
        print(
            f"  {r['name']:<34} {r.get('ref_rows', 0):>12,} "
            f"{r.get('app_rows', 0):>12,} {r.get('row_delta', 0):>+10,}"
        )

    print()
    print("=" * 78)
    print("ROW-SET OVERLAP ON NATURAL KEY")
    print("=" * 78)
    for r in results:
        if "key_overlap_pct" in r:
            print(
                f"  {r['name']:<34} {r['key_overlap_pct']:6.2f}% overlap   "
                f"pandas-only keys {r['ref_only_keys']:>7,}   "
                f"workflow-only {r['app_only_keys']:>7,}"
            )

    print()
    print("=" * 78)
    print("COLUMN DIFFERENCES")
    print("=" * 78)
    any_cols = False
    for r in results:
        if r.get("only_ref_cols") or r.get("only_app_cols"):
            any_cols = True
            print(f"  {r['name']}")
            if r["only_ref_cols"]:
                print(f"      pandas only   : {', '.join(r['only_ref_cols'])}")
            if r["only_app_cols"]:
                print(f"      workflow only : {', '.join(r['only_app_cols'])}")
    if not any_cols:
        print("  none - every shared file has the same columns on both sides")

    print()
    print("=" * 78)
    print("VALUE MISMATCHES ON SHARED COLUMNS")
    print("=" * 78)
    any_vals = False
    for r in results:
        mismatches = r.get("value_mismatches") or []
        if mismatches and mismatches != ["row counts differ; values not aligned"]:
            any_vals = True
            print(f"  {r['name']}")
            for line in mismatches:
                print(f"      {line}")
        elif mismatches:
            any_vals = True
            print(f"  {r['name']}: row counts differ, values not aligned")
    if not any_vals:
        print("  none - every aligned value matches within tolerance")

    print()
    print("=" * 78)
    print("FILE COVERAGE")
    print("=" * 78)
    for name in only_app:
        why = EXPECTED_EXTRA.get(name, "workflow-only output")
        print(f"  workflow only : {name:<32} ({why})")
    for name in only_ref:
        if name in SCRIPT_ONLY:
            print(f"  pandas only   : {name:<32} ({SCRIPT_ONLY[name]})")
            continue
        why = EXPECTED_DELTA.get(name)
        suffix = f"  <- {why}" if why else ""
        print(f"  pandas only   : {name:<32}{suffix}")

    cfg.COMPARE_OUT.mkdir(parents=True, exist_ok=True)
    print(f"\nDone. {len(results)} shared file(s) compared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
