"""
Add hypernym_chain column to multi_qid_review.csv and compute scores.
Enhanced scoring: Levenshtein for labels, Jaccard for definitions, semantic for hierarchy.
"""
import csv
import subprocess
import sys
from pathlib import Path
from typing import Dict

try:
    import yaml
except ImportError:
    print("Installing pyyaml...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import yaml

try:
    import numpy as np
except ImportError:
    print("Installing numpy...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import numpy as np

try:
    from sentence_transformers import SentenceTransformer, util
except ImportError:
    print("Installing sentence-transformers...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "sentence-transformers"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    from sentence_transformers import SentenceTransformer, util

BASE_DIR = Path(__file__).resolve().parent
OEWN_ROOT = BASE_DIR / "data_sources" / "english-wordnet" / "src" / "yaml"
OENN_ROOT = BASE_DIR / "data_sources" / "english-namenet" / "data" / "curated"
IN_CSV = BASE_DIR / "output" / "multi_qid_review.csv"
OUT_CSV = BASE_DIR / "output" / "multi_qid_review_with_scores.csv"


def build_synset_lookup() -> Dict[str, Dict]:
    """Load all synsets."""
    lookup = {}
    for root in [OEWN_ROOT, OENN_ROOT]:
        if not root.exists():
            continue
        for yaml_file in sorted(root.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for synset_id, payload in data.items():
                        if isinstance(payload, dict) and synset_id not in lookup:
                            hypernym_ids = payload.get("hypernym", [])
                            if isinstance(hypernym_ids, str):
                                hypernym_ids = [hypernym_ids]
                            members = payload.get("members", [])
                            lookup[synset_id] = {
                                "hypernym_ids": hypernym_ids,
                                "members": members,
                            }
            except Exception:
                pass
    return lookup


def resolve_hypernym_chain(hypernym_ids, synset_lookup):
    """Convert synset IDs to labels."""
    labels = []
    for hid in hypernym_ids:
        if hid in synset_lookup:
            members = synset_lookup[hid].get("members", [])
            if isinstance(members, list) and members:
                labels.append(str(members[0]).strip())
        else:
            labels.append(hid)
    return "|".join(labels) if labels else ""


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def normalized_levenshtein(s1: str, s2: str) -> float:
    """Normalized Levenshtein: 1.0 = identical, 0.0 = completely different."""
    if not s1 or not s2:
        return 0.0
    max_len = max(len(s1), len(s2))
    dist = levenshtein_distance(s1.lower(), s2.lower())
    return 1.0 - (dist / max_len) if max_len > 0 else 1.0


def string_similarity(s1: str, s2: str) -> float:
    """Word-level Jaccard similarity."""
    if not s1 or not s2:
        return 0.0
    words1 = set(s1.lower().split())
    words2 = set(s2.lower().split())
    if not words1 or not words2:
        return 0.0
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0.0


def score_label_match(wn_members: str, wd_label: str) -> float:
    """Score using Levenshtein distance on best member match."""
    if not wn_members or not wd_label:
        return 0.0
    members = [m.strip() for m in wn_members.split("|") if m.strip()]
    wd_label = wd_label.strip()
    
    # Find best match across all members
    best_score = 0.0
    for member in members:
        score = normalized_levenshtein(member, wd_label)
        best_score = max(best_score, score)
    
    return best_score


def main():
    print("Building synset lookup...")
    synset_lookup = build_synset_lookup()
    print(f"Loaded {len(synset_lookup)} synsets")

    print("Loading semantic similarity model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("Model loaded\n")

    print(f"Reading {IN_CSV}...")
    with IN_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} rows...")
    
    for i, row in enumerate(rows):
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(rows)}...", flush=True)
        
        synset_id = row.get("wn_synset", "").strip()
        
        # Add hypernym chain
        if synset_id in synset_lookup:
            hypernym_ids = synset_lookup[synset_id]["hypernym_ids"]
            row["wn_hypernym_chain"] = resolve_hypernym_chain(hypernym_ids, synset_lookup)
        else:
            row["wn_hypernym_chain"] = ""
        
        # Extract fields
        wn_members = row.get("wn_members", "").strip()
        wn_chain = row.get("wn_hypernym_chain", "").strip()
        wd_label = row.get("wd_label", "").strip()
        wd_parent = row.get("wd_parent", "").strip()
        wn_def = row.get("wn_definition", "").strip()
        wd_desc = row.get("wd_description", "").strip()
        
        # Compute scores
        score_label = score_label_match(wn_members, wd_label)
        
        # Semantic similarity for hierarchy
        if wn_chain and wd_parent:
            embeddings1 = model.encode(wn_chain, convert_to_tensor=True)
            embeddings2 = model.encode(wd_parent, convert_to_tensor=True)
            score_hier = float(util.pytorch_cos_sim(embeddings1, embeddings2)[0][0])
        else:
            score_hier = 0.0
        
        score_def = string_similarity(wn_def, wd_desc)
        score_combined = score_label * 0.5 + score_hier * 0.3 + score_def * 0.2
        
        row["score_label"] = f"{score_label:.2f}"
        row["score_hierarchy"] = f"{score_hier:.2f}"
        row["score_definition"] = f"{score_def:.2f}"
        row["score_combined"] = f"{score_combined:.2f}"

    # Write with new columns
    fieldnames = list(rows[0].keys()) if rows else []
    
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Wrote {len(rows)} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()
