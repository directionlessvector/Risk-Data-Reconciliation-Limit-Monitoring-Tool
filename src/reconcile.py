"""
reconcile.py
------------
Matches normalized records across two sources on trade_id and classifies
each pair into a break category, per Reconciliation & Control Logic Spec,
Section 2.

Break categories produced:
  - missing_front_office_only
  - missing_risk_system_only
  - value_break
  - currency_break
  - clean_match
"""

import pandas as pd


def reconcile(fo_df: pd.DataFrame, rs_df: pd.DataFrame, tolerance_pct: float) -> pd.DataFrame:
    """
    Outer-join Front Office and Risk System on trade_id, then classify
    each row into exactly one break category.

    Returns a dataframe with one row per trade_id (union of both sources)
    and columns describing both sides plus the resulting classification.
    """
    fo = fo_df.add_suffix("_fo")
    rs = rs_df.add_suffix("_rs")
    fo = fo.rename(columns={"trade_id_fo": "trade_id"})
    rs = rs.rename(columns={"trade_id_rs": "trade_id"})

    merged = pd.merge(fo, rs, on="trade_id", how="outer", indicator=True)

    def classify(row):
        if row["_merge"] == "left_only":
            return "missing_risk_system_only"
        if row["_merge"] == "right_only":
            return "missing_front_office_only"

        fo_notional, rs_notional = row["notional_fo"], row["notional_rs"]
        pct_diff = abs(fo_notional - rs_notional) / fo_notional if fo_notional else 0.0

        if pct_diff > tolerance_pct:
            return "value_break"
        if row["currency_fo"] != row["currency_rs"]:
            return "currency_break"
        return "clean_match"

    merged["break_category"] = merged.apply(classify, axis=1)

    def pct_diff_safe(row):
        if row["_merge"] != "both":
            return None
        fo_notional, rs_notional = row["notional_fo"], row["notional_rs"]
        return round(abs(fo_notional - rs_notional) / fo_notional * 100, 2) if fo_notional else 0.0

    merged["pct_diff"] = merged.apply(pct_diff_safe, axis=1)

    return merged


if __name__ == "__main__":
    from normalize import normalize_source
    import json

    fo = normalize_source("../data/front_office_positions.csv", "../config/front_office_mapping.json")
    rs = normalize_source("../data/risk_system_positions.csv", "../config/risk_system_mapping.json")
    params = json.load(open("../config/control_params.json"))

    result = reconcile(fo, rs, params["tolerance_pct"])
    print(result["break_category"].value_counts())
    print("\nNon-clean rows:")
    print(result[result["break_category"] != "clean_match"][
        ["trade_id", "break_category", "pct_diff", "currency_fo", "currency_rs"]
    ].to_string(index=False))
