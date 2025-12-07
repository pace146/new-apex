import numpy as np
import pandas as pd

# ---------------------------------------------------------
#  Auto-detect CPR column name (case and formatting safe)
# ---------------------------------------------------------

def find_cpr_column(df):
    candidates = [
        "CPR_Composite",
        "cpr_composite",
        "cpr__composite",
        "cprcomposite",
        "cpr composite"
    ]

    normalized = [c.lower().replace("_", "").replace(" ", "") for c in df.columns]

    for cand in candidates:
        key = cand.lower().replace("_", "").replace(" ", "")
        for col, norm in zip(df.columns, normalized):
            if norm == key:
                return col

    raise ValueError("❌ No CPR_Composite column found in dataframe.")


# ---------------------------------------------------------
#  Single Monte Carlo trial for ONE race
# ---------------------------------------------------------

def simulate_race_once(df):
    # Get CPR column name dynamically
    cpr_col = find_cpr_column(df)

    # Use CPR as base weight
    base = df[cpr_col].astype(float).values

    # Make everything positive (avoid zero-weight horses)
    base = np.maximum(base - base.min() + 1e-9, 0.001)

    # Apply randomness (Apex calibrated exponent = 1.25)
    noise = np.random.gamma(shape=1.25, scale=1.0, size=len(base))
    scores = base * noise

    # Order horses by scores
    order = np.argsort(scores)[::-1]

    win  = df.iloc[order[0]]["pp"]
    place = df.iloc[order[1]]["pp"]
    show  = df.iloc[order[2]]["pp"]

    return win, place, show


# ---------------------------------------------------------
#  Run Monte Carlo for ENTIRE CARD (race-by-race)
# ---------------------------------------------------------

def run_mc_simulation(df, runs=5000):
    """Group by race → simulate each race → return probabilities."""

    out_rows = []

    for race_id, group in df.groupby("race"):
        group = group.reset_index(drop=True)

        wins = {}
        places = {}
        shows = {}

        # Initialize counters
        for pp in group["pp"]:
            wins[pp] = 0
            places[pp] = 0
            shows[pp] = 0

        # Run MC trials
        for _ in range(runs):
            w, p, s = simulate_race_once(group)
            wins[w] += 1
            places[p] += 1
            shows[s] += 1

        # Store results
        for pp in group["pp"]:
            out_rows.append({
                "race": race_id,
                "pp": pp,
                "mc_win":   wins[pp]   / runs,
                "mc_place": places[pp] / runs,
                "mc_show":  shows[pp]  / runs
            })

    return pd.DataFrame(out_rows)
