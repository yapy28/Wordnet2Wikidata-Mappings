#!/usr/bin/env python3
"""
Build a COMPLETE comparison table that tracks ALL mappings between:
- OEWN/OENN synsets → QIDs
- Wikidata P8814 (synset ID) statements
- Wikidata P5063 (ILI) statements

This creates a unified view of the entire WordNet2Wikidata ecosystem.

The comparison table will:
1. Track all synset/ILI → QID mappings from OEWN/OENN
2. Check which mappings exist on Wikidata
3. Identify missing mappings (backlog)
4. Identify duplicate mappings (violations)
5. Compute match confidence scores
6. Track status of each mapping

This enables:
- Drift detection (changes over time)
- Violation tracking
- Fix proposal generation
- Progress monitoring
"""

import csv
from pathlib import Path
from collections import defaultdict, Counter
import sys

# Configuration
# Get the repo root (two levels up from scripts/)
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output" / "20260929"
COMPARISON_FILE = OUTPUT_DIR / "full_comparison_table.csv"

# File paths
# Note: These would need to be generated or fetched
OEWN_MAPPINGS = DATA_DIR / "oewn_mappings.csv"  # Would need to be generated
OENN_MAPPINGS = DATA_DIR / "oenn_mappings.csv"  # Would need to be generated
WD_P8814_ALL = OUTPUT_DIR / "P8814_all_from_wd.csv"  # Would need to be fetched
WD_P5063_ALL = OUTPUT_DIR / "P5063_all_from_wd.csv"  # Would need to be fetched


