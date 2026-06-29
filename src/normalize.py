"""
normalize.py
------------
Resolves the core real-world reconciliation problem: different source
systems use different column names, units, and date formats for the
same underlying data.

Design principle (see Data Dictionary & Source Schema Spec, Section 4):
all source-specific knowledge lives in a declarative JSON mapping config,
never hardcoded inside this function. Adding a new source system means
adding a new mapping file -- this module and everything downstream of it
does not change.
"""

import json
import pandas as pd

CANONICAL_COLUMNS = [
    "trade_id", "counterparty", "asset_class", "notional",
    "currency", "trade_date", "source_system",
]


def load_mapping(mapping_path: str) -> dict:
    """Load a source's mapping config from disk."""
    with open(mapping_path, "r") as f:
        return json.load(f)


def normalize_source(raw_csv_path: str, mapping_path: str) -> pd.DataFrame:
    """
    Load a raw source CSV and its mapping config, and return a dataframe
    conforming to the canonical schema.

    Steps (mirrors Data Dictionary Spec, Section 4):
      1. Rename columns per column_map
      2. Apply unit conversions (e.g. millions -> raw units)
      3. Standardize asset_class vocabulary
      4. Parse and reformat trade_date to ISO
      5. Drop source-specific columns not part of the canonical schema
      6. Tag every row with source_system
    """
    mapping = load_mapping(mapping_path)
    df = pd.read_csv(raw_csv_path)

    # 1. Drop source-specific columns that have no canonical equivalent
    drop_cols = [c for c in mapping.get("drop_columns", []) if c in df.columns]
    df = df.drop(columns=drop_cols)

    # 2. Rename columns to canonical names
    df = df.rename(columns=mapping["column_map"])

    # 3. Unit conversions (e.g. Front Office reports notional in millions)
    for field, conv in mapping.get("unit_conversions", {}).items():
        if "multiply_by" in conv:
            df[field] = df[field] * conv["multiply_by"]

    # 4. Standardize asset_class vocabulary across sources
    vocab = mapping.get("asset_class_vocab", {})
    if vocab and "asset_class" in df.columns:
        df["asset_class"] = df["asset_class"].map(vocab).fillna(df["asset_class"])

    # 5. Standardize date format to ISO (YYYY-MM-DD)
    date_fmt = mapping.get("date_format")
    if date_fmt and "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"], format=date_fmt).dt.strftime("%Y-%m-%d")

    # 6. Tag source system (not present in raw files -- added here)
    df["source_system"] = mapping["source_name"]

    # Ensure canonical column order, fail loudly if something's missing
    missing = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Normalized '{mapping['source_name']}' is missing canonical columns: {missing}")

    return df[CANONICAL_COLUMNS].copy()


if __name__ == "__main__":
    # Quick self-test when run directly
    fo = normalize_source("../data/front_office_positions.csv", "../config/front_office_mapping.json")
    rs = normalize_source("../data/risk_system_positions.csv", "../config/risk_system_mapping.json")
    print("Front Office normalized sample:")
    print(fo.head(3).to_string(index=False))
    print("\nRisk System normalized sample:")
    print(rs.head(3).to_string(index=False))
