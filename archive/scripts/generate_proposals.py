#!/usr/bin/env python3
"""
Generate QuickStatements and manual review files from categorized violations.

This script:
1. Reads categorized P8814 and P5063 violations
2. Identifies violations that can be auto-fixed
3. Generates QuickStatements for auto-fixable violations
4. Creates manual review files for ambiguous cases
5. Outputs summary statistics
"""

import csv
from collections import defaultdict
from pathlib import Path

OUTPUT_DIR = Path("data/output/20260929")
QUICKSTATEMENTS_DIR = OUTPUT_DIR / "quickstatements"
MANUAL_REVIEW_DIR = OUTPUT_DIR / "manual_review"

# Categories that can be auto-fixed
AUTO_FIX_CATEGORIES_P8814 = {
    "ONE_IN_MEMBERS_DESC_MISMATCH",
    "DIFFERENT_CONCEPTS",
    "MULTIPLE_QIDS_WITH_MISMATCHES",
}

# Categories that can be auto-fixed
AUTO_FIX_CATEGORIES_P5063 = {
    "DISSIMILAR_QIDS",
}

# Categories that require manual review
MANUAL_REVIEW_CATEGORIES = {
    "AMBIGUOUS_POLYSEMY",
    "AMBIGUOUS_NUANCE",
    "REVIEW",
}


def process_p8814_violations():
    """Process P8814 violations and generate proposals."""
    input_file = OUTPUT_DIR / "p8814_violations_final.csv"
    
    # Read violations and deduplicate by (qid, synset_id)
    seen = set()
    violations = []
    with open(input_file, 'r') as f:
        for row in csv.DictReader(f):
            key = (row.get('qid'), row.get('synset_id'))
            if key not in seen:
                seen.add(key)
                violations.append(row)
    
    # Separate by category
    auto_fix = []
    manual_review = []
    valid_no_fix = []
    
    for v in violations:
        category = v.get('category', '')
        is_real = v.get('is_real_violation', '') == 'TRUE'
        
        if not is_real:
            valid_no_fix.append(v)
            continue
            
        if category in AUTO_FIX_CATEGORIES_P8814:
            auto_fix.append(v)
        elif category in MANUAL_REVIEW_CATEGORIES:
            manual_review.append(v)
        else:
            # Unknown category, put in manual review
            manual_review.append(v)
    
    # Group by synset_id to find all QIDs sharing the same synset
    synset_to_qids = defaultdict(list)
    for v in auto_fix:
        synset_id = v.get('synset_id', '')
        synset_to_qids[synset_id].append(v)
    
    # Generate QuickStatements for auto-fix
    quickstatements = []
    for synset_id, qid_rows in synset_to_qids.items():
        # For each synset, determine which QID should keep it
        notes = qid_rows[0].get('categorization_notes', '')
        category = qid_rows[0].get('category', '')
        
        if "QID in members:" in notes:
            # Format: "QID in members: Q123, Not in members and low sim: Q456"
            keep_qid = notes.split("QID in members:")[1].strip().split(',')[0].strip()
            # All other QIDs with this synset should have P8814 removed
            for row in qid_rows:
                qid = row.get('qid', '')
                if qid != keep_qid:
                    quickstatements.append(f"-{qid}|P8814|{synset_id}|S248|{keep_qid}")
        elif category == "DIFFERENT_CONCEPTS":
            # Find the QID with highest similarity
            if "Similarity:" in notes:
                parts = notes.split("Similarity:")[1].strip()
                similarities = {}
                for part in parts.split(','):
                    part = part.strip()
                    if ':' in part:
                        qid_in_notes, score = part.split(':')
                        qid_in_notes = qid_in_notes.strip()
                        score = int(score.strip().split('|')[0].strip()) if score.strip() else 0
                        similarities[qid_in_notes] = score
                
                if similarities:
                    keep_qid = max(similarities, key=similarities.get)
                    # All other QIDs should have P8814 removed
                    for row in qid_rows:
                        qid = row.get('qid', '')
                        if qid != keep_qid:
                            quickstatements.append(f"-{qid}|P8814|{synset_id}|S248|{keep_qid}")
        elif category == "MULTIPLE_QIDS_WITH_MISMATCHES":
            # Keep the one in members if we can determine it
            # Otherwise mark for manual review
            for row in qid_rows:
                quickstatements.append(f"# {row.get('qid')}|P8814|{synset_id} - NEEDS VERIFICATION ({category})")
    
    # Write QuickStatements file
    qs_file = QUICKSTATEMENTS_DIR / "p8814_fixes_quickstatements.txt"
    qs_file.parent.mkdir(parents=True, exist_ok=True)
    with open(qs_file, 'w') as f:
        f.write("# P8814 QuickStatements - Generated from violation analysis\n")
        f.write("# Format: -QID|P8814|synset_id|S248|keep_qid\n")
        f.write("# Remove duplicate P8814 statements, keeping the canonical mapping\n\n")
        for qs in quickstatements:
            f.write(qs + "\n")
    
    # Write manual review file
    mr_file = MANUAL_REVIEW_DIR / "p8814_manual_review.csv"
    mr_file.parent.mkdir(parents=True, exist_ok=True)
    with open(mr_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=violations[0].keys())
        writer.writeheader()
        writer.writerows(manual_review)
    
    return {
        'total': len(violations),
        'auto_fix': len(auto_fix),
        'manual_review': len(manual_review),
        'valid_no_fix': len(valid_no_fix),
        'quickstatements_file': str(qs_file),
        'manual_review_file': str(mr_file),
    }


