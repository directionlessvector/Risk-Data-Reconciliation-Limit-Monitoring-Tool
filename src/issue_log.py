"""
issue_log.py
------------
Builds the auditable issue log per Reconciliation & Control Logic Spec,
Section 6. Combines reconciliation breaks and limit breaches into a
single status-tracked log.
"""

import pandas as pd


ISSUE_LOG_COLUMNS = [
    "break_id", "trade_id", "break_type", "root_cause",
    "commentary", "status", "date_identified",
]


def build_issue_log(breaks_df: pd.DataFrame, breaches_df: pd.DataFrame, run_date: str) -> pd.DataFrame:
    """Combine break-level and breach-level commentary into one issue log."""
    rows = []

    for i, row in breaks_df.reset_index(drop=True).iterrows():
        rows.append({
            "break_id": f"BRK-{run_date.replace('-', '')}-{i+1:03d}",
            "trade_id": row["trade_id"],
            "break_type": row["break_category"],
            "root_cause": row["root_cause"],
            "commentary": row["commentary"],
            "status": "Open",
            "date_identified": run_date,
        })

    offset = len(rows)
    for i, row in breaches_df.reset_index(drop=True).iterrows():
        rows.append({
            "break_id": f"LIM-{run_date.replace('-', '')}-{i+1:03d}",
            "trade_id": None,
            "break_type": "limit_breach",
            "root_cause": f"{row['counterparty']} / {row['asset_class']} exposure breach",
            "commentary": row["commentary"],
            "status": "Escalated",  # limit breaches default to Escalated per control policy
            "date_identified": run_date,
        })

    return pd.DataFrame(rows, columns=ISSUE_LOG_COLUMNS)
