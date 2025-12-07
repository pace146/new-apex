 # apex_montecarlo_v1.py (v1.2 — patched for CPR auto-detect)
 import pandas as pd
 import numpy as np
 
 # Acceptable CPR column names in priority order
 CPR_CANDIDATES = [
     "CPR_Composite",
     "CPR_Total",
     "CPR_Total_Score",
     "CPR_Composite_x",
     "CPR_Composite_y",
     "CPR_Cleaned"
 ]
 
 def find_cpr_column(df):
     for col in CPR_CANDIDATES:
         if col in df.columns:
             return col
     raise SystemExit(
         "❌ ERROR: No CPR column found. "
         "Expected one of: " + ", ".join(CPR_CANDIDATES)
     )
 
-def simulate_race_once(df, cpr_col):
-    base = df[cpr_col].astype(float).values
-    probs = base - base.min() + 1e-9
-    probs = probs / probs.sum()
+def simulate_race_once(df, cpr_col):
+    base_series = [float(v) if v not in (None, "", "nan") else 0.0 for v in df[cpr_col]]
+    min_base = min(base_series) if base_series else 0.0
+    probs = [b - min_base + 1e-9 for b in base_series]
+    total = sum(probs) or 1.0
+    probs = [p / total for p in probs]
+
+    idx = np.random.choice(len(df), p=probs)
+    return df.rows[idx].get("program")
 
-    idx = np.random.choice(len(df), p=probs)
-    return df.iloc[idx]["program"]
-
-def run_mc_simulation(df, sims=5000):
-    cpr_col = find_cpr_column(df)
-
-    results = []
-    for race, sub in df.groupby("race"):
-        wins = []
-        for _ in range(sims):
-            winner = simulate_race_once(sub, cpr_col)
-            wins.append(winner)
-        counts = pd.Series(wins).value_counts(normalize=True)
-        for pp in sub["program"]:
-            p = counts.get(pp, 0)
-            results.append({
-                "race": race,
+def run_mc_simulation(df, sims=5000):
+    cpr_col = find_cpr_column(df)
+
+    results = []
+    for race, sub in df.groupby("race"):
+        wins = []
+        for _ in range(sims):
+            winner = simulate_race_once(sub, cpr_col)
+            wins.append(winner)
+        counts = pd.Series(wins).value_counts(normalize=True)
+        for pp in sub["program"]:
+            p = counts.get(pp, 0)
+            results.append({
+                "race": race,
                 "program": pp,
                 "MC_WinProb": p
             })
     return pd.DataFrame(results)
 
 
 def main():
     print("📄 Loading → apex_output_live.csv")
     df = pd.read_csv("apex_output_live.csv", encoding="utf-8-sig")
 
     print("⚙️ Running Monte Carlo simulation...")
     df_mc = run_mc_simulation(df)
 
     print("💾 Saving Monte Carlo results → apex_output_with_mc.csv")
     out = df.merge(df_mc, on=["race","program"], how="left")
     out.to_csv("apex_output_with_mc.csv", index=False, encoding="utf-8-sig")
 
     print("✅ Monte Carlo simulation complete.")
 
 
 if __name__ == "__main__":
     main()
 
EOF
)
