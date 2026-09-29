"""
Categorize P5063 and P8814 violations to identify real errors vs valid duplicates.

Adds columns to violation tables:
- category: SYNONYMS_SAME_CONCEPT, BOTH_IN_MEMBERS, ONE_IN_MEMBERS, DIFFERENT_CONCEPTS, etc.
- is_real_violation: TRUE/FALSE (recommendation)
- notes: Explanation for the categorization

Usage:
  python scripts/categorize_violations.py

Input files:
  - data/output/20260929/p8814_violations_from_wd.csv
  - data/output/20260929/p5063_violations_from_wd.csv

Output files:
  - data/output/20260929/p8814_violations_categorized.csv
  - data/output/20260929/p5063_violations_categorized.csv
"""
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
P8814_INPUT = BASE_DIR / "data" / "output" / "20260929" / "p8814_violations_from_wd.csv"
P5063_INPUT = BASE_DIR / "data" / "output" / "20260929" / "p5063_violations_from_wd.csv"
P8814_OUTPUT = BASE_DIR / "data" / "output" / "20260929" / "p8814_violations_categorized.csv"
P5063_OUTPUT = BASE_DIR / "data" / "output" / "20260929" / "p5063_violations_categorized.csv"


def categorize_p8814(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Categorize P8814 violations (synsets with multiple QIDs).
    
    For each synset, we look at all its QIDs and their labels to determine:
    - Are the labels synonyms? (SYNONYMS_SAME_CONCEPT)
    - Are both labels in the synset's members? (BOTH_IN_MEMBERS)
    - Is only one label in members? (ONE_IN_MEMBERS)
    - Are the labels completely different? (DIFFERENT_CONCEPTS)
    """
    # Group rows by synset_id
    synset_groups = defaultdict(list)
    for row in rows:
        synset_groups[row['synset_id']].append(row)
    
    categorized_rows = []
    
    for synset_id, synset_rows in synset_groups.items():
        # Get synset info from first row
        definition = synset_rows[0]['synset_definition']
        members = set(m.strip().lower() for m in synset_rows[0]['synset_members'].split('|') if m.strip())
        ili = synset_rows[0]['synset_ili']
        
        # Get all QIDs and labels for this synset
        qid_labels = []
        for row in synset_rows:
            qid = row['qid']
            label = row['wikidata_label'].lower() if row['wikidata_label'] else ""
            qid_labels.append((qid, label))
        
        # Determine category
        category = "UNKNOWN"
        is_real_violation = "FALSE"
        notes = ""
        
        if len(qid_labels) == 1:
            category = "SINGLE_QID"
            is_real_violation = "FALSE"
            notes = "Only one QID for this synset"
        elif len(qid_labels) == 2:
            q1, l1 = qid_labels[0]
            q2, l2 = qid_labels[1]
            
            # Normalize labels
            l1_norm = l1.strip().lower()
            l2_norm = l2.strip().lower()
            
            # Check label similarity
            labels_identical = l1_norm == l2_norm
            l1_in_l2 = l1_norm in l2_norm or l2_norm in l1_norm
            words_l1 = set(l1_norm.split())
            words_l2 = set(l2_norm.split())
            labels_similar = labels_identical or l1_in_l2 or bool(words_l1 & words_l2)
            
            # Check if labels are in members
            l1_in_members = any(l1_norm in m for m in members)
            l2_in_members = any(l2_norm in m for m in members)
            
            if labels_similar:
                category = "SYNONYMS_SAME_CONCEPT"
                is_real_violation = "FALSE"
                notes = f"Labels '{qid_labels[0][1]}' and '{qid_labels[1][1]}' are synonyms"
            elif l1_in_members and l2_in_members:
                category = "BOTH_IN_MEMBERS"
                is_real_violation = "FALSE"
                notes = f"Both labels are in synset members: {synset_rows[0]['synset_members']}"
            elif l1_in_members or l2_in_members:
                category = "ONE_IN_MEMBERS"
                is_real_violation = "REVIEW"
                in_members = [q for q, l in qid_labels if any(l.strip().lower() in m for m in members)]
                not_in_members = [q for q, l in qid_labels if not any(l.strip().lower() in m for m in members)]
                notes = f"QIDs in members: {', '.join(in_members)} | Not in members: {', '.join(not_in_members)}"
            else:
                category = "DIFFERENT_CONCEPTS"
                is_real_violation = "TRUE"
                notes = f"Labels '{qid_labels[0][1]}' and '{qid_labels[1][1]}' are different concepts"
        else:
            # 3+ QIDs
            category = "MULTIPLE_QIDS"
            is_real_violation = "REVIEW"
            qids_str = ", ".join(q for q, l in qid_labels)
            labels_str = ", ".join(l for q, l in qid_labels)
            notes = f"Multiple QIDs ({len(qid_labels)}): {qids_str} | Labels: {labels_str}"
        
        # Add category info to each row
        for row in synset_rows:
            row_copy = row.copy()
            row_copy['category'] = category
            row_copy['is_real_violation'] = is_real_violation
            row_copy['categorization_notes'] = notes
            categorized_rows.append(row_copy)
    
    return categorized_rows


def categorize_p5063(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Categorize P5063 violations.
    
    There are two types:
    1. single_value: Wikidata item has multiple ILIs (QID -> ILI1, ILI2, ...)
    2. unique_value: ILI has multiple Wikidata items (ILI -> QID1, QID2, ...)
    
    For single_value: Check if both ILIs map to valid synsets for this QID
    For unique_value: Check if the ILI is valid and the QIDs are related
    """
    # Group by qid for single_value violations, and by ili for unique_value
    qid_groups = defaultdict(list)
    ili_groups = defaultdict(list)
    
    for row in rows:
        vtype = row.get('violation_type', '')
        if vtype == 'single_value':
            qid_groups[row['qid']].append(row)
        elif vtype == 'unique_value':
            ili_groups[row['ili']].append(row)
    
    categorized_rows = []
    
    # Process single_value violations
    for qid, qid_rows in qid_groups.items():
        # Get all ILIs for this QID
        ili_labels = []
        for row in qid_rows:
            ili = row['ili']
            label = row['wikidata_label']
            ili_labels.append((ili, label))
        
        category = "UNKNOWN"
        is_real_violation = "FALSE"
        notes = ""
        
        if len(ili_labels) == 1:
            category = "SINGLE_ILI"
            is_real_violation = "FALSE"
            notes = "Only one ILI for this QID"
        elif len(ili_labels) == 2:
            i1, l1 = ili_labels[0]
            i2, l2 = ili_labels[1]
            
            # Check if synsets are from same source and have similar definitions
            # Get synset info from rows
            s1 = qid_rows[0]
            s2 = qid_rows[1] if len(qid_rows) > 1 else qid_rows[0]
            
            def1 = s1.get('synset_definition', '').lower()
            def2 = s2.get('synset_definition', '').lower()
            members1 = set(m.strip().lower() for m in s1.get('synset_members', '').split('|') if m.strip())
            members2 = set(m.strip().lower() for m in s2.get('synset_members', '').split('|') if m.strip())
            
            # Check if both synsets have the same ILI (shouldn't happen but check)
            ili1 = s1.get('synset_ili', '')
            ili2 = s2.get('synset_ili', '')
            
            # Check if wikidata label appears in either synset's members
            label1 = s1.get('wikidata_label', '').lower()
            label2 = s2.get('wikidata_label', '').lower()
            label_in_members1 = any(label1 in m for m in members1)
            label_in_members2 = any(label2 in m for m in members2)
            
            # Check if definitions are similar
            words_def1 = set(def1.split())
            words_def2 = set(def2.split())
            def_similar = bool(words_def1 & words_def2) if words_def1 and words_def2 else False
            
            if label_in_members1 and label_in_members2:
                category = "BOTH_ILIS_VALID"
                is_real_violation = "FALSE"
                notes = f"Both ILIs ({i1}, {i2}) map to synsets with members matching QID label"
            elif label_in_members1 or label_in_members2:
                category = "ONE_ILI_MATCHES"
                is_real_violation = "REVIEW"
                notes = f"Only one ILI matches QID label"
            elif def_similar:
                category = "SIMILAR_DEFINITIONS"
                is_real_violation = "FALSE"
                notes = f"Synset definitions are similar"
            else:
                category = "DIFFERENT_CONCEPTS"
                is_real_violation = "TRUE"
                notes = f"ILIs map to different concepts"
        else:
            category = "MULTIPLE_ILIS"
            is_real_violation = "REVIEW"
            ilis = [r['ili'] for r in qid_rows]
            notes = f"Multiple ILIs ({len(ilis)}): {', '.join(ilis)}"
        
        for row in qid_rows:
            row_copy = row.copy()
            row_copy['category'] = category
            row_copy['is_real_violation'] = is_real_violation
            row_copy['categorization_notes'] = notes
            categorized_rows.append(row_copy)
    
    # Process unique_value violations  
    for ili, ili_rows in ili_groups.items():
        # Get all QIDs for this ILI
        qid_labels = []
        for row in ili_rows:
            qid = row['qid']
            label = row['wikidata_label']
            qid_labels.append((qid, label))
        
        category = "UNIQUE_VALUE_VIOLATION"
        is_real_violation = "REVIEW"
        notes = f"ILI {ili} maps to multiple QIDs: {', '.join(q for q, l in qid_labels)}"
        
        # Check if QID labels are similar
        if len(qid_labels) == 2:
            q1, l1 = qid_labels[0]
            q2, l2 = qid_labels[1]
            if l1.lower() == l2.lower():
                category = "SAME_LABEL_DIFFERENT_QIDS"
                is_real_violation = "REVIEW"
                notes = f"Same label '{l1}' for different QIDs {q1}, {q2}"
        
        for row in ili_rows:
            row_copy = row.copy()
            row_copy['category'] = category
            row_copy['is_real_violation'] = is_real_violation
            row_copy['categorization_notes'] = notes
            categorized_rows.append(row_copy)
    
    return categorized_rows


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    """Write rows to CSV."""
    if not rows:
        return
    
    fieldnames = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"  Written {len(rows)} rows to {path}")


