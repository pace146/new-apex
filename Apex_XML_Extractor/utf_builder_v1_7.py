# utf_builder_v1_7.py
import pandas as pd
from pathlib import Path

MC_FILES = {
    "exacta":   "verticals_mc_v1_4_exacta_tickets.csv",
    "trifecta": "verticals_mc_v1_4_trifecta_tickets.csv",
    "super":    "verticals_mc_v1_4_super_tickets.csv",
}

HORIZ_FILE = "apex_horizontals.csv"
OUTPUT_FILE = "UTF_Output/UTF_BetSlips.txt"


# ------------------------------------------------------------
# Load helper
# ------------------------------------------------------------
def load_csv(path):
    if not Path(path).exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        return df
    # Ensure minimal columns
    need = {"race", "type", "ticket", "cost"}
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"ERROR: MC file {path} missing columns: {missing}")
    df["race"] = pd.to_numeric(df["race"], errors="coerce").fillna(0).astype(int)
    return df.sort_values(["race","type","ticket"]).reset_index(drop=True)


# ------------------------------------------------------------
# Build vertical block for a single race
# ------------------------------------------------------------
def build_vertical_block(race, df_ex, df_tri, df_sup):
    lines = []
    lines.append(f"========== RACE {race} BET SLIP ==========\n")

    ## Vertical section label
    lines.append("========== VERTICAL WAGERS ==========\n")

    # EXACTA
    ex = df_ex[df_ex["race"] == race]
    if not ex.empty:
        lines.append("========== EXACTA ==========\n")
        for _, r in ex.iterrows():
            ticket = str(r["ticket"])
            cost = float(r["cost"])
            lines.append(f"{ticket}   ${cost:.2f}\n")

    # TRIFECTA
    tri = df_tri[df_tri["race"] == race]
    if not tri.empty:
        lines.append("========== TRIFECTA ==========\n")
        for _, r in tri.iterrows():
            ticket = str(r["ticket"])
            cost = float(r["cost"])
            lines.append(f"{ticket}   ${cost:.2f}\n")

    # SUPERFECTA
    sup = df_sup[df_sup["race"] == race]
    if not sup.empty:
        lines.append("========== SUPERFECTA ==========\n")
        for _, r in sup.iterrows():
            ticket = str(r["ticket"])
            cost = float(r["cost"])
            lines.append(f"{ticket}   ${cost:.2f}\n")

    lines.append("\n")
    return lines


# ------------------------------------------------------------
# Build horizontals block
# ------------------------------------------------------------
def build_horizontal_block(df_hz, race):
    lines = []
    hz = df_hz[df_hz["start_race"] == race]
    if hz.empty:
        return lines

    lines.append("========== HORIZONTAL WAGERS ==========\n")

    for _, r in hz.iterrows():
        seq = r["sequence"]
        cost = float(r["cost"])
        legs = r["legs"]
        notes = r.get("notes", "")

        lines.append(f"========== {seq} ==========\n")
        lines.append(f"Cost: ${cost:.2f}\n")
        lines.append(f"Legs: {legs}\n")
        if notes:
            lines.append(f"Notes: {notes}\n")
        lines.append("\n")

    return lines


# ------------------------------------------------------------
# Main builder
# ------------------------------------------------------------
def build_utf():
    # Load core CPR/MC dataset for race order
    df_base = pd.read_csv("apex_output_with_mc.csv", encoding="utf-8-sig")
    races = sorted(df_base["race"].unique().tolist())

    # Load verticals
    df_ex  = load_csv(MC_FILES["exacta"])
    df_tri = load_csv(MC_FILES["trifecta"])
    df_sup = load_csv(MC_FILES["super"])

    # Load horizontals
    df_hz = pd.read_csv(HORIZ_FILE, encoding="utf-8-sig") if Path(HORIZ_FILE).exists() \
            else pd.DataFrame()

    all_lines = []
    for r in races:
        all_lines.extend(build_vertical_block(r, df_ex, df_tri, df_sup))
        all_lines.extend(build_horizontal_block(df_hz, r))
        all_lines.append("\n")

    # Save output
    outdir = Path("UTF_Output")
    outdir.mkdir(exist_ok=True)
    outpath = outdir / "UTF_BetSlips.txt"
    with open(outpath, "w", encoding="utf-8-sig") as f:
        f.writelines(all_lines)

    print(f"✅ UTF bet slips written → {outpath}")


# ------------------------------------------------------------
if __name__ == "__main__":
    print("=== Apex UTF Builder v1.7 ===")
    build_utf()

