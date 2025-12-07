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
-    x = np.array(values, dtype=float)
-    med = np.nanmedian(x)
-    mad = np.nanmedian(np.abs(x - med))
+    x = [float(v) if v not in (None, "", "nan") else np.nan for v in values]
+    med = np.nanmedian([v for v in x if np.isfinite(v)])
+    diffs = [np.abs(v - med) for v in x if np.isfinite(v)]
+    mad = np.nanmedian(diffs)
     if not np.isfinite(mad) or mad == 0:
         mad = 1.0
-    z = (x - med) / (1.4826 * mad)
+    z = []
+    for v in x:
+        if np.isfinite(v):
+            z.append((v - med) / (1.4826 * mad))
+        else:
+            z.append(np.nan)
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
@@ -159,65 +165,71 @@ def compute_pp_features(df):
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
 
-    combo = np.zeros(len(df), dtype=float)
+    combo = [0.0 for _ in range(len(df))]
     for k, w in feats.items():
-        combo += w * zmap[k]
-    combo -= 0.15 * bl_pen
+        zvals = zmap.get(k, [])
+        combo = [c + w * (zvals[i] if i < len(zvals) else 0.0) for i, c in enumerate(combo)]
+    combo = [c - 0.15 * (bl_pen[i] if i < len(bl_pen) else 0.0) for i, c in enumerate(combo)]
 
     # scale to CPR points; cap for safety
-    pp_delta = 4.0 * combo  # ~balanced; change to 2.5 (conservative) or 6.0 (aggressive)
+    pp_delta = [c * 4.0 for c in combo]
     pp_delta = np.clip(pp_delta, -10, 10)
     df["PP_Delta"] = pp_delta
 
     # Only adjust if CPR_Composite exists already (keeps this file drop-in safe)
     if "CPR_Composite" in df.columns:
         base = pd.to_numeric(df["CPR_Composite"], errors="coerce")
         adj = (base + df["PP_Delta"].fillna(0)).clip(lower=0, upper=100)
         df["CPR_Composite"] = adj
+    else:
+        # Provide a sensible fallback so downstream steps have a CPR column
+        base = [50.0 for _ in range(len(df))]
+        combined = [min(100, max(0, b + (df["PP_Delta"][i] if i < len(df["PP_Delta"]) else 0))) for i, b in enumerate(base)]
+        df["CPR_Composite"] = combined
 
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
 
EOF
)
