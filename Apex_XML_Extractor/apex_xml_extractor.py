"""
Apex XML Extractor v2.0 — with full <ppdata> extraction
-------------------------------------------------------
Parses one or many horse-racing XML program files and outputs:
 • One row per <horsedata> entry (tonight's race)
 • A JSON-encoded list of all <ppdata> entries (past performances)

This version automatically:
 - Finds <horsedata> blocks
 - Extracts ALL <ppdata> blocks under each horse (up to 14)
 - Converts race times (e.g., 1:53.4) into seconds for ML usage
 - Handles ZIPs containing multiple XML files
"""

import argparse
import zipfile
import xml.etree.ElementTree as ET
import pandas as pd
import json
from pathlib import Path

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def parse_time(t):
    """Convert times like '1:53.4' or '28.1' into seconds."""
    if not t:
        return None
    t = t.strip()
    if ":" in t:
        try:
            m, s = t.split(":")
            return int(m) * 60 + float(s)
        except:
            return None
    try:
        return float(t)
    except:
        return None


def parse_float(x):
    try:
        return float(x)
    except:
        return None


# ---------------------------------------------------------
# Extract Past Performance (<ppdata>)
# ---------------------------------------------------------

def extract_ppdata(pp_elem):
    """
    Extract a single <ppdata> block into a dict.
    Normalizes time values and numeric values automatically.
    """
    pp = {}
    for el in pp_elem:
        tag = el.tag
        val = el.text.strip() if el.text else None

        # Normalize times
        if tag.lower() in ("final_time", "finishtime", "time", "race_time",
                           "lq", "lastquarter", "lead_time", "q1", "q2", "q3"):
            val = parse_time(val)

        # Normalize beaten lengths
        if tag.lower() in ("bl", "beatenlengths", "lengths_back"):
            val = parse_float(val)

        pp[tag] = val

    return pp


# ---------------------------------------------------------
# Extract Horse Block (<horsedata>)
# ---------------------------------------------------------

def extract_horsedata(h):
    """
    Extracts:
      • All top-level fields under <horsedata>
      • All <ppdata> blocks (up to 14 per horse)
    """
    rec = {}

    # First: extract simple fields under <horsedata>
    for el in h:
        if el.tag != "ppdata":
            rec[el.tag] = el.text.strip() if el.text else None

    # Second: extract ALL <ppdata> entries
    pp_list = []
    for pp_elem in h.findall("ppdata"):
        pp_list.append(extract_ppdata(pp_elem))

    # Save PP list as JSON text (clean for CSV output)
    rec["ppdata_list"] = json.dumps(pp_list)
    rec["ppdata_count"] = len(pp_list)

    return rec


# ---------------------------------------------------------
# Parse XML → list of horse dictionaries
# ---------------------------------------------------------

def parse_horse_blocks(xml_content: str):
    """Parse an XML string and return a list of {horse_data} dicts."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return []

    horses = []
    for h in root.findall(".//horsedata"):
        horses.append(extract_horsedata(h))

    return horses


# ---------------------------------------------------------
# File loaders (XML or ZIP)
# ---------------------------------------------------------

def parse_file(path: Path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        xml_text = f.read()
    return parse_horse_blocks(xml_text)


def parse_zip(path: Path):
    records = []
    with zipfile.ZipFile(path, "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith(".xml"):
                with zf.open(name) as file:
                    xml_bytes = file.read()
                    try:
                        xml_text = xml_bytes.decode("utf-8", errors="ignore")
                        records.extend(parse_horse_blocks(xml_text))
                    except Exception as e:
                        print(f"⚠️ Skipped {name}: {e}")
    return records


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Apex XML Extractor v2.0")
    parser.add_argument("--xml", type=str, help="Path to a single XML file")
    parser.add_argument("--zip", type=str, help="Path to a ZIP file containing XMLs")
    parser.add_argument("--out", type=str, default="apex_output.csv",
                        help="Output CSV path")
    args = parser.parse_args()

    records = []
    if args.xml:
        print(f"Parsing XML: {args.xml}")
        records = parse_file(Path(args.xml))
    elif args.zip:
        print(f"Parsing ZIP: {args.zip}")
        records = parse_zip(Path(args.zip))
    else:
        print("❌ You must supply either --xml or --zip")
        return

    if not records:
        print("❌ No <horsedata> records found.")
        return

    df = pd.DataFrame(records)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")

    print(f"✅ Parsed {len(df)} horses → {args.out}")
    print("   Includes ppdata_list (JSON) and ppdata_count columns.")


if __name__ == "__main__":
    main()
