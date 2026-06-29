"""
commentary.py
-------------
Templated, plain-English commentary generation per Reconciliation &
Control Logic Spec, Section 5.

Deliberately templated rather than free-form generative text: every
sentence is auditable back to its inputs, which matters in a context
where commentary may end up in a stakeholder-facing risk report.
"""

import pandas as pd


def generate_break_commentary(row: pd.Series) -> str:
    """Generate commentary for a single reconciliation break row."""
    category = row["break_category"]
    root_cause = row.get("root_cause")

    if category == "missing_risk_system_only":
        return (
            f"Trade {row['trade_id']} ({row['counterparty_fo']}) present in Front Office only "
            f"as of {row['trade_date_fo']}; {root_cause.lower()}"
            + (", expected to clear within 1 business day." if root_cause == "Timing Lag"
               else " - investigate booking status with source desk.")
        )

    if category == "missing_front_office_only":
        return (
            f"Trade {row['trade_id']} ({row['counterparty_rs']}) present in Risk System only "
            f"as of {row['trade_date_rs']}; {root_cause.lower()}"
            + (", expected to clear within 1 business day." if root_cause == "Timing Lag"
               else " - investigate booking status with source desk.")
        )

    if category == "value_break":
        pct = row["pct_diff"]
        if root_cause == "Stale Price / Rate Timing":
            return (
                f"Notional variance of {pct}% identified for trade {row['trade_id']} "
                f"({row['counterparty_fo']}); within range consistent with rate timing "
                f"differences between source systems."
            )
        return (
            f"Material notional variance of {pct}% identified for trade {row['trade_id']} "
            f"({row['counterparty_fo']}); escalated for data entry verification per SOP."
        )

    if category == "currency_break":
        return (
            f"Currency mismatch identified for trade {row['trade_id']} ({row['counterparty_fo']}): "
            f"Front Office reports {row['currency_fo']}, Risk System reports {row['currency_rs']}; "
            f"flagged for FX/reference data review."
        )

    return ""  # clean_match -> no commentary needed


def generate_limit_breach_commentary(row: pd.Series) -> str:
    """Generate commentary for a single limit breach row."""
    return (
        f"Aggregate {row['asset_class']} exposure to {row['counterparty']} of "
        f"${row['aggregate_exposure_usd']:,.0f} exceeds approved limit of "
        f"${row['max_notional_usd']:,.0f} by {row['overage_pct']}%; escalated to Risk Coverage."
    )


if __name__ == "__main__":
    from normalize import normalize_source
    from reconcile import reconcile
    from root_cause import apply_root_causes
    from limits import check_limits
    import json

    fo = normalize_source("../data/front_office_positions.csv", "../config/front_office_mapping.json")
    rs = normalize_source("../data/risk_system_positions.csv", "../config/risk_system_mapping.json")
    params = json.load(open("../config/control_params.json"))
    limits_df = pd.read_csv("../data/limits.csv")

    reconciled = reconcile(fo, rs, params["tolerance_pct"])
    tagged = apply_root_causes(reconciled, params, params["run_date"])
    breaks_only = tagged[tagged["break_category"] != "clean_match"].copy()
    breaks_only["commentary"] = breaks_only.apply(generate_break_commentary, axis=1)

    print("--- Break commentary ---")
    for _, row in breaks_only.iterrows():
        print(f"[{row['trade_id']}] {row['commentary']}")

    limit_results = check_limits(reconciled, limits_df)
    breaches = limit_results[limit_results["is_breach"]].copy()
    breaches["commentary"] = breaches.apply(generate_limit_breach_commentary, axis=1)

    print("\n--- Limit breach commentary ---")
    for _, row in breaches.iterrows():
        print(f"[{row['counterparty']} / {row['asset_class']}] {row['commentary']}")
