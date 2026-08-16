"""
Extracts synset entries that have a wikidata mapping from:
  - OEWN: data_sources/english-wordnet/src/yaml
  - OENN: data_sources/english-namenet/data/curated

Writes:
    output/oewn_mapped.csv       — entries from english-wordnet only
    output/oenn_mapped.csv       — entries from english-namenet only
    output/merged_mapped.csv     — all entries, with in_oewn / in_oenn columns

Columns kept per entry: synset_id, definition, ili, members, wikidata_qid,
multi_qid, qid_count, review_status
Only entries that have a wikidata field are included.
"""
import csv
from pathlib import Path
from typing import Dict, List

import yaml

BASE_DIR = Path(__file__).resolve().parent
OEWN_ROOT = BASE_DIR / "data_sources" / "english-wordnet" / "src" / "yaml"
OENN_ROOT = BASE_DIR / "data_sources" / "english-namenet" / "data" / "curated"
OUT_DIR = BASE_DIR / "output"

FIELDNAMES = [
    "synset_id",
    "definition",
    "ili",
    "members",
    "wikidata_qid",
    "multi_qid",
    "qid_count",
    "review_status",
]


def normalize_qids(wikidata_value) -> List[str]:
    if isinstance(wikidata_value, list):
        return [str(q).strip() for q in wikidata_value if str(q).strip()]

    text = str(wikidata_value).strip() if wikidata_value is not None else ""
    if not text:
        return []
    if "|" in text:
        return [q.strip() for q in text.split("|") if q.strip()]
    return [text]


def parse_yaml_file(path: Path) -> List[Dict[str, str]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  SKIP (parse error): {path} — {exc}")
        return []

    if not isinstance(data, dict):
        return []

    rows = []
    for synset_id, payload in data.items():
        if not isinstance(synset_id, str) or not isinstance(payload, dict):
            continue

        # Only include entries that have a wikidata mapping
        wikidata = payload.get("wikidata")
        if wikidata is None:
            continue

        definition_raw = payload.get("definition", "")
        if isinstance(definition_raw, list):
            definition = " ".join(str(d).strip() for d in definition_raw)
        else:
            definition = str(definition_raw).strip() if definition_raw else ""

        members_raw = payload.get("members", [])
        if isinstance(members_raw, list):
            members = "|".join(str(m).strip() for m in members_raw)
        else:
            members = str(members_raw).strip() if members_raw else ""

        ili_raw = payload.get("ili")
        ili = str(ili_raw).strip() if ili_raw is not None else ""

        qids = normalize_qids(wikidata)
        wikidata_qid = "|".join(qids)
        qid_count = len(qids)
        multi_qid = "TRUE" if qid_count > 1 else "FALSE"
        review_status = "REVIEW_REQUIRED" if qid_count > 1 else "OK"

        rows.append({
            "synset_id": synset_id,
            "definition": definition,
            "ili": ili,
            "members": members,
            "wikidata_qid": wikidata_qid,
            "multi_qid": multi_qid,
            "qid_count": str(qid_count),
            "review_status": review_status,
        })

    return rows


def extract_from_repo(root: Path, label: str) -> List[Dict[str, str]]:
    if not root.exists():
        raise SystemExit(f"Missing directory: {root}")

    all_rows = []
    yaml_files = list(root.rglob("*.yaml")) + list(root.rglob("*.yml"))
    print(f"{label}: scanning {len(yaml_files)} YAML files in {root}")
    for fp in sorted(yaml_files):
        rows = parse_yaml_file(fp)
        all_rows.extend(rows)
    print(f"{label}: {len(all_rows)} entries with wikidata mapping found")
    return all_rows


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote: {path}")


def build_merged(oewn_rows: List[Dict[str, str]], oenn_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    merged: Dict[str, Dict[str, str]] = {}

    for row in oewn_rows:
        sid = row["synset_id"]
        merged[sid] = {**row, "in_oewn": "TRUE", "in_oenn": "FALSE"}

    for row in oenn_rows:
        sid = row["synset_id"]
        if sid in merged:
            merged[sid]["in_oenn"] = "TRUE"
        else:
            merged[sid] = {**row, "in_oewn": "FALSE", "in_oenn": "TRUE"}

    return list(merged.values())


def main() -> None:
    oewn_rows = extract_from_repo(OEWN_ROOT, "OEWN")
    oenn_rows = extract_from_repo(OENN_ROOT, "OENN")
    merged_rows = build_merged(oewn_rows, oenn_rows)

    write_csv(OUT_DIR / "oewn_mapped.csv", oewn_rows)
    write_csv(OUT_DIR / "oenn_mapped.csv", oenn_rows)

    merged_path = OUT_DIR / "merged_mapped.csv"
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    with merged_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES + ["in_oewn", "in_oenn"])
        writer.writeheader()
        writer.writerows(merged_rows)
    print(f"Wrote: {merged_path}")

    in_both = sum(1 for r in merged_rows if r["in_oewn"] == "TRUE" and r["in_oenn"] == "TRUE")
    print(f"\nSummary:")
    print(f"  OEWN entries:   {len(oewn_rows)}")
    print(f"  OENN entries:   {len(oenn_rows)}")
    print(f"  Merged total:   {len(merged_rows)}")
    print(f"  In both repos:  {in_both}")


if __name__ == "__main__":
    main()