def process_p5063_violations():
    """Process P5063 violations and generate proposals."""
    input_file = OUTPUT_DIR / "p5063_violations_final.csv"
    
    # Read violations and deduplicate by (qid, ili)
    seen = set()
    violations = []
    with open(input_file, 'r') as f:
        for row in csv.DictReader(f):
            key = (row.get('qid'), row.get('ili'))
            if key not in seen:
                seen.add(key)
                violations.append(row)
    
    # Separate by category
    auto_fix = []
    manual_review = []
    valid_no_fix = []
    
    for v in violations:
        category = v.get('category', '')
        is_real = v.get('is_real_violation', '') == 'TRUE'
        
        if not is_real:
            valid_no_fix.append(v)
            continue
            
        if category in AUTO_FIX_CATEGORIES_P5063:
            auto_fix.append(v)
        elif category in MANUAL_REVIEW_CATEGORIES:
            manual_review.append(v)
        else:
            # Unknown category, put in manual review
            manual_review.append(v)
    
    # Group by ili to find all QIDs sharing the same ILI
    ili_to_qids = defaultdict(list)
    for v in auto_fix:
        ili = v.get('ili', '')
        ili_to_qids[ili].append(v)
    
    # Generate QuickStatements for auto-fix
    quickstatements = []
    for ili, qid_rows in ili_to_qids.items():
        # For DISSIMILAR_QIDS, multiple QIDs share the same ILI
        # We need to determine which QID should keep the ILI
        # Strategy: Keep the QID whose label/definition best matches the synset definition
        
        # Get the synset definition from the first row (they should all have the same synset)
        synset_def = qid_rows[0].get('synset_definition', '')
        
        # For each QID, calculate similarity to synset definition
        # Simple approach: if QID label is in synset members, or description is similar
        best_qid = None
        best_score = -1
        
        for row in qid_rows:
            qid = row.get('qid', '')
            wd_label = row.get('wikidata_label', '').lower()
            wd_desc = row.get('wikidata_description', '').lower()
            synset_members = row.get('synset_members', '').lower()
            
            score = 0
            
            # Check if QID label is in synset members
            if wd_label and any(member in wd_label or wd_label in member for member in synset_members.split('|')):
                score += 10
            
            # Check if synset definition contains QID label
            if wd_label and wd_label in synset_def.lower():
                score += 5
            
            # Check if QID description matches synset definition
            if wd_desc and wd_desc in synset_def.lower():
                score += 3
            
            if score > best_score:
                best_score = score
                best_qid = qid
        
        # Generate QuickStatements to remove P5063 from all QIDs except best_qid
        if best_qid:
            for row in qid_rows:
                qid = row.get('qid', '')
                if qid != best_qid:
                    quickstatements.append(f"-{qid}|P5063|{ili}|S248|{best_qid}")
        else:
            # If we couldn't determine, mark all for review
            for row in qid_rows:
                qid = row.get('qid', '')
                quickstatements.append(f"# {qid}|P5063|{ili} - NEEDS VERIFICATION")
    
    # Write QuickStatements file
    qs_file = QUICKSTATEMENTS_DIR / "p5063_fixes_quickstatements.txt"
    qs_file.parent.mkdir(parents=True, exist_ok=True)
    with open(qs_file, 'w') as f:
        f.write("# P5063 QuickStatements - Generated from violation analysis\n")
        f.write("# Format: -QID|P5063|ili|S248|keep_qid\n")
        f.write("# Remove duplicate P5063 statements, keeping the canonical mapping\n\n")
        for qs in quickstatements:
            f.write(qs + "\n")
    
    # Write manual review file
    mr_file = MANUAL_REVIEW_DIR / "p5063_manual_review.csv"
    mr_file.parent.mkdir(parents=True, exist_ok=True)
    with open(mr_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=violations[0].keys())
        writer.writeheader()
        writer.writerows(manual_review)
    
    return {
        'total': len(violations),
        'auto_fix': len(auto_fix),
        'manual_review': len(manual_review),
        'valid_no_fix': len(valid_no_fix),
        'quickstatements_file': str(qs_file),
        'manual_review_file': str(mr_file),
    }


