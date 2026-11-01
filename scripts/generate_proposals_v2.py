#!/usr/bin/env python3
"""
Generate QuickStatements and manual review files from categorized violations.

This script:
1. Reads final P8814 and P5063 violations
2. Groups by synset_id (P8814) or ili (P5063) to find all QIDs sharing the same mapping
3. Determines which QID should keep the mapping
4. Generates QuickStatements to remove duplicates from all other QIDs
5. Creates manual review files for ambiguous cases
6. Outputs summary statistics
"""

import csv
from collections import defaultdict
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path("data/output/20260929")
QUICKSTATEMENTS_DIR = OUTPUT_DIR / "quickstatements"
MANUAL_REVIEW_DIR = OUTPUT_DIR / "manual_review"


def process_p8814_violations():
    """Process P8814 violations and generate proposals."""
    input_file = OUTPUT_DIR / "p8814_violations_final.csv"
    
    # Read all violations
    with open(input_file, 'r') as f:
        all_violations = list(csv.DictReader(f))
    
    # Filter real violations only
    real_violations = [v for v in all_violations if v.get('is_real_violation') == 'TRUE']
    
    # Group by synset_id to find all QIDs sharing the same synset
    synset_to_qids = defaultdict(list)
    for v in real_violations:
        synset_id = v.get('synset_id', '')
        qid = v.get('qid', '')
        synset_to_qids[synset_id].append({
            'qid': qid,
            'synset_id': synset_id,
            'category': v.get('category', ''),
            'notes': v.get('categorization_notes', ''),
            'wd_label': v.get('wikidata_label', ''),
            'wd_description': v.get('wikidata_description', ''),
            'synset_members': v.get('synset_members', ''),
            'synset_definition': v.get('synset_definition', ''),
        })
    
    # Generate QuickStatements
    quickstatements = []
    manual_review = []
    
    for synset_id, qid_data_list in synset_to_qids.items():
        if len(qid_data_list) == 1:
            # Only one QID for this synset - shouldn't be a violation
            # But if it is, skip it
            continue
        
        # Determine which QID to keep
        notes = qid_data_list[0].get('notes', '')
        category = qid_data_list[0].get('category', '')
        
        keep_qid = None
        
        # Try multiple strategies to determine keep_qid
        
        # Strategy 1: Check if notes specify "QID in members"
        if "QID in members:" in notes:
            try:
                keep_qid = notes.split("QID in members:")[1].strip().split(',')[0].strip()
            except (IndexError, AttributeError):
                pass
        
        # Strategy 2: Use similarity scores from notes
        if keep_qid is None and "Similarity:" in notes:
            try:
                sim_part = notes.split("Similarity:")[1].strip()
                # Parse similarity scores
                similarities = {}
                for part in sim_part.split(','):
                    part = part.strip()
                    if ':' in part:
                        qid_in_notes = part.split(':')[0].strip()
                        score = int(part.split(':')[1].strip().split('|')[0].strip())
                        similarities[qid_in_notes] = score
                if similarities:
                    keep_qid = max(similarities, key=similarities.get)
            except (IndexError, ValueError):
                pass
        
        # Strategy 3: Check if QID label is in synset members
        if keep_qid is None:
            synset_members = qid_data_list[0].get('synset_members', '').lower()
            if synset_members:
                for qd in qid_data_list:
                    wd_label = qd.get('wd_label', '').lower()
                    if wd_label and wd_label in synset_members:
                        keep_qid = qd['qid']
                        break
        
        # Strategy 4: Check if QID label is in synset definition
        if keep_qid is None:
            synset_def = qid_data_list[0].get('synset_definition', '').lower()
            if synset_def:
                for qd in qid_data_list:
                    wd_label = qd.get('wd_label', '').lower()
                    if wd_label and wd_label in synset_def:
                        keep_qid = qd['qid']
                        break
        
        # Strategy 5: Use first QID as fallback (will need manual review)
        if keep_qid is None:
            keep_qid = qid_data_list[0]['qid']
        
        # Generate QuickStatements for all QIDs except keep_qid
        for qd in qid_data_list:
            qid = qd['qid']
            if qid != keep_qid:
                quickstatements.append(f"-{qid}|P8814|{synset_id}|S248|{keep_qid}")
    
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
    if manual_review:
        with open(mr_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=manual_review[0].keys())
            writer.writeheader()
            writer.writerows(manual_review)
    
    return {
        'total': len(all_violations),
        'real': len(real_violations),
        'auto_fix': len(quickstatements),
        'manual_review': len(manual_review),
        'valid': len(all_violations) - len(real_violations),
        'unique_synsets': len(synset_to_qids),
        'quickstatements_file': str(qs_file),
        'manual_review_file': str(mr_file),
    }


