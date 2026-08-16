"""
Build a verification-oriented comparison table from:
- output/merged_mapped.csv
- output/wikidata_wordnet_links.csv

Scope intentionally limited:
1) Expand YAML rows to one row per qid_candidate (if multi_qid)
2) Merge on qid_candidate = qid
3) Compute simple deterministic match flags only

Output:
- output/comparison_table.csv
"""

import csv
import re
from pathlib import Path
from typing import Dict, List, Set

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"
MAPPED_CSV = OUT_DIR / "merged_mapped.csv"
WD_CSV = OUT_DIR / "wikidata_wordnet_links.csv"
OUT_CSV = OUT_DIR / "comparison_table.csv"

QID_RE = re.compile(r"^Q[1-9][0-9]*$")
TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def split_qids(qids_text: str) -> List[str]:
    if not qids_text:
        return []
    return [q.strip() for q in qids_text.split("|") if q.strip()]


def normalize_text(value: str) -> str:
    return " ".join(TOKEN_RE.findall((value or "").lower()))


def text_tokens(value: str) -> Set[str]:
    return set(normalize_text(value).split())


def expand_mapped_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    expanded: List[Dict[str, str]] = []
    for row in rows:
        qids = split_qids(row.get("wikidata_qid", ""))
        if not qids:
            qids = [""]

        for qid_candidate in qids:
            expanded.append(
                {
                    "synset_id": row.get("synset_id", ""),
                    "definition": row.get("definition", ""),
                    "ili": row.get("ili", ""),
                    "members": row.get("members", ""),
                    "wikidata_qid_original": row.get("wikidata_qid", ""),
                    "qid_candidate": qid_candidate,
                    "qid_count_original": row.get("qid_count", ""),
                    "multi_qid_original": row.get("multi_qid", ""),
                    "review_status_original": row.get("review_status", ""),
                    "in_oewn": row.get("in_oewn", ""),
                    "in_oenn": row.get("in_oenn", ""),
                }
            )
    return expanded


def build_wikidata_index(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}

    # Keep first valid row per QID. This is enough for basic verification join.
    for row in rows:
        qid = (row.get("qid") or "").strip()
        if not QID_RE.match(qid):
            continue
        if qid in index:
            continue

        index[qid] = {
            "entity_uri": row.get("entity_uri", ""),
            "qid": qid,
            "entity_label": row.get("entity_label", ""),
            "entity_description": row.get("entity_description", ""),
            "wd_ili": row.get("ili", ""),
            "wd_ssid": row.get("ssid", ""),
        }

    return index


def member_tokens(members_text: str) -> List[str]:
    return [m.strip() for m in (members_text or "").split("|") if m.strip()]


def compute_flags(row: Dict[str, str]) -> Dict[str, str]:
    synset_id = row.get("synset_id", "")
    syn_ili = row.get("ili", "")
    members = member_tokens(row.get("members", ""))
    label = row.get("entity_label", "")
    definition = row.get("definition", "")
    description = row.get("entity_description", "")

    members_set = set(members)
    members_norm = {normalize_text(m) for m in members}
    label_norm = normalize_text(label)

    def_tokens = text_tokens(definition)
    desc_tokens = text_tokens(description)
    overlap = len(def_tokens & desc_tokens)

    return {
        "flag_qid_join_found": "1" if row.get("qid", "") else "0",
        "flag_match_ssid_exact": "1" if synset_id and row.get("wd_ssid", "") and synset_id == row.get("wd_ssid", "") else "0",
        "flag_match_ili_exact": "1" if syn_ili and row.get("wd_ili", "") and syn_ili == row.get("wd_ili", "") else "0",
        "flag_label_in_members_exact": "1" if label and label in members_set else "0",
        "flag_label_in_members_norm": "1" if label_norm and label_norm in members_norm else "0",
        "flag_def_desc_overlap_any": "1" if overlap > 0 else "0",
        "def_desc_overlap_count": str(overlap),
    }


def build_comparison_rows(mapped_rows: List[Dict[str, str]], wd_index: Dict[str, Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    expanded = expand_mapped_rows(mapped_rows)

    for base in expanded:
        qid_candidate = base.get("qid_candidate", "")
        wd = wd_index.get(qid_candidate, {})

        combined = {
            **base,
            "entity_uri": wd.get("entity_uri", ""),
            "qid": wd.get("qid", ""),
            "entity_label": wd.get("entity_label", ""),
            "entity_description": wd.get("entity_description", ""),
            "wd_ili": wd.get("wd_ili", ""),
            "wd_ssid": wd.get("wd_ssid", ""),
        }

        combined.update(compute_flags(combined))
        out.append(combined)

    return out


def write_comparison(path: Path, rows: List[Dict[str, str]]) -> None:
    fieldnames = [
        "synset_id",
        "definition",
        "ili",
        "members",
        "wikidata_qid_original",
        "qid_candidate",
        "qid_count_original",
        "multi_qid_original",
        "review_status_original",
        "in_oewn",
        "in_oenn",
        "entity_uri",
        "qid",
        "entity_label",
        "entity_description",
        "wd_ili",
        "wd_ssid",
        "flag_qid_join_found",
        "flag_match_ssid_exact",
        "flag_match_ili_exact",
        "flag_label_in_members_exact",
        "flag_label_in_members_norm",
        "flag_def_desc_overlap_any",
        "def_desc_overlap_count",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    if not MAPPED_CSV.exists():
        raise SystemExit(f"Missing input: {MAPPED_CSV}")
    if not WD_CSV.exists():
        raise SystemExit(f"Missing input: {WD_CSV}")

    mapped_rows = read_csv(MAPPED_CSV)
    wd_rows = read_csv(WD_CSV)
    wd_index = build_wikidata_index(wd_rows)

    comparison_rows = build_comparison_rows(mapped_rows, wd_index)
    write_comparison(OUT_CSV, comparison_rows)

    joins_found = sum(1 for r in comparison_rows if r.get("flag_qid_join_found") == "1")
    print(f"Rows written: {len(comparison_rows)}")
    print(f"Rows with qid join: {joins_found}")
    print(f"Output: {OUT_CSV}")


if __name__ == "__main__":
    main()
