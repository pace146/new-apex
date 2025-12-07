# apex_horizontal_bankroll_v1_5.py
import argparse, pandas as pd, numpy as np

DEFAULT_BASE = 500.0
MIN_UNITS = {
    "Daily Double": 2.0,
    "Pick 3": 0.20,
    "Pick 4": 0.20,
    "Pick 5": 0.20,
    "Pick 6": 0.20,
    "Swinger": 1.0
}

# ---------------------------------------------------------------------
#  LOAD DATA (patched to accept CPR_Composite or cpr_composite)
# ---------------------------------------------------------------------
def load_df(path="apex_output_with_mc.csv"):
    df = pd.read_csv(path, encoding="utf-8-sig")

    # CPR field detection
    cpr_col = None
    for c in ["CPR_Composite", "cpr_composite"]:
        if c in df.columns:
            cpr_col = c
            break

    if not cpr_col:
        raise SystemExit("ERROR: No CPR column found. Expected CPR_Composite or cpr_composite.")

    # MC field detection
    if "MC_WinProb" not in df.columns:
        raise SystemExit("ERROR: MC_WinProb missing from Monte Carlo output")

    df["race"] = pd.to_numeric(df["race"], errors="coerce").astype(int)
    df["program"] = pd.to_numeric(df["program"], errors="coerce").astype(int)
    df["CPR"] = pd.to_numeric(df[cpr_col], errors="coerce")
    df["MC_WinProb"] = pd.to_numeric(df["MC_WinProb"], errors="coerce").clip(0,1)

    return df.sort_values(["race","program"]).reset_index(drop=True)


# ---------------------------------------------------------------------
#  Tier assignment (using CPR + MC)
# ---------------------------------------------------------------------
def assign_tiers(sub: pd.DataFrame):
    sub = sub.copy()

    sub["CPR_RankTmp"] = sub["CPR"].rank(method="min", ascending=False).astype(int)
    cpr_lead = sub["CPR"].max()

    # A Tier
    condA = (sub["CPR_RankTmp"] <= 2) | (sub["MC_WinProb"] >= 0.28)

    # B Tier
    condB = (~condA) & ((cpr_lead - sub["CPR"] <= 8.0) | (sub["MC_WinProb"] >= 0.16))

    # C Tier
    sub["Tier"] = np.where(condA, "A", np.where(condB, "B", "C"))

    return sub.drop(columns=["CPR_RankTmp"])


# ---------------------------------------------------------------------
#  Chaos detection
# ---------------------------------------------------------------------
def is_chaos_leg(sub: pd.DataFrame):
    cpr_std = sub["CPR"].std(ddof=0)
    mc_top = sub["MC_WinProb"].max()
    return (cpr_std <= 3.0 and mc_top < 0.27) or (mc_top < 0.20)


# ---------------------------------------------------------------------
#  Convert tier → betting legs
# ---------------------------------------------------------------------
def legs_from_tier(sub: pd.DataFrame, useA=True, useB=True, useC=False):
    if useA and useB and useC:
        mask = sub["Tier"].isin(["A", "B", "C"])
    elif useA and useB:
        mask = sub["Tier"].isin(["A", "B"])
    else:
        mask = (sub["Tier"] == "A")

    return sorted(sub.loc[mask, "program"].astype(int).tolist())


# ---------------------------------------------------------------------
#  Build sequences (Daily Double, P3, P4, P5, P6)
# ---------------------------------------------------------------------
def sequence_rows(df, base):
    rows = []
    races = sorted(df["race"].unique().tolist())

    # Confidence multiplier
    card_mc_top = df.groupby("race")["MC_WinProb"].max()
    strong_legs = (card_mc_top >= 0.34).sum()

    if strong_legs >= 3: mult = 1.5
    elif strong_legs >= 1: mult = 1.0
    else: mult = 0.6

    bankroll = base * mult

    # Basic opening block
    start = races[0]
    dd = (start, start+1)
    p3 = (start, start+2)
    p4 = (start, start+3)
    p5 = (start, start+4) if (start+4) in races else None
    p6 = (start, start+5) if (start+5) in races else None

    # Tiering + Chaos map
    tiered = df.groupby("race", group_keys=False).apply(assign_tiers)
    chaos_map = {r: is_chaos_leg(tiered[tiered["race"]==r]) for r in races}

    def legs_for_race(r):
        sub = tiered[tiered["race"]==r]
        if chaos_map[r]:
            return legs_from_tier(sub, True, True, True)
        return legs_from_tier(sub, True, True, False)

    # Caps + allocations
    caps = {
        "Daily Double": 100.0,
        "Pick 3": 80.0,
        "Pick 4": 120.0,
        "Pick 5": 150.0,
        "Pick 6": 200.0
    }
    allocations = {
        "Daily Double": 0.25,
        "Pick 3": 0.20,
        "Pick 4": 0.25,
        "Pick 5": 0.20,
        "Pick 6": 0.10
    }

    def seq_cost(legs_lists, unit):
        combos = 1
        for leg in legs_lists:
            combos *= max(1, len(leg))
        return combos, combos * unit

    def emit(name, span):
        if not span: return
        s, e = span
        if e not in races: return

        legs_lists = [legs_for_race(r) for r in range(s, e+1)]
        unit = MIN_UNITS[name]

        combos, cost = seq_cost(legs_lists, unit)
        alloc_cap = bankroll * allocations.get(name, 0.15)
        hard_cap = caps.get(name, alloc_cap)
        final_cost = min(cost, alloc_cap, hard_cap)

        if final_cost < cost:
            unit = max(MIN_UNITS[name], round(final_cost / combos, 2))
            final_cost = round(combos * unit, 2)

        rows.append({
            "sequence": name,
            "start_race": s,
            "end_race": e,
            "unit": unit,
            "combos": combos,
            "cost": round(final_cost, 2),
            "legs": " / ".join(",".join(map(str, leg)) for leg in legs_lists),
            "notes": "Chaos legs spread" if any(chaos_map[r] for r in range(s, e+1)) else "Standard structure"
        })

    emit("Daily Double", dd)
    emit("Pick 3", p3)
    emit("Pick 4", p4)
    if p5: emit("Pick 5", p5)
    if p6: emit("Pick 6", p6)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
#  MAIN
# ---------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=float, default=DEFAULT_BASE)
    ap.add_argument("--input", default="apex_output_with_mc.csv")
    ap.add_argument("--out", default="apex_horizontals.csv")
    args = ap.parse_args()

    df = load_df(args.input)
    out = sequence_rows(df, args.base)
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"✅ Saved → {args.out}")


if __name__ == "__main__":
    main()