def process_p5063_violations():
    """Process P5063 violations and generate proposals."""
    input_file = OUTPUT_DIR / "p5063_violations_final.csv"
    
    # Read all violations and deduplicate by (qid, ili)
    seen = set()
    all_violations = []
    with open(input_file, 'r') as f:
        for row in csv.DictReader(f):
            key = (row.get('qid'), row.get('ili'))
            if key not in seen:
                seen.add(key)
                all_violations.append(row)
    
    # Filter real violations only
    real_violations = [v for v in all_violations if v.get('is_real_violation') == 'TRUE']
    
    # Group by ili to find all QIDs sharing the same ILI
    ili_to_qids = defaultdict(list)
    for v in real_violations:
        ili = v.get('ili', '')
        qid = v.get('qid', '')
        ili_to_qids[ili].append({
            'qid': qid,
            'ili': ili,
            'category': v.get('category', ''),
            'notes': v.get('categorization_notes', ''),
            'wd_label': v.get('wikidata_label', ''),
            'wd_description': v.get('wikidata_description', ''),
            'synset_id': v.get('synset_id', ''),
            'synset_definition': v.get('synset_definition', ''),
            'synset_members': v.get('synset_members', ''),
        })
    
    # Generate QuickStatements
    quickstatements = []
    manual_review = []
    
    for ili, qid_data_list in ili_to_qids.items():
        if len(qid_data_list) == 1:
            # Only one QID for this ILI - shouldn't be a violation
            continue
        
        # Determine which QID to keep (the one that best matches the synset definition)
        best_qid = None
        best_score = -1
        
        for qd in qid_data_list:
            wd_label = qd.get('wd_label', '').lower()
            wd_desc = qd.get('wd_description', '').lower()
            synset_def = qd.get('synset_definition', '').lower()
            synset_members = qd.get('synset_members', '').lower()
            
            score = 0
            
            # Check if QID label is in synset members
            if wd_label:
                members_list = synset_members.split('|') if synset_members else []
                if any(member.strip() in wd_label or wd_label in member.strip() for member in members_list):
                    score += 10
            
            # Check if synset definition contains QID label
            if wd_label and synset_def:
                if wd_label in synset_def:
                    score += 5
            
            # Check if QID description matches synset definition
            if wd_desc and synset_def:
                if wd_desc in synset_def or synset_def in wd_desc:
                    score += 3
            
            if score > best_score:
                best_score = score
                best_qid = qd['qid']
        
        if best_qid is None:
            # Can't determine - needs manual review
            manual_review.extend(qid_data_list)
            continue
        
        # Generate QuickStatements for all QIDs except best_qid
        for qd in qid_data_list:
            qid = qd['qid']
            if qid != best_qid:
                quickstatements.append(f"-{qid}|P5063|{ili}|S248|{best_qid}")
    
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
    if manual_review:
        with open(mr_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=manual_review[0].keys())
            writer.writeheader()
            writer.writerows(manual_review)
    
    return {
        'total': len(all_violations),
        'real': len(real_violations),
        'auto_fix': len(quickstatements),
        'manual_review': len(manual_review),
        'valid': len(all_violations) - len(real_violations),
        'unique_ilis': len(ili_to_qids),
        'quickstatements_file': str(qs_file),
        'manual_review_file': str(mr_file),
    }


def generate_summary(p8814_stats, p5063_stats):
    """Generate summary report."""
    total_auto = p8814_stats['auto_fix'] + p5063_stats['auto_fix']
    total_manual = p8814_stats['manual_review'] + p5063_stats['manual_review']
    total_real = p8814_stats['real'] + p5063_stats['real']
    total_valid = p8814_stats['valid'] + p5063_stats['valid']
    total_all = p8814_stats['total'] + p5063_stats['total']
    
    report = f"""
{'='*70}
PROPOSAL GENERATION SUMMARY - v2
{'='*70}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

P8814 (WordNet Synset ID) Violations:
  Total:           {p8814_stats['total']:,}
  Real Violations: {p8814_stats['real']:,}
  Auto-fix:        {p8814_stats['auto_fix']:,} QuickStatements
  Manual Review:   {p8814_stats['manual_review']:,}
  Valid (No Fix):  {p8814_stats['valid']:,}
  Unique Synsets:  {p8814_stats['unique_synsets']:,}
  QuickStatements: {p8814_stats['quickstatements_file']}
  Manual Review:   {p8814_stats['manual_review_file']}

P5063 (ILI) Violations:
  Total:           {p5063_stats['total']:,}
  Real Violations: {p5063_stats['real']:,}
  Auto-fix:        {p5063_stats['auto_fix']:,} QuickStatements
  Manual Review:   {p5063_stats['manual_review']:,}
  Valid (No Fix):  {p5063_stats['valid']:,}
  Unique ILIs:     {p5063_stats['unique_ilis']:,}
  QuickStatements: {p5063_stats['quickstatements_file']}
  Manual Review:   {p5063_stats['manual_review_file']}

{'='*70}
TOTALS:
{'='*70}
  Total Violations:     {total_all:,}
  Real Violations:     {total_real:,}
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
3. Address manual review cases (if any)
4. Submit bulk edits for auto-fixable violations
"""
    return report


def main():
    print("Processing P8814 violations...")
    p8814_stats = process_p8814_violations()
    print(f"  ✓ Generated {p8814_stats['auto_fix']} QuickStatements")
    print(f"  ✓ Manual review: {p8814_stats['manual_review']}")
    
    print("\nProcessing P5063 violations...")
    p5063_stats = process_p5063_violations()
    print(f"  ✓ Generated {p5063_stats['auto_fix']} QuickStatements")
    print(f"  ✓ Manual review: {p5063_stats['manual_review']}")
    
    print("\n" + generate_summary(p8814_stats, p5063_stats))
    
    # Save summary to file
    summary_file = OUTPUT_DIR / "proposal_summary_v2.txt"
    with open(summary_file, 'w') as f:
        f.write(generate_summary(p8814_stats, p5063_stats))
    print(f"\n✓ Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
