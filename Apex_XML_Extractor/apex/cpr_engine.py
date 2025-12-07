from __future__ import annotations
import pandas as pd
import numpy as np

NUMERIC_HINTS = ['dt_s','dt_wp','dt_pp','dt_sp','dt_ip','dt_rp','th_s','th_wp','th_pp','th_sp','th_ip','th_rp','sc_avgcr','era_apv','bt91_tmc','btty_tmc','btly_tmc']

def score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in NUMERIC_HINTS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    feats = [c for c in NUMERIC_HINTS if c in df.columns]
    if feats:
        z = (df[feats] - df[feats].mean())/df[feats].std(ddof=0)
        z = z.fillna(0.0)
        comp = z.mean(axis=1)
        df['cpr'] = (75 + 10*comp).clip(50,100)
    else:
        df['cpr'] = 75.0
    pct = df['cpr'].rank(pct=True)
    df['conf_bucket'] = np.select([pct<0.35, pct<0.7, pct<0.94], ['LOW','MED','HIGH'], default='HAMMER')
    return df
