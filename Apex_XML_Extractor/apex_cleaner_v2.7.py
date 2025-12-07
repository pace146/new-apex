# apex_cleaner_v2.7.py
# Apex CPR Cleaner — PP-integrated (Option A2: Balanced influence)
# ---------------------------------------------------------------
# - Loads apex_output.csv (from extractor v2.0+ with ppdata_list)
# - Derives PP-based features (best/avg finals & LQ, trend, early/late index, avg BL)
# - Computes PP_Delta and (if CPR_Composite exists) applies a balanced adjustment
# - Writes output CSV (and gracefully skips XLSX if openpyxl isn’t installed)

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def robust_z(values, clip=3.0):
    x = np.array(values, dtype=float)
    med = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - med))
    if not np.isfinite(mad) or mad == 0:
        mad = 1.0
    z = (x - med) / (1.4826 * mad)
    return np.clip(z, -clip, clip)


def safe_json_list(x):
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        x = x.strip()
        if x.startswith("[") and x.endswith("]"):
            try:
                return json.loads(x)
            except Exception:
                return []
    return []


def collect_numeric_series(pp_list, candidate_tags):
    """Return a newest-first numeric series (floats) for the first matching tag per pp row."""
    vals = []
    for pp in pp_list:
        if not isinstance(pp, dict):
            continue
        val = None
        for tag in candidate_tags:
            if tag in pp and pp[tag] not in (None, "", "NA"):
                val = pp[tag]
                break
        if val is None:
            continue
        try:
            vals.append(float(val))
        except Exception:
            # try times like "1:53.4"
            s = str(val).strip()
            if ":" in s:
                try:
                    m, sec = s.split(":")
                    vals.append(int(m) * 60 + float(sec))
                except Exception:
                    pass
    return vals


def avg_last(vals, n):
    if not vals:
        return np.nan
    take = vals[:n]
    return float(np.mean(take)) if take else np.nan


def best_last(vals, n, is_time=True):
    if not vals:
        return np.nan
    take = vals[:n]
    if not take:
        return np.nan
    return float(np.min(take) if is_time else np.max(take))


def trend_improving_times(vals, n_short=3, n_prev=3):
    """
    For time-series where lower is better (e.g., seconds):
    trend = prev_avg - short_avg  (positive = improving/faster)
    """
    if len(vals) < (n_short + n_prev):
        return np.nan
    short = np.mean(vals[:n_short])
    prev = np.mean(vals[n_short:n_short + n_prev])
    if not np.isfinite(short) or not np.isfinite(prev):
        return np.nan
    return float(prev - short)


def compute_pp_features(df):
    """
    Reads ppdata_list for each row and adds:
    - pp_best_final3, pp_avg_final3
    - pp_best_lq3,   pp_avg_lq3,   pp_lq_trend
    - pp_early_idx,  pp_late_idx
    - pp_avg_bl3
    """
    # Tag maps (cover your feeds: DTN / WBS / M1)
    Q1_TAGS = ("hrse_tm1qc", "q1", "lead_tm1qc")
    Q2_TAGS = ("hrse_tm2qc", "q2", "lead_tm2qc")
    Q3_TAGS = ("hrse_tm3qc", "q3", "lead_tm3qc")
    LQ_TAGS = ("hrse_tm4qc", "lq", "lastquarter", "lead_tm4qc")
    FN_TAGS = ("hrse_tmfnc", "final_time", "time", "race_time", "finishtime")
    BL_TAGS = ("bl", "beatenlengths", "lengths_back", "call_st_lb")

    best_final3 = []
    avg_final3 = []
    best_lq3 = []
    avg_lq3 = []
    lq_tr = []
    early_idx = []
    late_idx = []
    avg_bl3 = []

    # iterate rows
    for _, row in df.iterrows():
        pp_list = safe_json_list(row.get("ppdata_list"))

        fn_series = collect_numeric_series(pp_list, FN_TAGS)
        lq_series = collect_numeric_series(pp_list, LQ_TAGS)
        q1_series = collect_numeric_series(pp_list, Q1_TAGS)
        q2_series = collect_numeric_series(pp_list, Q2_TAGS)
        q3_series = collect_numeric_series(pp_list, Q3_TAGS)
        bl_series = collect_numeric_series(pp_list, BL_TAGS)

        # newest-first is assumed; if your feed is oldest-first, reverse here:
        # fn_series = list(reversed(fn_series))

        best_final3.append(best_last(fn_series, 3, is_time=True))
        avg_final3.append(avg_last(fn_series, 3))

        best_lq3.append(best_last(lq_series, 3, is_time=True))
        avg_lq3.append(avg_last(lq_series, 3))
        lq_tr.append(trend_improving_times(lq_series, 3, 3))

        # Early/Late speed indices: lower times are better → invert sign so "bigger is better"
        e_parts = [v for v in (avg_last(q1_series, 3), avg_last(q2_series, 3)) if np.isfinite(v)]
        l_parts = [v for v in (avg_last(q3_series, 3), avg_last(lq_series, 3)) if np.isfinite(v)]
        e_idx = -float(np.mean(e_parts)) if e_parts else np.nan
        l_idx = -float(np.mean(l_parts)) if l_parts else np.nan

        early_idx.append(e_idx)
        late_idx.append(l_idx)
        avg_bl3.append(avg_last(bl_series, 3))

    df["pp_best_final3"] = best_final3
    df["pp_avg_final3"] = avg_final3
    df["pp_best_lq3"] = best_lq3
    df["pp_avg_lq3"] = avg_lq3
    df["pp_lq_trend"] = lq_tr
    df["pp_early_idx"] = early_idx
    df["pp_late_idx"] = late_idx
    df["pp_avg_bl3"] = avg_bl3
    return df


