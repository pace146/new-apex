from __future__ import annotations
import zipfile, os
from xml.etree import ElementTree as ET
import pandas as pd

def extract_zip(zip_path: str, extract_to: str) -> str:
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_to)
        names = z.namelist()
    xmls = [n for n in names if n.lower().endswith('.xml')]
    if not xmls:
        raise FileNotFoundError('No .xml file found in ZIP')
    return os.path.join(extract_to, xmls[0])

def parse_horsedata(xml_file: str) -> pd.DataFrame:
    tree = ET.parse(xml_file)
    root = tree.getroot()
    rows = []
    for hd in root.iter('horsedata'):
        rec = {}
        for el in hd:
            rec[el.tag.strip().lower()] = (el.text or '').strip()
        race_raw = rec.get('race', '')
        try:
            rec['race_num'] = int(race_raw) if race_raw.isdigit() else None
        except:
            rec['race_num'] = None
        rows.append(rec)
    return pd.DataFrame(rows)
