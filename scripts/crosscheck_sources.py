#!/usr/bin/env python3
"""
Cross-check every P8814 / P5063 duplicate group against what the source repos say.

For each synset (P8814) or ILI (P5063) that has duplicate QIDs on Wikidata, look up the
QID(s) that english-wordnet (OEWN) / english-namenet (OENN) assign to it. If exactly one
of the Wikidata QIDs is named by the source, that QID is the *source pick* and the
proposal generator prefers it as the QID to keep.

The repos are read from a git ref (default upstream/main) via `git archive`, so nothing is
checked out and your working branches are left alone.

Output: <run-dir>/source_crosscheck.csv

Usage:
    python scripts/crosscheck_sources.py [--run-dir DIR] [--wordnet-repo DIR] [--namenet-repo DIR]
                                         [--wordnet-ref REF] [--namenet-ref REF]
"""
import argparse
import csv
import subprocess
import tarfile
import tempfile
from collections import defaultdict
from io import BytesIO
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = BASE_DIR / "data" / "output" / "20261101"

FIELDS = ["prop", "value", "group_qids", "real_qids", "source_qids", "source_pick", "status"]

# status values
PICK = "source_confirms_one"           # exactly one group QID is named by the source
SEVERAL = "source_lists_several"       # the source itself lists more than one of the group QIDs
OTHER = "source_other_qid"             # source names a QID, but none of the group's QIDs
NO_QID = "source_no_qid"               # synset/ILI found in source, but without a Wikidata QID
MISSING = "not_in_source"              # synset/ILI not found in the source repos


def normalize_qids(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [q.strip() for q in str(value).split("|") if q.strip()]


def classify(group_qids, source_qids, found):
    """Return (status, source_pick) for one duplicate group."""
    if not found:
        return MISSING, ""
    if not source_qids:
        return NO_QID, ""
    hits = sorted(set(group_qids) & set(source_qids))
    if not hits:
        return OTHER, ""
    if len(hits) == 1:
        return PICK, hits[0]
    return SEVERAL, ""


def read_yaml_tree(root, tag, synsets):
    """Collect synset entries (definition + partOfSpeech) from a directory of YAML files."""
    for path in sorted(Path(root).rglob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for sid, payload in data.items():
            if isinstance(payload, dict) and "definition" in payload and "partOfSpeech" in payload:
                synsets[str(sid)].append({
                    "src": tag,
                    "qids": normalize_qids(payload.get("wikidata")),
                    "ili": str(payload.get("ili") or ""),
                })


def archive_to_tempdir(repo, ref, subpath, tmp):
    """Extract <subpath> of <ref> from a local git repo into tmp without touching its working tree."""
    raw = subprocess.run(["git", "-C", str(repo), "archive", ref, subpath], check=True, capture_output=True).stdout
    with tarfile.open(fileobj=BytesIO(raw)) as tar:
        tar.extractall(tmp, filter="data")
    return Path(tmp) / subpath


def load_sources(wordnet_repo, wordnet_ref, namenet_repo, namenet_ref):
    synsets = defaultdict(list)
    with tempfile.TemporaryDirectory() as tmp:
        read_yaml_tree(archive_to_tempdir(wordnet_repo, wordnet_ref, "src/yaml", tmp + "/oewn"), "OEWN", synsets)
        read_yaml_tree(archive_to_tempdir(namenet_repo, namenet_ref, "data/curated", tmp + "/oenn"), "OENN", synsets)
    by_ili = defaultdict(list)
    for entries in synsets.values():
        for e in entries:
            if e["ili"]:
                by_ili[e["ili"]].append(e)
    return synsets, by_ili


def duplicate_groups(run_dir):
    """Yield (prop, value, all_qids, real_qids) from the final violation CSVs."""
    for prop, field, name in (("P8814", "synset_id", "p8814"), ("P5063", "ili", "p5063")):
        groups = defaultdict(lambda: {"all": set(), "real": set()})
        with open(Path(run_dir) / f"{name}_violations_final.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                g = groups[row[field]]
                g["all"].add(row["qid"])
                if row["is_real_violation"] == "TRUE":
                    g["real"].add(row["qid"])
        for value, g in groups.items():
            yield prop, value, sorted(g["all"]), sorted(g["real"])


def crosscheck(run_dir, synsets, by_ili):
    rows = []
    for prop, value, all_qids, real_qids in duplicate_groups(run_dir):
        entries = synsets.get(value, []) if prop == "P8814" else by_ili.get(value, [])
        source_qids = sorted({q for e in entries for q in e["qids"]})
        status, pick = classify(real_qids or all_qids, source_qids, bool(entries))
        rows.append({
            "prop": prop, "value": value,
            "group_qids": "|".join(all_qids), "real_qids": "|".join(real_qids),
            "source_qids": "|".join(source_qids), "source_pick": pick, "status": status,
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    ap.add_argument("--wordnet-repo", type=Path, default=Path.home() / "GIT" / "english-wordnet")
    ap.add_argument("--namenet-repo", type=Path, default=Path.home() / "GIT" / "english-namenet")
    ap.add_argument("--wordnet-ref", default="upstream/main")
    ap.add_argument("--namenet-ref", default="upstream/main")
    args = ap.parse_args()

    synsets, by_ili = load_sources(args.wordnet_repo, args.wordnet_ref, args.namenet_repo, args.namenet_ref)
    print(f"Source synsets loaded: {len(synsets):,}")
    rows = crosscheck(args.run_dir, synsets, by_ili)

    out = args.run_dir / "source_crosscheck.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    for prop in ("P8814", "P5063"):
        counts = defaultdict(int)
        for r in rows:
            if r["prop"] == prop and r["real_qids"]:
                counts[r["status"]] += 1
        print(f"{prop} real groups: {dict(counts)}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
