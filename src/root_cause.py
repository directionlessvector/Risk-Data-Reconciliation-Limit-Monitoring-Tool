"""
root_cause.py
-------------
Deterministic, fully-explainable root-cause classification, per
Reconciliation & Control Logic Spec, Section 3.

Design principle: every tag must trace back to an explicit, inspectable
condition. If no rule confidently applies, the system says so rather
than forcing a guess (the "Unclassified -- Manual Review" fallback).
This is deliberately rules-based, not ML, because auditability matters
more than predictive sophistication in a risk/compliance context.
"""

import pandas as pd
from datetime import datetime


def classify_root_cause(row: pd.Series, params: dict, run_date: str) -> str:
    """
    Apply the rule table from Control Logic Spec Section 3 to a single
    reconciled row (post break_category classification).
    """
    category = row["break_category"]
    run_dt = datetime.strptime(run_date, "%Y-%m-%d")
    window_days = params["timing_lag_window_days"]

    if category in ("missing_risk_system_only", "missing_front_office_only"):
        # Use whichever side's trade_date is populated
        date_str = row["trade_date_fo"] if category == "missing_risk_system_only" else row["trade_date_rs"]
        trade_dt = datetime.strptime(date_str, "%Y-%m-%d")
        age_days = (run_dt - trade_dt).days

        if age_days <= window_days:
            return "Timing Lag"
        return "Unbooked / Feed Failure - Escalate"

    if category == "value_break":
        pct = row["pct_diff"]
        if pct <= params["value_break_classification"]["stale_price_max_pct"] * 100:
            return "Stale Price / Rate Timing"
        return "Data Entry Error - Escalate"

    if category == "currency_break":
        return "FX / Reference Data Mismatch"

    if category == "clean_match":
        return None  # no break, no root cause needed

    return "Unclassified - Manual Review"


def apply_root_causes(reconciled_df: pd.DataFrame, params: dict, run_date: str) -> pd.DataFrame:
    df = reconciled_df.copy()
    df["root_cause"] = df.apply(lambda r: classify_root_cause(r, params, run_date), axis=1)
    return df


if __name__ == "__main__":
    from normalize import normalize_source
    from reconcile import reconcile
    import json

    fo = normalize_source("../data/front_office_positions.csv", "../config/front_office_mapping.json")
    rs = normalize_source("../data/risk_system_positions.csv", "../config/risk_system_mapping.json")
    params = json.load(open("../config/control_params.json"))

    reconciled = reconcile(fo, rs, params["tolerance_pct"])
    tagged = apply_root_causes(reconciled, params, params["run_date"])

    print(tagged[tagged["break_category"] != "clean_match"][
        ["trade_id", "break_category", "root_cause"]
    ].to_string(index=False))
