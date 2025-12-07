# apex_horizontal_bankroll_v1_8.py
# Apex horizontals with v4.3 chaos rules, CPR+MC tiers, hard caps, bankroll-based trimming, and UTF-ready output.
import argparse, math
from pathlib import Path
import pandas as pd
import numpy as np

# ---------- Config ----------
DEFAULT_BASE = 500.0

# Minimum unit bets (track defaults; XML-specific overrides can be added later)
MIN_UNITS = {
    "Daily Double": 2.00,
    "Pick 3": 0.20,
    "Pick 4": 0.20,
    "Pick 5": 0.20,
    "Pick 6": 0.20,
    "Swinger": 1.00,   # not used in builder below but left for completeness
}

# Allocation of horizontal bankroll per sequence type
ALLOC = {
    "Daily Double": 0.25,
    "Pick 3": 0.20,
    "Pick 4": 0.25,
    "Pick 5": 0.20,
    "Pick 6": 0.10,
}

# Hard dollar caps (prevents runaway tickets even if bankroll is huge)
HARD_CAP = {
    "Daily Double": 100.0,
    "Pick 3": 80.0,
    "Pick 4": 150.0,
    "Pick 5": 200.0,
    "Pick 6": 300.0,
}

# Max horses per leg
MAX_PER_LEG_NON_CHAOS = 4   # A+B only
MAX_PER_LEG_CHAOS     = 6   # A+B+C cap

# Chaos rules (Apex v4.3 style)
MC_TOP_CHAOS_MAX = 0.22        # top MC below this
CPR_SPREAD3_MAX  = 3.0         # top-3 CPR spread less than this
ADVERSITY_MIN    = 2           # at least this many adversity flags

# Tiering
A_MC_MIN = 0.28
B_MC_MIN = 0.16
B_CPR_DELTA_MAX = 8.0

# Optional: single detection (strong anchor)
SINGLE_MC_MIN   = 0.34
SINGLE_CPR_GAP  = 3.0

# Columns we will try to read for CPR + MC
CPR_CANDIDATES = ["CPR_Total", "CPR_Composite", "cpr_total", "cpr_composite", "CPR_Composite_x", "CPR_Cleaned"]
MC_CANDIDATES  = ["MC_WinProb", "mc_winprob", "MC_WinPct", "mc_winpct"]

# Some adversity proxies present in your CPR outputs (we’ll use whichever exist)
ADVERSITY_COL_CANDIDATES = [
    "rct91_of_s","rct91_al_s","rctty_s","rctly_s",        # trip/traffic series
    "rca91_of_s","rca91_al_s","rcaty_s","rcaly_s",        # adversity series
    "cpr_break","cpr_pace_l","cpr_off"                    # negative state flags
]

