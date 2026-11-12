"""
FINAL CATEGORIZATION - 100% COVERAGE

This script categorizes ALL violations with NO REVIEW category left.
Even if some decisions are wrong, they can be manually corrected.

Goal: Provide a complete starting point for manual verification before meeting.

Output:
- p8814_violations_final.csv (0% REVIEW)
- p5063_violations_final.csv (0% REVIEW)
"""
import csv
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set

BASE_DIR = Path(__file__).resolve().parent.parent
P8814_INPUT = BASE_DIR / "data" / "output" / "20261101" / "p8814_violations_from_wd.csv"
P5063_INPUT = BASE_DIR / "data" / "output" / "20261101" / "p5063_violations_from_wd.csv"
P8814_OUTPUT = BASE_DIR / "data" / "output" / "20261101" / "p8814_violations_final.csv"
P5063_OUTPUT = BASE_DIR / "data" / "output" / "20261101" / "p5063_violations_final.csv"

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def normalize_text(value: str) -> str:
    """Normalize text to lowercase tokens only."""
    return " ".join(TOKEN_RE.findall((value or "").lower()))


def text_tokens(value: str) -> Set[str]:
    """Extract set of normalized tokens."""
    return set(normalize_text(value).split())


def compute_similarity(text1: str, text2: str) -> int:
    """Compute token overlap similarity."""
    tokens1 = text_tokens(text1)
    tokens2 = text_tokens(text2)
    if not tokens1 or not tokens2:
        return 0
    return len(tokens1 & tokens2)


def jaccard_similarity(text1: str, text2: str) -> float:
    """Compute Jaccard similarity."""
    tokens1 = text_tokens(text1)
    tokens2 = text_tokens(text2)
    if not tokens1 and not tokens2:
        return 0.0
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return intersection / union if union > 0 else 0.0


def get_pos_from_synset_id(synset_id: str) -> str:
    """Extract POS from synset ID."""
    if '-' in synset_id:
        suffix = synset_id.rsplit('-', 1)[-1]
        pos_map = {'n': 'noun', 'v': 'verb', 'a': 'adj', 'r': 'adverb', 's': 'satellite'}
        return pos_map.get(suffix, suffix)
    return 'unknown'