def load_csv(filepath):
    """Load CSV file and return list of dicts."""
    if not filepath.exists():
        print(f"Warning: File not found: {filepath}")
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def build_comparison_table():
    """Build the full comparison table."""
    
    print("Building full comparison table...")
    print("=" * 70)
    
    # Load data from all sources
    print("\n1. Loading source data...")
    
    # From OEWN/OENN YAML (these files don't exist yet, but we have the violations)
    # We'll use the violations data we already have to build a partial comparison
    
    # Load P8814 violations from Wikidata
    p8814_violations = load_csv(OUTPUT_DIR / "p8814_violations_final.csv")
    print(f"   Loaded {len(p8814_violations)} P8814 violations")
    
    # Load P5063 violations from Wikidata
    p5063_violations = load_csv(OUTPUT_DIR / "p5063_violations_final.csv")
    print(f"   Loaded {len(p5063_violations)} P5063 violations")
    
    # Load QuickStatements to see what we're proposing to fix
    p8814_qs = []
    if (OUTPUT_DIR / "quickstatements/p8814_fixes_quickstatements.txt").exists():
        with open(OUTPUT_DIR / "quickstatements/p8814_fixes_quickstatements.txt") as f:
            p8814_qs = [l.strip() for l in f if l.startswith('-Q')]
    print(f"   Loaded {len(p8814_qs)} P8814 QuickStatements")
    
    p5063_qs = []
    if (OUTPUT_DIR / "quickstatements/p5063_fixes_quickstatements.txt").exists():
        with open(OUTPUT_DIR / "quickstatements/p5063_fixes_quickstatements.txt") as f:
            p5063_qs = [l.strip() for l in f if l.startswith('-Q')]
    print(f"   Loaded {len(p5063_qs)} P5063 QuickStatements")
    
    # Parse QuickStatements to extract fix information
    p8814_fixes = defaultdict(dict)  # synset_id -> {qid_to_remove: keep_qid}
    for qs in p8814_qs:
        parts = qs.split('|')
        if len(parts) >= 5:
            qid_remove = parts[0][1:]  # Remove the '-'
            # parts[1] is property (P8814)
            synset_id = parts[2]  # This is the synset_id
            # parts[3] is S248
            keep_qid = parts[4]  # The keep_qid
            p8814_fixes[synset_id][qid_remove] = keep_qid
    
    p5063_fixes = defaultdict(dict)  # ili -> {qid_to_remove: keep_qid}
    for qs in p5063_qs:
        parts = qs.split('|')
        if len(parts) >= 5:
            qid_remove = parts[0][1:]  # Remove the '-'
            # parts[1] is property (P5063)
            ili = parts[2]  # This is the ILI
            # parts[3] is S248
            keep_qid = parts[4]  # The keep_qid
            p5063_fixes[ili][qid_remove] = keep_qid
    
    print(f"   Parsed {len(p8814_fixes)} P8814 fix groups")
    print(f"   Parsed {len(p5063_fixes)} P5063 fix groups")
    
    # Build comparison table rows
    print("\n2. Building comparison table...")
    
    rows = []
    
    # Add P8814 violation entries
    for v in p8814_violations:
        qid = v.get('qid', '')
        synset_id = v.get('synset_id', '')
        synset_def = v.get('synset_definition', '')
        synset_members = v.get('synset_members', '')
        synset_source = v.get('synset_source', '')
        wd_label = v.get('wikidata_label', '')
        wd_desc = v.get('wikidata_description', '')
        category = v.get('category', '')
        is_real = v.get('is_real_violation', '') == 'TRUE'
        notes = v.get('categorization_notes', '')
        
        # Check if this QID has a fix proposed
        has_fix = False
        fix_qid = None
        if synset_id in p8814_fixes:
            if qid in p8814_fixes[synset_id]:
                has_fix = True
                fix_qid = p8814_fixes[synset_id][qid]
        
        row = {
            'entity_type': 'P8814',
            'qid': qid,
            'wd_label': wd_label,
            'wd_description': wd_desc,
            'synset_id': synset_id,
            'synset_definition': synset_def,
            'synset_members': synset_members,
            'synset_source': synset_source,
            'ili': v.get('synset_ili', ''),
            'category': category,
            'is_violation': 'TRUE' if is_real else 'FALSE',
            'violation_type': 'DUPLICATE_P8814' if is_real else 'VALID',
            'has_fix_proposed': 'TRUE' if has_fix else 'FALSE',
            'fix_qid': fix_qid or '',
            'fix_applied': 'FALSE',  # Not yet applied
            'confidence_score': compute_confidence(v),
            'status': 'FIX_PROPOSED' if has_fix and is_real else ('VALID' if not is_real else 'NEEDS_FIX'),
        }
        rows.append(row)
    
    # Add P5063 violation entries
    # Deduplicate first
    seen_5063 = set()
    unique_p5063 = []
    for v in p5063_violations:
        key = (v.get('qid'), v.get('ili'))
        if key not in seen_5063:
            seen_5063.add(key)
            unique_p5063.append(v)
    
    for v in unique_p5063:
        qid = v.get('qid', '')
        ili = v.get('ili', '')
        synset_id = v.get('synset_id', '')
        synset_def = v.get('synset_definition', '')
        synset_members = v.get('synset_members', '')
        synset_source = v.get('synset_source', '')
        wd_label = v.get('wikidata_label', '')
        wd_desc = v.get('wikidata_description', '')
        category = v.get('category', '')
        is_real = v.get('is_real_violation', '') == 'TRUE'
        notes = v.get('categorization_notes', '')
        
        # Check if this QID has a fix proposed
        has_fix = False
        fix_qid = None
        if ili in p5063_fixes:
            if qid in p5063_fixes[ili]:
                has_fix = True
                fix_qid = p5063_fixes[ili][qid]
        
        row = {
            'entity_type': 'P5063',
            'qid': qid,
            'wd_label': wd_label,
            'wd_description': wd_desc,
            'synset_id': synset_id,
            'synset_definition': synset_def,
            'synset_members': synset_members,
            'synset_source': synset_source,
            'ili': ili,
            'category': category,
            'is_violation': 'TRUE' if is_real else 'FALSE',
            'violation_type': 'DUPLICATE_P5063' if is_real else 'VALID',
            'has_fix_proposed': 'TRUE' if has_fix else 'FALSE',
            'fix_qid': fix_qid or '',
            'fix_applied': 'FALSE',
            'confidence_score': compute_confidence(v),
            'status': 'FIX_PROPOSED' if has_fix and is_real else ('VALID' if not is_real else 'NEEDS_FIX'),
        }
        rows.append(row)
    
    print(f"   Total rows: {len(rows)}")
    
    # Write comparison table
    print("\n3. Writing comparison table...")
    
    fieldnames = [
        'entity_type',
        'qid',
        'wd_label',
        'wd_description',
        'synset_id',
        'synset_definition',
        'synset_members',
        'synset_source',
        'ili',
        'category',
        'is_violation',
        'violation_type',
        'has_fix_proposed',
        'fix_qid',
        'fix_applied',
        'confidence_score',
        'status',
    ]
    
    COMPARISON_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COMPARISON_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"   Written to: {COMPARISON_FILE}")
    print(f"   Size: {len(rows):,} rows")
    
    # Print summary
    print("\n" + "=" * 70)
    print("COMPARISON TABLE SUMMARY")
    print("=" * 70)
    
    entity_types = Counter(r['entity_type'] for r in rows)
    violations = Counter(r['is_violation'] for r in rows)
    statuses = Counter(r['status'] for r in rows)
    
    print(f"\nEntity Types:")
    for entity, count in sorted(entity_types.items()):
        print(f"  {entity}: {count:,}")
    
    print(f"\nViolations:")
    for v, count in sorted(violations.items()):
        print(f"  {v}: {count:,}")
    
    print(f"\nStatuses:")
    for s, count in sorted(statuses.items()):
        print(f"  {s}: {count:,}")
    
    print("\n" + "=" * 70)