def generate_summary(p8814_stats, p5063_stats):
    """Generate summary report."""
    total_auto = p8814_stats['auto_fix'] + p5063_stats['auto_fix']
    total_manual = p8814_stats['manual_review'] + p5063_stats['manual_review']
    total_valid = p8814_stats['valid_no_fix'] + p5063_stats['valid_no_fix']
    total_all = p8814_stats['total'] + p5063_stats['total']
    
    report = f"""
{'='*70}
PROPOSAL GENERATION SUMMARY
{'='*70}

Generated: 2026-11-01

P8814 (WordNet Synset ID) Violations:
  Total:        {p8814_stats['total']:,}
  Auto-fix:     {p8814_stats['auto_fix']:,} → QuickStatements: {p8814_stats['quickstatements_file']}
  Manual Review: {p8814_stats['manual_review']:,} → File: {p8814_stats['manual_review_file']}
  Valid (No Fix): {p8814_stats['valid_no_fix']:,}

P5063 (ILI) Violations:
  Total:        {p5063_stats['total']:,}
  Auto-fix:     {p5063_stats['auto_fix']:,} → QuickStatements: {p5063_stats['quickstatements_file']}
  Manual Review: {p5063_stats['manual_review']:,} → File: {p5063_stats['manual_review_file']}
  Valid (No Fix): {p5063_stats['valid_no_fix']:,}

{'='*70}
TOTALS:
{'='*70}
  Total Violations:     {total_all:,}
  Auto-fixable:         {total_auto:,}
  Manual Review:        {total_manual:,}
  Valid (No Fix):       {total_valid:,}

{'='*70}
FILES GENERATED:
{'='*70}
  {p8814_stats['quickstatements_file']}
  {p5063_stats['quickstatements_file']}
  {p8814_stats['manual_review_file']}
  {p5063_stats['manual_review_file']}

{'='*70}
NEXT STEPS:
{'='*70}
1. Review the QuickStatements files for correctness
2. Test a small batch on Wikidata
3. Address manual review cases
4. Submit bulk edits for auto-fixable violations
"""
    return report


def main():
    print("Processing P8814 violations...")
    p8814_stats = process_p8814_violations()
    print(f"  ✓ Generated {p8814_stats['auto_fix']} QuickStatements")
    print(f"  ✓ Identified {p8814_stats['manual_review']} cases for manual review")
    
    print("\nProcessing P5063 violations...")
    p5063_stats = process_p5063_violations()
    print(f"  ✓ Generated {p5063_stats['auto_fix']} QuickStatements")
    print(f"  ✓ Identified {p5063_stats['manual_review']} cases for manual review")
    
    print("\n" + generate_summary(p8814_stats, p5063_stats))
    
    # Save summary to file
    summary_file = OUTPUT_DIR / "proposal_summary.txt"
    with open(summary_file, 'w') as f:
        f.write(generate_summary(p8814_stats, p5063_stats))
    print(f"\n✓ Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
