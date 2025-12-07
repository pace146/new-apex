# verticals_mc_builder_v1_4.py (patched)
import argparse, pandas as pd, numpy as np

def load_df(path):
    df = pd.read_csv(path, encoding="utf-8-sig")

    # Accept either CPR_Total or CPR_Composite
    if "CPR_Total" in df.columns:
        df["CPR_Total"] = pd.to_numeric(df["CPR_Total"], errors="coerce")
    elif "CPR_Composite" in df.columns:
        df["CPR_Total"] = pd.to_numeric(df["CPR_Composite"], errors="coerce")
    else:
        raise SystemExit("ERROR: Neither CPR_Total nor CPR_Composite exists in input file.")

    need = {"race","program","horse_name","CPR_Total","MC_WinProb"}
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing columns in {path}: {missing}")

    for c in ["race","program","MC_WinProb"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["race"] = df["race"].astype(int)
    df["program"] = df["program"].astype(int)
    df["MC_WinProb"] = df["MC_WinProb"].clip(0,1)

    return df.sort_values(["race","program"]).reset_index(drop=True)


def exacta_for_race(sub, unit=2.0, max_lines=24):
    s = sub.copy()
    s["rank"] = (-0.7*s["CPR_Total"] - 0.3*(100*s["MC_WinProb"])).rank(method="min")
    A = s.nsmallest(2, "rank")["program"].tolist()
    B = s.nsmallest(5, "rank")["program"].tolist()

    rows=[]
    for a in A:
        for b in B:
            if a!=b:
                rows.append({"race":int(sub["race"].iloc[0]),"type":"EXACTA",
                             "ticket":f"{a}/{b}","cost":unit})
    return rows[:max_lines]


def trifecta_for_race(sub, unit=2.0, max_lines=24):
    s = sub.copy()
    s["rank"] = (-0.65*s["CPR_Total"] - 0.35*(100*s["MC_WinProb"])).rank(method="min")
    A = s.nsmallest(2,"rank")["program"].tolist()
    B = s.nsmallest(6,"rank")["program"].tolist()

    rows=[]
    for a in A:
        for b in B:
            if a==b: continue
            for c in B:
                if c in (a,b): continue
                rows.append({"race":int(sub["race"].iloc[0]),"type":"TRIFECTA",
                             "ticket":f"{a}/{b}/{c}","cost":unit})
    return rows[:max_lines]


def super_for_race(sub, unit=0.20, max_lines=60):
    s=sub.copy()
    s["rank"]=(-0.6*s["CPR_Total"] -0.4*(100*s["MC_WinProb"])).rank(method="min")
    A=s.nsmallest(2,"rank")["program"].tolist()
    B=s.nsmallest(7,"rank")["program"].tolist()

    rows=[]
    for a in A:
        for b in B:
            if b==a: continue
            for c in B:
                if c in (a,b): continue
                for d in B:
                    if d in (a,b,c): continue
                    rows.append({"race":int(sub["race"].iloc[0]),"type":"SUPER",
                                 "ticket":f"{a}/{b}/{c}/{d}","cost":unit})
    return rows[:max_lines]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",default="apex_output_with_mc.csv")
    args=ap.parse_args()

    df=load_df(args.input)
    ex_rows=[]; tri_rows=[]; sup_rows=[]

    for r,sub in df.groupby("race"):
        ex_rows+=exacta_for_race(sub)
        tri_rows+=trifecta_for_race(sub)
        sup_rows+=super_for_race(sub)

    pd.DataFrame(ex_rows).to_csv("verticals_mc_v1_4_exacta_tickets.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(tri_rows).to_csv("verticals_mc_v1_4_trifecta_tickets.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(sup_rows).to_csv("verticals_mc_v1_4_super_tickets.csv",index=False,encoding="utf-8-sig")

    print("✅ Wrote:\n  verticals_mc_v1_4_exacta_tickets.csv\n  verticals_mc_v1_4_trifecta_tickets.csv\n  verticals_mc_v1_4_super_tickets.csv")


if __name__=="__main__":
    main()