def compute_confidence(row):
    """Compute a confidence score based on available data."""
    score = 0
    
    # Check if this is a valid mapping (no fix needed)
    if row.get('is_violation') == 'FALSE':
        score = 10  # Highest confidence for valid mappings
        return score
    
    # Check if we have a fix proposed
    if row.get('has_fix_proposed') == 'TRUE':
        score += 5
    
    # Check category
    category = row.get('category', '')
    if 'ONE_IN_MEMBERS' in category:
        score += 3
    elif 'DIFFERENT_CONCEPTS' in category:
        score += 2
    elif 'DISSIMILAR' in category:
        score += 2
    
    # Check if label matches synset members
    wd_label = row.get('wd_label', '').lower()
    synset_members = row.get('synset_members', '').lower()
    if wd_label and synset_members and wd_label in synset_members:
        score += 2
    
    return min(score, 10)  # Cap at 10


def main():
    print("=" * 70)
    print("BUILDING FULL COMPARISON TABLE")
    print("=" * 70)
    print("\nThis script builds a comparison table that tracks:")
    print("  - All P8814 and P5063 violations from Wikidata")
    print("  - Proposed fixes from QuickStatements")
    print("  - Status of each mapping")
    print("\nNote: For a COMPLETE comparison table that includes all OEWN/OENN")
    print("mappings (not just violations), we would need to:")
    print("  1. Extract mappings from OEWN/OENN YAML files")
    print("  2. Fetch ALL P8814/P5063 statements from Wikidata")
    print("  3. Merge and compare all mappings")
    print("\nThis current implementation builds a comparison table from the")
    print("violation data we already have + the proposed fixes.")
    print("=" * 70)
    
    build_comparison_table()
    
    print("\n✅ Comparison table built successfully!")
    print(f"\nNext steps:")
    print(f"  1. Review {COMPARISON_FILE}")
    print(f"  2. Use it to track drift and progress")
    print(f"  3. Integrate with comprehensive dashboard")


if __name__ == "__main__":
    main()