# ---------- Helpers ----------
def find_first_col(df: pd.DataFrame, candidates) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def load_df(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    # standardize race/program numeric
    for col in ["race", "program", "pp"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # CPR column
    cpr_col = find_first_col(df, CPR_CANDIDATES)
    if cpr_col is None:
        raise SystemExit(f"ERROR: No CPR column found. Expected one of: {CPR_CANDIDATES}")
    df["CPR_STD"] = pd.to_numeric(df[cpr_col], errors="coerce")

    # MC column
    mc_col = find_first_col(df, MC_CANDIDATES)
    if mc_col is None:
        raise SystemExit(f"ERROR: No Monte Carlo win-prob column found. Expected one of: {MC_CANDIDATES}")
    df["MC_WIN"] = pd.to_numeric(df[mc_col], errors="coerce").clip(0,1)

    # Names/keys
    if "program" not in df.columns:
        # Fallback to saddlecloth or pp; enforce numeric
        for alt in ["saddleclth", "pp"]:
            if alt in df.columns:
                df["program"] = pd.to_numeric(df[alt], errors="coerce")
                break
    if "horse_name" not in df.columns:
        df["horse_name"] = df.get("horse", df.get("name", ""))
    # sort
    if "race" not in df.columns:
        raise SystemExit("ERROR: input has no 'race' column.")
    df = df.sort_values(["race", "program"], na_position="last").reset_index(drop=True)
    return df

def count_adversity_flags(sub: pd.DataFrame) -> int:
    # Count how many adversity columns (from our candidate list) have at least one positive signal in this race
    present = [c for c in ADVERSITY_COL_CANDIDATES if c in sub.columns]
    if not present:
        return 0
    flags = 0
    for c in present:
        s = pd.to_numeric(sub[c], errors="coerce").fillna(0)
        # treat >0 as a flag (you can tighten this later)
        if (s > 0).any():
            flags += 1
    return flags

def chaos_leg(sub: pd.DataFrame) -> bool:
    # v4.3 chaos: (top MC < 0.22) & (top-3 CPR spread < 3.0) & (adversity flags >= 2)
    mc_top = sub["MC_WIN"].max()
    top3 = sub["CPR_STD"].nlargest(3).values
    cpr_spread3 = (top3[0] - top3[-1]) if len(top3) == 3 else (top3[0] - sub["CPR_STD"].min())
    adv = count_adversity_flags(sub)
    return (mc_top < MC_TOP_CHAOS_MAX) and (cpr_spread3 < CPR_SPREAD3_MAX) and (adv >= ADVERSITY_MIN)

def assign_tiers(sub: pd.DataFrame) -> pd.DataFrame:
    s = sub.copy()
    # CPR rank (1 = best)
    s["_cpr_rank"] = s["CPR_STD"].rank(method="min", ascending=False)
    # A: rank ≤2 or MC ≥ 0.28
    isA = (s["_cpr_rank"] <= 2) | (s["MC_WIN"] >= A_MC_MIN)

    # B: not A and (within 8 CPR of leader OR MC ≥ 0.16)
    lead = s["CPR_STD"].max()
    isB = (~isA) & ( (lead - s["CPR_STD"] <= B_CPR_DELTA_MAX) | (s["MC_WIN"] >= B_MC_MIN) )

    s["Tier"] = np.where(isA, "A", np.where(isB, "B", "C"))
    return s.drop(columns=["_cpr_rank"])

def detect_single(sub: pd.DataFrame) -> int | None:
    # Single if MC ≥ 0.34 and CPR gap to next ≥ 3.0
    s = sub.sort_values("CPR_STD", ascending=False).reset_index(drop=True)
    if s.empty: return None
    cpr_gap = (s.loc[0, "CPR_STD"] - s.loc[1, "CPR_STD"]) if len(s) > 1 else 999
    if (s.loc[0, "MC_WIN"] >= SINGLE_MC_MIN) and (cpr_gap >= SINGLE_CPR_GAP):
        prog = int(pd.to_numeric(s.loc[0, "program"], errors="coerce"))
        if not math.isnan(prog):
            return prog
    return None

def cap_leg(legs: list[int], is_chaos: bool) -> list[int]:
    max_len = MAX_PER_LEG_CHAOS if is_chaos else MAX_PER_LEG_NON_CHAOS
    return legs[:max_len]

def legs_from_tiers(sub: pd.DataFrame, is_chaos: bool, single_prog: int | None) -> list[int]:
    if single_prog is not None:
        return [single_prog]
    if is_chaos:
        keep = sub[sub["Tier"].isin(["A","B","C"])].copy()
    else:
        keep = sub[sub["Tier"].isin(["A","B"])].copy()
    # priority sort: A first, then B, then C, each by hybrid score descending
    keep["_score"] = 0.7*keep["MC_WIN"] + 0.3*(keep["CPR_STD"] - keep["CPR_STD"].min())/(keep["CPR_STD"].max()-keep["CPR_STD"].min() + 1e-9)
    keep["_tier_ord"] = keep["Tier"].map({"A":0,"B":1,"C":2})
    keep = keep.sort_values(["_tier_ord","_score"], ascending=[True, False])
    legs = [int(x) for x in pd.to_numeric(keep["program"], errors="coerce").dropna().astype(int).tolist()]
    return cap_leg(legs, is_chaos)

def sequence_span(races: list[int], start: int, length: int) -> tuple[int,int] | None:
    end = start + (length-1)
    if all(r in races for r in range(start, end+1)):
        return (start, end)
    return None

def combos_count(legs_lists: list[list[int]]) -> int:
    combos = 1
    for leg in legs_lists:
        combos *= max(1, len(leg))
    return combos

def trim_ticket_to_cap(seq_name: str, legs_lists: list[list[int]], unit: float, cap: float, min_per_leg: int) -> tuple[list[list[int]], float]:
    """
    Reduce ticket until combos*unit <= cap by removing lowest priority horses.
    Priority: drop from legs with the most entries, removing the worst-scored horse across those legs.
    Since we don't have per-horse scores anymore here, we'll trim by length only (safest generic approach).
    """
    def total_cost(ll): return combos_count(ll) * unit

    # enforce minimums per leg
    legs_lists = [leg[:] for leg in legs_lists]  # copy
    # quick exit
    if total_cost(legs_lists) <= cap:
        return legs_lists, unit

    # Scale unit first (never below minimum)
    min_unit = MIN_UNITS.get(seq_name, unit)
    # Try to scale unit to fit cap — round to 2 decimals
    scaled_unit = max(min_unit, round(cap / max(1, combos_count(legs_lists)), 2))
    if combos_count(legs_lists) * scaled_unit <= cap:
        return legs_lists, scaled_unit

    # If still too big, start trimming legs, but keep at least min_per_leg in each.
    # Prefer trimming the longest legs first.
    while combos_count(legs_lists) * scaled_unit > cap:
        # pick index of the longest leg that is above minimum size
        sizes = [len(x) for x in legs_lists]
        idxs = [i for i,sz in enumerate(sizes) if sz > min_per_leg]
        if not idxs:
            break
        # remove the last horse from the largest leg
        longest = max(idxs, key=lambda i: sizes[i])
        legs_lists[longest].pop()  # drop worst (end of list)
        # loop continues

        # If we get stuck with huge cost because min_per_leg prevents more trimming, we stop.
        if all(len(l)<=min_per_leg for l in legs_lists):
            break

    return legs_lists, scaled_unit

def build_sequences(df: pd.DataFrame, base: float) -> pd.DataFrame:
    races = sorted(pd.to_numeric(df["race"], errors="coerce").dropna().astype(int).unique().tolist())
    if not races:
        return pd.DataFrame(columns=["sequence","start_race","end_race","unit","combos","cost","legs","notes"])

    # Card confidence multiplier based on count of strong legs (MC ≥ 0.34)
    strong_legs = (df.groupby("race")["MC_WIN"].max() >= 0.34).sum()
    mult = 1.5 if strong_legs >= 3 else (1.0 if strong_legs >= 1 else 0.6)
    bankroll = base * mult

    # Precompute per-race slices
    tiered = df.groupby("race", group_keys=False).apply(assign_tiers)
    chaos_map = {}
    single_map = {}
    for r in races:
        sub = tiered[tiered["race"]==r]
        chaos_map[r] = chaos_leg(sub)
        single_map[r] = detect_single(sub)

    def legs_for_race(r: int) -> list[int]:
        sub = tiered[tiered["race"]==r]
        return legs_from_tiers(sub, chaos_map[r], single_map[r])

    def emit(seq_name: str, span: tuple[int,int] | None, min_per_leg: int) -> dict | None:
        if not span: return None
        s,e = span
        legs_lists = [legs_for_race(r) for r in range(s, e+1)]
        # If any leg is empty (data gap), abort this sequence
        if any(len(l)==0 for l in legs_lists):
            return None

        unit = MIN_UNITS.get(seq_name, 0.20)
        combos = combos_count(legs_lists)
        raw_cost = combos * unit

        alloc_cap = bankroll * ALLOC.get(seq_name, 0.15)
        hard = HARD_CAP.get(seq_name, alloc_cap)
        cap = min(alloc_cap, hard)

        final_legs, final_unit = trim_ticket_to_cap(seq_name, legs_lists, unit, cap, min_per_leg)
        combos2 = combos_count(final_legs)
        cost2 = round(combos2 * final_unit, 2)

        # Label
        notes = []
        if any(chaos_map[r] for r in range(s,e+1)): notes.append("Chaos legs spread")
        if any(single_map[r] is not None for r in range(s,e+1)): notes.append("Anchor single")
        if cost2 < raw_cost: notes.append("Trimmed to cap")
        if not notes: notes = ["Standard structure"]

        return {
            "sequence": seq_name,
            "start_race": s, "end_race": e,
            "unit": round(final_unit, 2),
            "combos": combos2,
            "cost": cost2,
            "legs": " / ".join(",".join(map(str, leg)) for leg in final_legs),
            "notes": "; ".join(notes)
        }

    rows = []
    start = races[0]
    spans = {
        "Daily Double": sequence_span(races, start, 2),
        "Pick 3":       sequence_span(races, start, 3),
        "Pick 4":       sequence_span(races, start, 4),
        "Pick 5":       sequence_span(races, start, 5),
        "Pick 6":       sequence_span(races, start, 6),
    }
    # Minimum per-leg coverage
    # DD must keep at least 2 per leg; others at least 1 (but singles allowed if detected)
    mins = {
        "Daily Double": 2,
        "Pick 3": 1,
        "Pick 4": 1,
        "Pick 5": 1,
        "Pick 6": 1,
    }

    for name, span in spans.items():
        row = emit(name, span, mins[name])
        if row: rows.append(row)

    return pd.DataFrame(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="apex_output_with_mc.csv", help="CSV with CPR + MC columns")
    ap.add_argument("--out",   default="apex_horizontals.csv")
    ap.add_argument("--base",  type=float, default=DEFAULT_BASE)
    args = ap.parse_args()

    df = load_df(args.input)
    out = build_sequences(df, args.base)
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"✅ Saved → {args.out}")

if __name__ == "__main__":
    main()
