from __future__ import annotations
import os, json, datetime, pandas as pd

def ensure_dirs(*paths):
    for p in paths:
        os.makedirs(p, exist_ok=True)

def save_json(path: str, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def timestamp() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

def per_race_export(df: pd.DataFrame, out_dir: str, card_name: str):
    groups = df.groupby('race_num')
    index = []
    for r, part in groups:
        if pd.isna(r): 
            continue
        recs = part.to_dict(orient='records')
        fname = f"{card_name}_race_{int(r)}.json"
        save_json(os.path.join(out_dir, fname), {'race': int(r), 'starters': recs})
        index.append({'race': int(r), 'file': fname, 'n_starters': len(recs)})
    save_json(os.path.join(out_dir, f"{card_name}_index.json"), {'races': index})