def apply_pp_to_cpr(df, mode="A2"):
    """
    Option A2 (balanced): build PP_Delta from z-scored features and add to CPR_Composite if present.
    """
    feats = {
        "pp_best_final3": 0.30,  # better (lower secs) → higher z after robust_z
        "pp_avg_lq3":     0.30,
        "pp_lq_trend":    0.20,  # positive = improving
        "pp_late_idx":    0.20,  # bigger is better (already inverted)
    }

    # z-score features (robust)
    zmap = {}
    for k in feats:
        zmap[k] = robust_z(df[k].values) if k in df.columns else np.zeros(len(df))

    # small penalty for avg beaten lengths (higher BL is worse)
    bl_pen = robust_z(df["pp_avg_bl3"].values) if "pp_avg_bl3" in df.columns else np.zeros(len(df))

    combo = np.zeros(len(df), dtype=float)
    for k, w in feats.items():
        combo += w * zmap[k]
    combo -= 0.15 * bl_pen

    # scale to CPR points; cap for safety
    pp_delta = 4.0 * combo  # ~balanced; change to 2.5 (conservative) or 6.0 (aggressive)
    pp_delta = np.clip(pp_delta, -10, 10)
    df["PP_Delta"] = pp_delta

    # Only adjust if CPR_Composite exists already (keeps this file drop-in safe)
    if "CPR_Composite" in df.columns:
        base = pd.to_numeric(df["CPR_Composite"], errors="coerce")
        adj = (base + df["PP_Delta"].fillna(0)).clip(lower=0, upper=100)
        df["CPR_Composite"] = adj

    return df


def maybe_write_xlsx(df, out_csv_path: Path):
    """
    Optional: write a colored XLSX next to the CSV if openpyxl is available.
    Skips gracefully if openpyxl isn’t installed.
    """
    try:
        import openpyxl  # noqa
    except Exception:
        print("⚠️ openpyxl not installed; skipping colored XLSX export.")
        return

    xlsx_path = out_csv_path.with_suffix(".xlsx")
    try:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="CPR")
            ws = xw.book["CPR"]
            # simple header bold
            for cell in ws[1]:
                cell.font = openpyxl.styles.Font(bold=True)
        print(f"✅ Saved colored workbook → {xlsx_path}")
    except Exception as e:
        print(f"⚠️ Could not write XLSX: {e}")


def main():
    ap = argparse.ArgumentParser(description="Apex CPR Cleaner v2.7 (PP-integrated, A2 balanced)")
    ap.add_argument("--input", "-i", required=True, help="Input CSV (from extractor)")
    ap.add_argument("--output", "-o", default="apex_output_cpr.csv", help="Output CSV")
    ap.add_argument("--no_xlsx", action="store_true", help="Skip XLSX export even if openpyxl is available")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    print(f"📄 Loading extractor output → {in_path}")
    df = pd.read_csv(in_path)

    # If ppdata_list missing, proceed without PP (keeps pipeline resilient)
    if "ppdata_list" not in df.columns:
        print("⚠️ ppdata_list missing; running cleaner without PP features.")
    else:
        print("🧠 Computing PP-derived features (A2)…")
        df = compute_pp_features(df)
        df = apply_pp_to_cpr(df, mode="A2")

    print(f"💾 Saving → {out_path}")
    df.to_csv(out_path, index=False)

    if not args.no_xlsx:
        maybe_write_xlsx(df, out_path)

    print("✅ Cleaner finished successfully.")


if __name__ == "__main__":
    main()
