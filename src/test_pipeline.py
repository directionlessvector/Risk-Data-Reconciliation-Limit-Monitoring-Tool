"""
test_pipeline.py
-----------------
Lightweight tests validating that the core control logic behaves as
specified in the Reconciliation & Control Logic Spec. Not exhaustive --
covers the rules an interviewer is most likely to probe.

Run with: python -m pytest test_pipeline.py -v
       or: python test_pipeline.py
"""

import json
import pandas as pd
from pathlib import Path

from normalize import normalize_source
from reconcile import reconcile
from root_cause import apply_root_causes, classify_root_cause
from limits import check_limits

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
CONFIG = BASE / "config"

params = json.load(open(CONFIG / "control_params.json"))


def _get_reconciled():
    fo = normalize_source(str(DATA / "front_office_positions.csv"), str(CONFIG / "front_office_mapping.json"))
    rs = normalize_source(str(DATA / "risk_system_positions.csv"), str(CONFIG / "risk_system_mapping.json"))
    return reconcile(fo, rs, params["tolerance_pct"])


def test_normalization_produces_canonical_schema():
    fo = normalize_source(str(DATA / "front_office_positions.csv"), str(CONFIG / "front_office_mapping.json"))
    rs = normalize_source(str(DATA / "risk_system_positions.csv"), str(CONFIG / "risk_system_mapping.json"))
    expected_cols = {"trade_id", "counterparty", "asset_class", "notional", "currency", "trade_date", "source_system"}
    assert set(fo.columns) == expected_cols
    assert set(rs.columns) == expected_cols


def test_unit_conversion_applied_correctly():
    fo = normalize_source(str(DATA / "front_office_positions.csv"), str(CONFIG / "front_office_mapping.json"))
    # TR10001 raw is 5.0 (millions) -> should become 5,000,000
    row = fo[fo["trade_id"] == "TR10001"].iloc[0]
    assert row["notional"] == 5_000_000


def test_date_formats_normalized_to_iso():
    fo = normalize_source(str(DATA / "front_office_positions.csv"), str(CONFIG / "front_office_mapping.json"))
    row = fo[fo["trade_id"] == "TR10001"].iloc[0]
    assert row["trade_date"] == "2026-06-10"  # raw was 10/06/2026 (DD/MM/YYYY)


def test_missing_record_detected():
    reconciled = _get_reconciled()
    row = reconciled[reconciled["trade_id"] == "TR10004"].iloc[0]
    assert row["break_category"] == "missing_risk_system_only"


def test_value_break_within_tolerance_flagged():
    reconciled = _get_reconciled()
    row = reconciled[reconciled["trade_id"] == "TR10009"].iloc[0]
    assert row["break_category"] == "value_break"
    assert row["pct_diff"] == 3.0


def test_clean_match_for_identical_trades():
    reconciled = _get_reconciled()
    row = reconciled[reconciled["trade_id"] == "TR10001"].iloc[0]
    assert row["break_category"] == "clean_match"


def test_currency_break_detected():
    reconciled = _get_reconciled()
    row = reconciled[reconciled["trade_id"] == "TR10014"].iloc[0]
    assert row["break_category"] == "currency_break"


def test_root_cause_stale_price_vs_data_entry_error():
    reconciled = _get_reconciled()
    tagged = apply_root_causes(reconciled, params, params["run_date"])
    stale = tagged[tagged["trade_id"] == "TR10009"].iloc[0]
    error = tagged[tagged["trade_id"] == "TR10017"].iloc[0]
    assert stale["root_cause"] == "Stale Price / Rate Timing"
    assert error["root_cause"] == "Data Entry Error - Escalate"


def test_root_cause_unclassified_fallback_exists():
    # Construct a synthetic row that matches no rule, confirm graceful fallback
    fake_row = pd.Series({"break_category": "some_unhandled_category"})
    result = classify_root_cause(fake_row, params, params["run_date"])
    assert result == "Unclassified - Manual Review"


def test_limit_breach_detected_for_acme_fx():
    reconciled = _get_reconciled()
    limits_df = pd.read_csv(DATA / "limits.csv")
    result = check_limits(reconciled, limits_df)
    acme = result[(result["counterparty"] == "Acme Capital LLC") & (result["asset_class"] == "FX")].iloc[0]
    assert acme["is_breach"] == True
    assert acme["aggregate_exposure_usd"] == 15_600_000


def test_no_breach_for_within_limit_counterparty():
    reconciled = _get_reconciled()
    limits_df = pd.read_csv(DATA / "limits.csv")
    result = check_limits(reconciled, limits_df)
    delta = result[result["counterparty"] == "Delta Square Investments"].iloc[0]
    assert delta["is_breach"] == False


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests")