def main():
    print("=" * 70)
    print("Categorizing Violations")
    print("=" * 70)
    
    # Process P8814
    print("\nProcessing P8814 violations...")
    with open(P8814_INPUT, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        p8814_rows = list(reader)
    
    print(f"  Loaded {len(p8814_rows)} rows")
    categorized_p8814 = categorize_p8814(p8814_rows)
    write_csv(P8814_OUTPUT, categorized_p8814)
    
    # Process P5063
    print("\nProcessing P5063 violations...")
    with open(P5063_INPUT, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        p5063_rows = list(reader)
    
    print(f"  Loaded {len(p5063_rows)} rows")
    categorized_p5063 = categorize_p5063(p5063_rows)
    write_csv(P5063_OUTPUT, categorized_p5063)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    # P8814 summary
    p8814_cats = defaultdict(int)
    for row in categorized_p8814:
        cat = row.get('category', 'UNKNOWN')
        p8814_cats[cat] += 1
    
    print(f"\nP8814 Violations ({len(categorized_p8814)} rows):")
    for cat, count in sorted(p8814_cats.items(), key=lambda x: -x[1]):
        real_pct = sum(1 for r in categorized_p8814 if r['category'] == cat and r['is_real_violation'] == 'TRUE') / count * 100 if count > 0 else 0
        print(f"  {cat}: {count} ({real_pct:.0f}% marked as real violations)")
    
    # P5063 summary
    p5063_cats = defaultdict(int)
    for row in categorized_p5063:
        cat = row.get('category', 'UNKNOWN')
        p5063_cats[cat] += 1
    
    print(f"\nP5063 Violations ({len(categorized_p5063)} rows):")
    for cat, count in sorted(p5063_cats.items(), key=lambda x: -x[1]):
        real_pct = sum(1 for r in categorized_p5063 if r['category'] == cat and r['is_real_violation'] == 'TRUE') / count * 100 if count > 0 else 0
        print(f"  {cat}: {count} ({real_pct:.0f}% marked as real violations)")
    
    print("\nDone! Categorized files written to:")
    print(f"  {P8814_OUTPUT}")
    print(f"  {P5063_OUTPUT}")


if __name__ == "__main__":
    main()
