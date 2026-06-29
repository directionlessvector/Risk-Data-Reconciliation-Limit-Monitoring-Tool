"""
limits.py
---------
Limit monitoring logic per Reconciliation & Control Logic Spec, Section 4.

Aggregates reconciled exposure (matched, clean-or-tolerated trades) per
counterparty + asset_class, and compares against the limits reference
table. Flags breaches independently of reconciliation breaks -- a trade
can be a clean match and still contribute to a limit breach at the
aggregate level.
"""

import pandas as pd


def check_limits(reconciled_df: pd.DataFrame, limits_df: pd.DataFrame) -> pd.DataFrame:
    """
    Sum reconciled notional per counterparty + asset_class (using the
    Front Office side as the exposure of record for matched/clean trades,
    consistent with reconciled rows having matching or tolerated values),
    then compare against limits.csv.
    """
    # Only include rows that exist on at least one side and aren't a
    # missing-record break (limit monitoring operates on confirmed,
    # reconciled exposure -- not on unconfirmed single-sided trades)
    confirmed = reconciled_df[reconciled_df["_merge"] == "both"].copy()

    # Use Front Office notional as exposure of record for aggregation
    confirmed["exposure_notional"] = confirmed["notional_fo"]
    confirmed["counterparty"] = confirmed["counterparty_fo"]
    confirmed["asset_class"] = confirmed["asset_class_fo"]

    agg = (
        confirmed.groupby(["counterparty", "asset_class"], as_index=False)["exposure_notional"]
        .sum()
        .rename(columns={"exposure_notional": "aggregate_exposure_usd"})
    )

    merged = pd.merge(agg, limits_df, on=["counterparty", "asset_class"], how="left")
    merged["max_notional_usd"] = merged["max_notional_usd"].fillna(float("inf"))

    merged["is_breach"] = merged["aggregate_exposure_usd"] > merged["max_notional_usd"]
    merged["overage_usd"] = (merged["aggregate_exposure_usd"] - merged["max_notional_usd"]).clip(lower=0)
    merged["overage_pct"] = merged.apply(
        lambda r: round(r["overage_usd"] / r["max_notional_usd"] * 100, 2)
        if r["is_breach"] and r["max_notional_usd"] not in (float("inf"), 0) else 0.0,
        axis=1,
    )

    return merged


if __name__ == "__main__":
    from normalize import normalize_source
    from reconcile import reconcile
    import json

    fo = normalize_source("../data/front_office_positions.csv", "../config/front_office_mapping.json")
    rs = normalize_source("../data/risk_system_positions.csv", "../config/risk_system_mapping.json")
    params = json.load(open("../config/control_params.json"))
    limits_df = pd.read_csv("../data/limits.csv")

    reconciled = reconcile(fo, rs, params["tolerance_pct"])
    limit_results = check_limits(reconciled, limits_df)

    print(limit_results.to_string(index=False))
    print("\nBreaches only:")
    print(limit_results[limit_results["is_breach"]].to_string(index=False))
