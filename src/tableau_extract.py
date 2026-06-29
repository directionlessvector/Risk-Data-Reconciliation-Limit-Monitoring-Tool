"""
tableau_extract.py
-------------------
Produces a single flat, Tableau-friendly CSV from the pipeline outputs.
This is the file referenced in the PRD as feeding the Tableau dashboard
(breach volume over time, breach type distribution, breach status).

Run standalone after run_pipeline.py, or import build_tableau_extract()
directly.
"""

import pandas as pd
from pathlib import Path


def build_tableau_extract(issue_log_df: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    """
    Flatten the issue log into a Tableau-ready shape: one row per issue,
    with a few derived columns that make filtering/grouping easier in
    Tableau without needing calculated fields for the basics.
    """
    df = issue_log_df.copy()
    df["is_limit_breach"] = df["break_type"] == "limit_breach"
    df["is_reconciliation_break"] = ~df["is_limit_breach"]
    df["severity"] = df["root_cause"].apply(
        lambda x: "High" if isinstance(x, str) and "Escalate" in x
        else ("High" if isinstance(x, str) and "breach" in x.lower() else "Low")
    )
    df.to_csv(output_path, index=False)
    return df


if __name__ == "__main__":
    OUTPUT = Path(__file__).resolve().parent.parent / "output"
    issue_log_df = pd.read_csv(OUTPUT / "issue_log.csv")
    extract_path = OUTPUT / "tableau_extract.csv"
    extract = build_tableau_extract(issue_log_df, extract_path)
    print(f"Tableau extract written: {extract_path} ({len(extract)} rows)")
    print(extract[["break_id", "break_type", "severity", "status"]].to_string(index=False))
