"""
run_pipeline.py
----------------
Main entry point. Executes the full pipeline in the order defined by
Reconciliation & Control Logic Spec, Section 7:

  1. Load mapping configs
  2. Normalize each source into canonical schema
  3. Reconcile (match + classify breaks)
  4. Run limit monitoring
  5. Apply root-cause classification
  6. Generate commentary
  7. Write issue log + Excel summary report
  8. (Downstream, outside Python) Tableau dashboard reads the issue log

Usage:
    python run_pipeline.py
"""

import json
import time
import pandas as pd
from pathlib import Path

from normalize import normalize_source
from reconcile import reconcile
from root_cause import apply_root_causes
from limits import check_limits
from commentary import generate_break_commentary, generate_limit_breach_commentary
from issue_log import build_issue_log
from report import write_excel_report

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
CONFIG = BASE / "config"
OUTPUT = BASE / "output"


def run():
    start = time.time()
    print("=" * 70)
    print("RISK DATA RECONCILIATION & LIMIT MONITORING PIPELINE")
    print("=" * 70)

    params = json.load(open(CONFIG / "control_params.json"))
    run_date = params["run_date"]

    # --- Step 1-2: Ingest + Normalize ---------------------------------
    print("\n[1/6] Normalizing source files into canonical schema...")
    fo = normalize_source(str(DATA / "front_office_positions.csv"), str(CONFIG / "front_office_mapping.json"))
    rs = normalize_source(str(DATA / "risk_system_positions.csv"), str(CONFIG / "risk_system_mapping.json"))
    print(f"   Front Office: {len(fo)} records | Risk System: {len(rs)} records")

    # --- Step 3: Reconcile --------------------------------------------
    print("\n[2/6] Reconciling records across sources...")
    reconciled = reconcile(fo, rs, params["tolerance_pct"])
    counts = reconciled["break_category"].value_counts()
    for cat, n in counts.items():
        print(f"   {cat}: {n}")

    # --- Step 4: Limit monitoring --------------------------------------
    print("\n[3/6] Checking exposures against risk limits...")
    limits_df = pd.read_csv(DATA / "limits.csv")
    limit_results = check_limits(reconciled, limits_df)
    breaches = limit_results[limit_results["is_breach"]].copy()
    print(f"   {len(breaches)} limit breach(es) identified out of {len(limit_results)} counterparty/asset_class books")

    # --- Step 5: Root-cause classification -----------------------------
    print("\n[4/6] Applying root-cause classification...")
    tagged = apply_root_causes(reconciled, params, run_date)
    breaks_only = tagged[tagged["break_category"] != "clean_match"].copy()

    # --- Step 6: Commentary generation ---------------------------------
    print("\n[5/6] Generating stakeholder commentary...")
    breaks_only["commentary"] = breaks_only.apply(generate_break_commentary, axis=1)
    breaches["commentary"] = breaches.apply(generate_limit_breach_commentary, axis=1)

    # --- Step 7: Issue log + Excel report -------------------------------
    print("\n[6/6] Writing issue log and summary report...")
    OUTPUT.mkdir(exist_ok=True)
    issue_log_df = build_issue_log(breaks_only, breaches, run_date)
    issue_log_path = OUTPUT / "issue_log.csv"
    issue_log_df.to_csv(issue_log_path, index=False)
    print(f"   Issue log written: {issue_log_path}  ({len(issue_log_df)} rows)")

    report_path = OUTPUT / "risk_reconciliation_report.xlsx"
    write_excel_report(
        report_path=report_path,
        reconciled=reconciled,
        breaks_only=breaks_only,
        limit_results=limit_results,
        issue_log_df=issue_log_df,
        run_date=run_date,
        fo_count=len(fo),
        rs_count=len(rs),
    )
    print(f"   Excel report written: {report_path}")

    elapsed = time.time() - start
    print("\n" + "=" * 70)
    print(f"PIPELINE COMPLETE in {elapsed:.2f} seconds")
    print(f"  Total records reconciled : {len(reconciled)}")
    print(f"  Clean matches             : {counts.get('clean_match', 0)}")
    print(f"  Reconciliation breaks     : {len(breaks_only)}")
    print(f"  Limit breaches            : {len(breaches)}")
    print("=" * 70)

    return {
        "reconciled": reconciled,
        "breaks_only": breaks_only,
        "limit_results": limit_results,
        "breaches": breaches,
        "issue_log": issue_log_df,
    }


if __name__ == "__main__":
    run()