def categorize_p8814_final(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    FINAL categorization for P8814 - NO REVIEW LEFT.
    Uses aggressive thresholds to make a decision on every case.
    """
    synset_groups = defaultdict(list)
    for row in rows:
        synset_groups[row['synset_id']].append(row)
    
    categorized_rows = []
    
    for synset_id, synset_rows in synset_groups.items():
        definition = synset_rows[0]['synset_definition']
        members_str = synset_rows[0]['synset_members']
        members = set(m.strip().lower() for m in members_str.split('|') if m.strip())
        
        qid_info = []
        for row in synset_rows:
            qid = row['qid']
            label = row['wikidata_label'].strip()
            description = (row.get('wikidata_description') or '').strip()
            qid_info.append({
                'qid': qid,
                'label': label,
                'description': description,
                'label_norm': label.lower(),
            })
        
        # Remove duplicates
        unique_qids = {qi['qid']: qi for qi in qid_info}
        qid_info = list(unique_qids.values())
        num_qids = len(qid_info)
        
        # Compute similarity scores
        similarity_scores = {}
        for qi in qid_info:
            sim = compute_similarity(definition, qi['description'])
            jaccard = jaccard_similarity(definition, qi['description'])
            similarity_scores[qi['qid']] = {'token_overlap': sim, 'jaccard': jaccard}
        
        # Always make a decision - no REVIEW
        category = ""
        is_real_violation = ""
        recommendation = ""
        notes = ""
        confidence = 0
        
        if num_qids == 1:
            category = "SINGLE_QID"
            is_real_violation = "FALSE"
            confidence = 100
            recommendation = "KEEP"
            notes = "Only one QID for this synset"
            
        elif num_qids == 2:
            q1, q2 = qid_info[0], qid_info[1]
            l1, l2 = q1['label_norm'], q2['label_norm']
            s1, s2 = similarity_scores[q1['qid']], similarity_scores[q2['qid']]
            
            l1_in_members = any(l1 in m for m in members)
            l2_in_members = any(l2 in m for m in members)
            
            # Rule: If both in members, always KEEP (valid polysemy/synonym)
            if l1_in_members and l2_in_members:
                category = "BOTH_IN_MEMBERS"
                is_real_violation = "FALSE"
                confidence = 90
                recommendation = "KEEP_BOTH"
                notes = f"Both labels in synset members: {members_str}"
                
            # Rule: If one in members, one not
            elif l1_in_members or l2_in_members:
                # If non-member has very low similarity (0-1), REMOVE it
                non_member = q2 if l1_in_members else q1
                if similarity_scores[non_member['qid']]['token_overlap'] <= 1:
                    category = "ONE_IN_MEMBERS_DESC_MISMATCH"
                    is_real_violation = "TRUE"
                    confidence = 90
                    recommendation = f"REMOVE {non_member['qid']}"
                    notes = f"QID in members: {q1['qid'] if l1_in_members else q2['qid']}, Not in members and low sim: {non_member['qid']}"
                else:
                    # Medium similarity - assume valid
                    category = "ONE_IN_MEMBERS_MEDIUM_SIM"
                    is_real_violation = "FALSE"
                    confidence = 70
                    recommendation = "KEEP_BOTH - Medium similarity"
                    notes = f"One in members, medium similarity suggests valid"
                
            # Rule: Neither in members
            else:
                # High similarity for both - assume synonyms
                if s1['token_overlap'] >= 3 and s2['token_overlap'] >= 3:
                    category = "NEITHER_IN_MEMBERS_BUT_SIMILAR"
                    is_real_violation = "FALSE"
                    confidence = 80
                    recommendation = "KEEP_BOTH - Similar concepts"
                    notes = f"Neither in members but high similarity"
                # Low similarity for both - ERROR
                else:
                    category = "DIFFERENT_CONCEPTS"
                    is_real_violation = "TRUE"
                    confidence = 90
                    recommendation = "REMOVE_ONE - Different concepts"
                    notes = f"Neither in members, low similarity"
        
        else:  # 3+ QIDs
            in_members = [qi for qi in qid_info if any(qi['label_norm'] in m for m in members)]
            not_in_members = [qi for qi in qid_info if not any(qi['label_norm'] in m for m in members)]
            
            # If all in members, KEEP
            if len(not_in_members) == 0:
                category = "MULTIPLE_QIDS_ALL_IN_MEMBERS"
                is_real_violation = "FALSE"
                confidence = 85
                recommendation = "KEEP_ALL"
                notes = f"All {num_qids} QIDs have labels in synset members"
                
            # If some not in members
            elif len(not_in_members) > 0:
                # Check similarity of non-members
                all_not_low = all(similarity_scores[qi['qid']]['token_overlap'] <= 1 for qi in not_in_members)
                
                if all_not_low:
                    category = "MULTIPLE_QIDS_WITH_MISMATCHES"
                    is_real_violation = "TRUE"
                    confidence = 85
                    mismatch_qids = ', '.join(qi['qid'] for qi in not_in_members)
                    recommendation = f"REMOVE: {mismatch_qids}"
                    notes = f"{len(not_in_members)} QIDs not in members with low similarity"
                else:
                    category = "MULTIPLE_QIDS_MIXED"
                    is_real_violation = "FALSE"
                    confidence = 65
                    recommendation = "KEEP_ALL - Mixed but mostly valid"
                    notes = f"{len(in_members)} in members, {len(not_in_members)} not but with ok similarity"
        
        # Add similarity info
        sim_str = ', '.join(f"{qi['qid']}:{similarity_scores[qi['qid']]['token_overlap']}" for qi in qid_info)
        notes += f" | Similarity: {sim_str}"
        
        # Add category to each row
        for row in synset_rows:
            row_copy = row.copy()
            row_copy['category'] = category
            row_copy['is_real_violation'] = is_real_violation
            row_copy['confidence'] = str(confidence)
            row_copy['recommendation'] = recommendation
            row_copy['categorization_notes'] = notes
            row_copy['def_desc_similarity'] = sim_str
            categorized_rows.append(row_copy)
    
    return categorized_rows


def categorize_p5063_final(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    FINAL categorization for P5063 - NO REVIEW LEFT.
    """
    qid_groups = defaultdict(list)
    ili_groups = defaultdict(list)
    
    for row in rows:
        vtype = row.get('violation_type', '')
        if vtype == 'single_value':
            qid_groups[row['qid']].append(row)
        elif vtype == 'unique_value':
            ili_groups[row['ili']].append(row)
    
    categorized_rows = []
    
    # Process single_value: One QID, multiple ILIs
    for qid, qid_rows in qid_groups.items():
        label = qid_rows[0]['wikidata_label']
        description = (qid_rows[0].get('wikidata_description') or '').strip()
        
        ili_info = []
        for row in qid_rows:
            ili = row['ili']
            synset_def = row['synset_definition']
            synset_id = row['synset_id']
            members = row['synset_members']
            ili_info.append({
                'ili': ili,
                'synset_definition': synset_def,
                'synset_id': synset_id,
                'members': members,
            })
        
        unique_ilis = {ii['ili']: ii for ii in ili_info}
        ili_info = list(unique_ilis.values())
        num_ilis = len(ili_info)
        
        similarity_scores = {}
        for ii in ili_info:
            sim = compute_similarity(description, ii['synset_definition'])
            jaccard = jaccard_similarity(description, ii['synset_definition'])
            similarity_scores[ii['ili']] = {'token_overlap': sim, 'jaccard': jaccard}
        
        has_pos_conflict = len(set(get_pos_from_synset_id(ii['synset_id']) for ii in ili_info)) > 1
        
        # Always make a decision
        category = ""
        is_real_violation = ""
        recommendation = ""
        notes = ""
        confidence = 0
        
        if num_ilis == 1:
            category = "SINGLE_ILI"
            is_real_violation = "FALSE"
            confidence = 100
            recommendation = "KEEP"
            notes = "Only one ILI for this QID"
            
        elif num_ilis == 2:
            i1, i2 = ili_info[0], ili_info[1]
            s1, s2 = similarity_scores[i1['ili']], similarity_scores[i2['ili']]
            
            # High similarity for both - KEEP
            if s1['token_overlap'] >= 3 and s2['token_overlap'] >= 3:
                category = "MULTIPLE_ILIS_HIGH_SIM"
                is_real_violation = "FALSE"
                confidence = 85
                recommendation = "KEEP_BOTH"
                notes = f"Both ILIs have high similarity"
                
            # POS conflict - KEEP (different senses)
            elif has_pos_conflict:
                category = "MULTIPLE_ILIS_POS_DIFFERENCE"
                is_real_violation = "FALSE"
                confidence = 80
                recommendation = "KEEP_BOTH - Different POS"
                pos_info = ', '.join(f"{ii['synset_id']}:{get_pos_from_synset_id(ii['synset_id'])}" for ii in ili_info)
                notes = f"Different POS: {pos_info}"
                
            # One low, one high - REMOVE the low one
            elif (s1['token_overlap'] >= 3 and s2['token_overlap'] <= 2) or \
                 (s2['token_overlap'] >= 3 and s1['token_overlap'] <= 2):
                low_ili = i1['ili'] if s1['token_overlap'] <= 2 else i2['ili']
                category = "MULTIPLE_ILIS_MISMATCH"
                is_real_violation = "TRUE"
                confidence = 85
                recommendation = f"REMOVE {low_ili}"
                notes = f"One ILI has low similarity: {low_ili}"
                
            # Both medium - assume valid (different aspects)
            else:
                category = "MULTIPLE_ILIS_MEDIUM_SIM"
                is_real_violation = "FALSE"
                confidence = 70
                recommendation = "KEEP_BOTH - Different aspects"
                notes = f"Both have medium similarity, likely different aspects"
        
        else:  # 3+ ILIs
            avg_sim = sum(similarity_scores[ii['ili']]['token_overlap'] for ii in ili_info) / num_ilis
            
            if avg_sim >= 3:
                category = "MULTIPLE_ILIS_MOST_VALID"
                is_real_violation = "FALSE"
                confidence = 80
                recommendation = "KEEP_ALL"
                notes = f"Most ILIs have high similarity (avg: {avg_sim:.1f})"
                
            elif avg_sim >= 1.5:
                category = "MULTIPLE_ILIS_MIXED"
                is_real_violation = "FALSE"
                confidence = 70
                recommendation = "KEEP_ALL - Mixed but acceptable"
                notes = f"Mixed similarity (avg: {avg_sim:.1f})"
                
            else:
                category = "MULTIPLE_ILIS_LOW_SIM"
                is_real_violation = "TRUE"
                confidence = 85
                recommendation = "REMOVE_DUPLICATES"
                notes = f"Most ILIs have low similarity (avg: {avg_sim:.1f})"
        
        sim_str = ', '.join(f"{ii['ili']}:{similarity_scores[ii['ili']]['token_overlap']}" for ii in ili_info)
        notes += f" | Similarity: {sim_str}"
        
        for row in qid_rows:
            row_copy = row.copy()
            row_copy['category'] = category
            row_copy['is_real_violation'] = is_real_violation
            row_copy['confidence'] = str(confidence)
            row_copy['recommendation'] = recommendation
            row_copy['categorization_notes'] = notes
            row_copy['def_desc_similarity'] = sim_str
            categorized_rows.append(row_copy)
    
    # Process unique_value: One ILI, multiple QIDs
    for ili, ili_rows in ili_groups.items():
        qid_info = []
        for row in ili_rows:
            qid = row['qid']
            label = row['wikidata_label']
            description = (row.get('wikidata_description') or '').strip()
            qid_info.append({
                'qid': qid,
                'label': label,
                'description': description,
            })
        
        unique_qids = {qi['qid']: qi for qi in qid_info}
        qid_info = list(unique_qids.values())
        num_qids = len(qid_info)
        
        # Check for duplicate labels
        label_groups = defaultdict(list)
        for qi in qid_info:
            label_groups[qi['label'].lower()].append(qi['qid'])
        has_duplicate_labels = any(len(v) > 1 for v in label_groups.values())
        
        # Compute pairwise similarities
        pairwise_sims = []
        for i in range(num_qids):
            for j in range(i+1, num_qids):
                q1, q2 = qid_info[i], qid_info[j]
                sim = compute_similarity(q1['description'], q2['description'])
                label_sim = compute_similarity(q1['label'], q2['label'])
                pairwise_sims.append((q1['qid'], q2['qid'], sim))
        
        avg_sim = sum(s[2] for s in pairwise_sims) / len(pairwise_sims) if pairwise_sims else 0
        
        # Always make a decision
        category = ""
        is_real_violation = ""
        recommendation = ""
        notes = ""
        confidence = 0
        
        if has_duplicate_labels:
            category = "DUPLICATE_LABELS"
            is_real_violation = "FALSE"
            confidence = 80
            recommendation = "CHECK_REDIRECTS"
            notes = f"Same label for multiple QIDs"
            for label, qids in label_groups.items():
                if len(qids) > 1:
                    notes += f" | '{label}': {', '.join(qids)}"
            
        elif avg_sim >= 3:
            category = "SIMILAR_QIDS"
            is_real_violation = "FALSE"
            confidence = 85
            recommendation = "KEEP_ALL - Similar concepts"
            notes = f"QIDs have similar descriptions (avg: {avg_sim:.1f})"
            
        elif avg_sim >= 1.5:
            category = "MEDIUM_SIMILAR_QIDS"
            is_real_violation = "FALSE"
            confidence = 75
            recommendation = "KEEP_ALL - Related concepts"
            notes = f"QIDs have medium similarity (avg: {avg_sim:.1f})"
            
        else:
            category = "DISSIMILAR_QIDS"
            is_real_violation = "TRUE"
            confidence = 85
            recommendation = "REMOVE_DUPLICATES"
            notes = f"QIDs have low similarity (avg: {avg_sim:.1f})"
        
        sim_str = '; '.join(f"{s[0]}-{s[1]}:{s[2]}" for s in pairwise_sims[:5])
        if len(pairwise_sims) > 5:
            sim_str += f" +{len(pairwise_sims)-5} more"
        notes += f" | Pairwise sims: {sim_str}"
        
        for row in ili_rows:
            row_copy = row.copy()
            row_copy['category'] = category
            row_copy['is_real_violation'] = is_real_violation
            row_copy['confidence'] = str(confidence)
            row_copy['recommendation'] = recommendation
            row_copy['categorization_notes'] = notes
            row_copy['def_desc_similarity'] = sim_str
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


def main(run_dir=None):
    global P8814_INPUT, P5063_INPUT, P8814_OUTPUT, P5063_OUTPUT
    if run_dir:
        run_dir = Path(run_dir)
        P8814_INPUT, P5063_INPUT = run_dir / "p8814_violations_from_wd.csv", run_dir / "p5063_violations_from_wd.csv"
        P8814_OUTPUT, P5063_OUTPUT = run_dir / "p8814_violations_final.csv", run_dir / "p5063_violations_final.csv"
    print("=" * 70)
    print("FINAL CATEGORIZATION - 100% COVERAGE")
    print("=" * 70)
    
    # Process P8814
    print("\nProcessing P8814 violations...")
    with open(P8814_INPUT, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        p8814_rows = list(reader)
    
    print(f"  Loaded {len(p8814_rows)} rows")
    categorized_p8814 = categorize_p8814_final(p8814_rows)
    write_csv(P8814_OUTPUT, categorized_p8814)
    
    # Process P5063
    print("\nProcessing P5063 violations...")
    with open(P5063_INPUT, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        p5063_rows = list(reader)
    
    print(f"  Loaded {len(p5063_rows)} rows")
    categorized_p5063 = categorize_p5063_final(p5063_rows)
    write_csv(P5063_OUTPUT, categorized_p5063)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY - 100% COVERAGE")
    print("=" * 70)
    
    def print_summary(rows, name):
        from collections import Counter
        cats = Counter(r['category'] for r in rows)
        real_count = sum(1 for r in rows if r['is_real_violation'] == 'TRUE')
        false_count = sum(1 for r in rows if r['is_real_violation'] == 'FALSE')
        review_count = sum(1 for r in rows if r['is_real_violation'] == 'REVIEW')
        
        print(f"\n{name} Violations ({len(rows)} rows):")
        print(f"  Total: {len(rows)}")
        print(f"  Real violations: {real_count} ({real_count/len(rows)*100:.1f}%)")
        print(f"  Valid/keep: {false_count} ({false_count/len(rows)*100:.1f}%)")
        print(f"  REVIEW: {review_count} ({review_count/len(rows)*100:.1f}%)")
        
        print(f"\n  By category:")
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            real_pct = sum(1 for r in rows if r['category'] == cat and r['is_real_violation'] == 'TRUE') / count * 100 if count > 0 else 0
            print(f"    {cat}: {count}")
    
    print_summary(categorized_p8814, "P8814")
    print_summary(categorized_p5063, "P5063")
    
    print("\nDone! Final files written to:")
    print(f"  {P8814_OUTPUT}")
    print(f"  {P5063_OUTPUT}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else None)
