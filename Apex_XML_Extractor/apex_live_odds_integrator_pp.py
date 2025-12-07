# apex_live_odds_integrator_pp.py
# Version: 1.1 (Dec 1, 2025)
# FIXED: No longer lowercases all column names, preserves CPR_Composite etc.

import pandas as pd
import sys
import traceback


def load_csv(path: str) -> pd.DataFrame:
    """Load CSV with safe error handling."""
    try:
        return pd.read_csv(path)
    except Exception as e:
        print(f"❌ ERROR loading {path}: {e}")
        traceback.print_exc()
        sys.exit(1)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preserve capitalization but still remove leading/trailing spaces
    and internal spaces. DO NOT lowercase — this breaks other modules.
    """
    df.columns = [c.strip().replace(" ", "_") for c in df.columns]
    return df


def merge_live_odds(base: pd.DataFrame, live: pd.DataFrame) -> pd.DataFrame:
    """
    Merge live odds onto CPR file using 'program' column as key.
    """

    # Validate program column exists in both
    if "program" not in base.columns:
        raise ValueError("Base CPR file missing required column: 'program'")
    if "program" not in live.columns:
        raise ValueError("Live odds file missing required column: 'program'")

    # Merge
    merged = pd.merge(base, live, on="program", how="left")

    # Check for missing odds (optional)
    if merged["live_odds_(dec)"].isna().sum() > 0:
        print("⚠️ WARNING: Some horses had no matching live odds.")

    return merged


def main():
    print("📄 Loading base CPR file → apex_output_cpr.csv")
    base = load_csv("apex_output_cpr.csv")
    base = normalize_columns(base)

    print("📄 Loading live odds → live_odds.csv")
    live = load_csv("live_odds.csv")
    live = normalize_columns(live)

    print("🔧 Merging live odds into CPR data...")
    out = merge_live_odds(base, live)

    print("💾 Saving → apex_output_live.csv")
    out.to_csv("apex_output_live.csv", index=False)

    print("✅ Live odds integrated successfully.")


if __name__ == "__main__":
    main()
