"""
Enhanced categorization of P5063 and P8814 violations with deep semantic analysis.

Adds columns:
- category: Detailed categorization
- is_real_violation: TRUE/FALSE/REVIEW
- def_desc_similarity: Token overlap score
- confidence: 0-100 confidence in categorization
- recommendation: Suggested action
- notes: Explanation

This script attempts to handle:
- Ambiguous polysemy
- Linguistic nuances  
- Part-of-speech conflicts
- Redirect and historical name detection

Usage:
  python scripts/categorize_violations_enhanced.py
"""
import csv
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
P8814_INPUT = BASE_DIR / "data" / "output" / "20260929" / "p8814_violations_from_wd.csv"
P5063_INPUT = BASE_DIR / "data" / "output" / "20260929" / "p5063_violations_from_wd.csv"
P8814_OUTPUT = BASE_DIR / "data" / "output" / "20260929" / "p8814_violations_enhanced.csv"
P5063_OUTPUT = BASE_DIR / "data" / "output" / "20260929" / "p5063_violations_enhanced.csv"

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
STOP_WORDS = {'the', 'a', 'an', 'of', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}


def normalize_text(value: str) -> str:
    """Normalize text to lowercase tokens, removing stop words."""
    tokens = TOKEN_RE.findall((value or "").lower())
    return " ".join(t for t in tokens if t not in STOP_WORDS)


def text_tokens(value: str) -> Set[str]:
    """Extract set of normalized tokens."""
    return set(normalize_text(value).split())


def compute_similarity(text1: str, text2: str) -> int:
    """Compute token overlap similarity between two texts."""
    tokens1 = text_tokens(text1)
    tokens2 = text_tokens(text2)
    if not tokens1 or not tokens2:
        return 0
    return len(tokens1 & tokens2)


def jaccard_similarity(text1: str, text2: str) -> float:
    """Compute Jaccard similarity (intersection/union)."""
    tokens1 = text_tokens(text1)
    tokens2 = text_tokens(text2)
    if not tokens1 and not tokens2:
        return 0.0
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return intersection / union if union > 0 else 0.0


def is_substring(a: str, b: str) -> bool:
    """Check if a is substring of b (normalized)."""
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    return a_norm in b_norm or b_norm in a_norm


def contains_all_tokens(small: str, large: str) -> bool:
    """Check if all tokens in small are in large."""
    small_tokens = text_tokens(small)
    large_tokens = text_tokens(large)
    return small_tokens.issubset(large_tokens)


# ============================================================
# POLYSEMY AND SEMANTIC ANALYSIS HELPERS
# ============================================================


def is_polysemy_case(synset_members: str, qid_labels: List[str]) -> bool:
    """
    Check if this might be a polysemy case (one word, multiple meanings).
    """
    members = set(m.strip().lower() for m in synset_members.split('|') if m.strip())
    labels = [l.strip().lower() for l in qid_labels if l.strip()]
    
    # If all labels are variations of the same word, likely polysemy
    if len(set(labels)) == len(labels):
        # All labels are distinct
        base_words = [l.split()[0] for l in labels]  # First word
        if len(set(base_words)) == 1:
            return True  # Same base word, different meanings
    
    return False


def is_pos_conflict(synset_ids: List[str]) -> bool:
    """
    Check if synsets have different parts of speech based on synset ID suffix.
    Synset IDs end with: -n (noun), -v (verb), -a (adj), -r (adverb), -s (satellite adj)
    """
    suffixes = set()
    for sid in synset_ids:
        if '-' in sid:
            suffixes.add(sid.rsplit('-', 1)[-1])
    return len(suffixes) > 1


def get_pos_from_synset_id(synset_id: str) -> str:
    """Extract POS from synset ID."""
    if '-' in synset_id:
        suffix = synset_id.rsplit('-', 1)[-1]
        pos_map = {'n': 'noun', 'v': 'verb', 'a': 'adj', 'r': 'adverb', 's': 'satellite'}
        return pos_map.get(suffix, suffix)
    return 'unknown'


def is_synonym_pair(label1: str, label2: str) -> bool:
    """
    Check if two labels are synonyms using simple rules.
    """
    l1, l2 = label1.lower(), label2.lower()
    
    # Exact match
    if l1 == l2:
        return True
    
    # One is substring of other
    if l1 in l2 or l2 in l1:
        return True
    
    # Same base word
    words1 = set(l1.split())
    words2 = set(l2.split())
    if words1 & words2:
        return True
    
    return False


def is_redirect_or_historical(qid1: str, qid2: str, label1: str, label2: str) -> bool:
    """
    Heuristic: Check if one QID might be a redirect or historical name of another.
    """
    # Simple check: if labels are the same or very similar, one might be redirect
    if label1.lower() == label2.lower():
        return True
    if is_synonym_pair(label1, label2):
        return True
    return False


# ============================================================
# ENHANCED CATEGORIZATION FUNCTIONS
# ============================================================


def categorize_p8814_enhanced(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Enhanced categorization for P8814 violations with deep analysis.
    """
    # Group rows by synset_id
    synset_groups = defaultdict(list)
    for row in rows:
        synset_groups[row['synset_id']].append(row)
    
    categorized_rows = []
    
    for synset_id, synset_rows in synset_groups.items():
        # Get synset info from first row
        definition = synset_rows[0]['synset_definition']
        members_str = synset_rows[0]['synset_members']
        members = set(m.strip().lower() for m in members_str.split('|') if m.strip())
        ili = synset_rows[0]['synset_ili']
        
        # Get all QIDs, labels, and descriptions for this synset
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
        
        # Compute similarity scores for each QID
        similarity_scores = {}
        for qi in qid_info:
            sim = compute_similarity(definition, qi['description'])
            jaccard = jaccard_similarity(definition, qi['description'])
            similarity_scores[qi['qid']] = {'token_overlap': sim, 'jaccard': jaccard}
        
        # Determine category with enhanced logic
        category = "UNKNOWN"
        is_real_violation = "REVIEW"
        confidence = 50
        recommendation = "REVIEW"
        notes = ""
        
        num_qids = len(qid_info)
        
        if num_qids == 1:
            category = "SINGLE_QID"
            is_real_violation = "FALSE"
            confidence = 100
            recommendation = "KEEP"
            notes = "Only one QID for this synset"
            
        elif num_qids == 2:
            q1, q2 = qid_info[0], qid_info[1]
            l1, l2 = q1['label_norm'], q2['label_norm']
            d1, d2 = q1['description'], q2['description']
            s1, s2 = similarity_scores[q1['qid']], similarity_scores[q2['qid']]
            
            # Check if labels are in members
            l1_in_members = any(l1 in m for m in members)
            l2_in_members = any(l2 in m for m in members)
            
            # Check various conditions
            labels_identical = l1 == l2
            labels_synonyms = is_synonym_pair(q1['label'], q2['label'])
            
            # High similarity for both = likely valid
            both_high_sim = s1['token_overlap'] >= 3 and s2['token_overlap'] >= 3
            
            # One high, one low = likely one is wrong
            one_high_one_low = (s1['token_overlap'] >= 3 and s2['token_overlap'] <= 2) or \
                              (s2['token_overlap'] >= 3 and s1['token_overlap'] <= 2)
            
            # Both low but labels in members = might be polysemy
            both_low_but_in_members = s1['token_overlap'] <= 2 and s2['token_overlap'] <= 2 and \
                                       l1_in_members and l2_in_members
            
            # Check for POS conflict in synsets
            synset_ids = [r['synset_id'] for r in synset_rows if r.get('synset_id')]
            has_pos_conflict = is_pos_conflict(synset_ids)
            
            # === DECISION TREE ===
            
            # Rule 1: Both in members + high similarity = VALID
            if l1_in_members and l2_in_members and both_high_sim:
                category = "BOTH_IN_MEMBERS_HIGH_SIM"
                is_real_violation = "FALSE"
                confidence = 95
                recommendation = "KEEP_BOTH"
                notes = f"Both labels in members with high similarity ({s1['token_overlap']}, {s2['token_overlap']})"
                
            # Rule 2: Labels are synonyms = VALID
            elif labels_synonyms or labels_identical:
                category = "SYNONYMS_SAME_CONCEPT"
                is_real_violation = "FALSE"
                confidence = 90
                recommendation = "KEEP_BOTH"
                notes = f"Labels '{q1['label']}' and '{q2['label']}' are synonyms"
                
            # Rule 3: Both in members but low similarity = POLYSEMY (valid)
            elif l1_in_members and l2_in_members and both_low_but_in_members:
                category = "BOTH_IN_MEMBERS_POLYSEMY"
                is_real_violation = "FALSE"
                confidence = 75
                recommendation = "KEEP_BOTH_POLYSEMY"
                notes = f"Both in members but low similarity - likely polysemy. Sim: ({s1['token_overlap']}, {s2['token_overlap']})"
                
            # Rule 4: One in members, one not, low similarity for non-member = ERROR
            elif (l1_in_members and not l2_in_members and s2['token_overlap'] <= 2) or \
                 (l2_in_members and not l1_in_members and s1['token_overlap'] <= 2):
                category = "ONE_IN_MEMBERS_DESC_MISMATCH"
                is_real_violation = "TRUE"
                confidence = 90
                recommendation = f"REMOVE {"Q2" if l1_in_members else "Q1"}"
                not_in_qid = q2['qid'] if l1_in_members else q1['qid']
                notes = f"QID in members but description mismatch for {not_in_qid}. Sim: ({s1['token_overlap']}, {s2['token_overlap']})"
                
            # Rule 5: One in members, one not, medium similarity = REVIEW
            elif (l1_in_members and not l2_in_members and s2['token_overlap'] <= 3) or \
                 (l2_in_members and not l1_in_members and s1['token_overlap'] <= 3):
                category = "ONE_IN_MEMBERS_MEDIUM_SIM"
                is_real_violation = "REVIEW"
                confidence = 60
                recommendation = "REVIEW - Check if concept matches"
                notes = f"One in members, medium similarity. Sim: ({s1['token_overlap']}, {s2['token_overlap']})"
                
            # Rule 6: One in members, one not, high similarity = VALID
            elif l1_in_members or l2_in_members:
                category = "ONE_IN_MEMBERS_HIGH_SIM"
                is_real_violation = "FALSE"
                confidence = 80
                recommendation = "KEEP_BOTH - Different aspects"
                notes = f"One in members but high similarity suggests related concepts"
                
            # Rule 7: Both not in members, high similarity = VALID (synonyms)
            elif not l1_in_members and not l2_in_members and both_high_sim:
                category = "NEITHER_IN_MEMBERS_BUT_SIMILAR"
                is_real_violation = "FALSE"
                confidence = 70
                recommendation = "KEEP_BOTH - Similar concepts"
                notes = f"Neither in members but high similarity. Sim: ({s1['token_overlap']}, {s2['token_overlap']})"
                
            # Rule 8: Both not in members, low similarity = ERROR
            elif not l1_in_members and not l2_in_members and s1['token_overlap'] <= 2 and s2['token_overlap'] <= 2:
                category = "DIFFERENT_CONCEPTS"
                is_real_violation = "TRUE"
                confidence = 95
                recommendation = "REMOVE_ONE - Different concepts"
                notes = f"Neither in members, low similarity. Sim: ({s1['token_overlap']}, {s2['token_overlap']})"
                
            # Rule 9: Check for POS conflict
            elif has_pos_conflict:
                category = "POS_CONFLICT"
                is_real_violation = "FALSE"
                confidence = 70
                recommendation = "KEEP_BOTH - Different POS"
                notes = f"Synsets have different parts of speech - likely valid"
                
            # Rule 10: Default
            else:
                category = "ONE_IN_MEMBERS"
                is_real_violation = "REVIEW"
                confidence = 50
                recommendation = "REVIEW"
                notes = f"QIDs in members: {q1['qid'] if l1_in_members else q2['qid']} | Not in members: {q2['qid'] if l1_in_members else q1['qid']}"
            
            # Add similarity info to notes
            notes += f" | Token overlap: {s1['token_overlap']}, {s2['token_overlap']} | Jaccard: {s1['jaccard']:.2f}, {s2['jaccard']:.2f}"
            
        else:  # 3+ QIDs
            # Analyze all QIDs together
            in_members = [qi for qi in qid_info if any(qi['label_norm'] in m for m in members)]
            not_in_members = [qi for qi in qid_info if not any(qi['label_norm'] in m for m in members)]
            
            all_sims = [similarity_scores[qi['qid']]['token_overlap'] for qi in qid_info]
            avg_sim = sum(all_sims) / len(all_sims)
            
            # If most have high similarity, likely valid
            high_sim_count = sum(1 for s in all_sims if s >= 3)
            
            if high_sim_count >= num_qids - 1:
                category = "MULTIPLE_QIDS_VALID"
                is_real_violation = "FALSE"
                confidence = 80
                recommendation = "KEEP_ALL - Mostly high similarity"
                notes = f"{len(in_members)} in members, {len(not_in_members)} not. Avg similarity: {avg_sim:.1f}"
                
            elif len(not_in_members) > 0 and all(similarity_scores[qi['qid']]['token_overlap'] <= 2 for qi in not_in_members):
                category = "MULTIPLE_QIDS_WITH_MISMATCHES"
                is_real_violation = "TRUE"
                confidence = 85
                mismatch_qids = ', '.join(qi['qid'] for qi in not_in_members)
                recommendation = f"REMOVE: {mismatch_qids}"
                notes = f"{len(not_in_members)} QIDs have low similarity. Avg: {avg_sim:.1f}"
                
            elif is_polysemy_case(members_str, [qi['label'] for qi in qid_info]):
                category = "MULTIPLE_QIDS_POLYSEMY"
                is_real_violation = "FALSE"
                confidence = 70
                recommendation = "KEEP_ALL - Polysemy"
                notes = f"Multiple meanings of same word. Avg similarity: {avg_sim:.1f}"
                
            else:
                category = "MULTIPLE_QIDS"
                is_real_violation = "REVIEW"
                confidence = 50
                recommendation = "REVIEW - Complex case"
                notes = f"Multiple QIDs ({num_qids}). Avg similarity: {avg_sim:.1f}"
        
        # Add category info to each row
        for row in synset_rows:
            row_copy = row.copy()
            row_copy['category'] = category
            row_copy['is_real_violation'] = is_real_violation
            row_copy['confidence'] = str(confidence)
            row_copy['recommendation'] = recommendation
            row_copy['categorization_notes'] = notes
            row_copy['def_desc_similarity'] = ', '.join(
                f"{qi['qid']}:{similarity_scores[qi['qid']]['token_overlap']}" 
                for qi in qid_info
            )
            categorized_rows.append(row_copy)
    
    return categorized_rows


def categorize_p5063_enhanced(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Enhanced categorization for P5063 violations.
    """
    # Group by QID for single_value, by ILI for unique_value
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
        # Get QID info from first row
        label = qid_rows[0]['wikidata_label']
        description = (qid_rows[0].get('wikidata_description') or '').strip()
        
        # Get all ILIs for this QID
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
        
        # Remove duplicates
        unique_ilis = {ii['ili']: ii for ii in ili_info}
        ili_info = list(unique_ilis.values())
        num_ilis = len(ili_info)
        
        # Compute similarity between QID description and each synset definition
        similarity_scores = {}
        for ii in ili_info:
            sim = compute_similarity(description, ii['synset_definition'])
            jaccard = jaccard_similarity(description, ii['synset_definition'])
            similarity_scores[ii['ili']] = {'token_overlap': sim, 'jaccard': jaccard}
        
        # Check for POS conflict
        synset_ids = [ii['synset_id'] for ii in ili_info]
        has_pos_conflict = is_pos_conflict(synset_ids)
        
        # Check if QID label appears in any synset members
        labels_in_members = []
        for ii in ili_info:
            members = set(m.strip().lower() for m in ii['members'].split('|') if m.strip())
            if any(label.lower() in m for m in members):
                labels_in_members.append(ii['ili'])
        
        # Decision logic
        category = "UNKNOWN"
        is_real_violation = "REVIEW"
        confidence = 50
        recommendation = "REVIEW"
        notes = ""
        
        if num_ilis == 1:
            category = "SINGLE_ILI"
            is_real_violation = "FALSE"
            confidence = 100
            recommendation = "KEEP"
            notes = "Only one ILI for this QID"
            
        elif num_ilis == 2:
            i1, i2 = ili_info[0], ili_info[1]
            s1, s2 = similarity_scores[i1['ili']], similarity_scores[i2['ili']]
            
            # Both have high similarity
            if s1['token_overlap'] >= 4 and s2['token_overlap'] >= 4:
                category = "MULTIPLE_ILIS_HIGH_SIM"
                is_real_violation = "FALSE"
                confidence = 85
                recommendation = "KEEP_BOTH - Both match well"
                notes = f"Both ILIs have high similarity. Sim: {s1['token_overlap']}, {s2['token_overlap']}"
                
            # POS conflict (different POS)
            elif has_pos_conflict:
                category = "MULTIPLE_ILIS_POS_DIFFERENCE"
                is_real_violation = "FALSE"
                confidence = 75
                recommendation = "KEEP_BOTH - Different POS"
                pos_info = ', '.join(f"{ii['synset_id']}:{get_pos_from_synset_id(ii['synset_id'])}" for ii in ili_info)
                notes = f"Different parts of speech: {pos_info}"
                
            # One has high similarity, one low
            elif (s1['token_overlap'] >= 4 and s2['token_overlap'] <= 2) or \
                 (s2['token_overlap'] >= 4 and s1['token_overlap'] <= 2):
                low_ili = i1['ili'] if s1['token_overlap'] <= 2 else i2['ili']
                category = "MULTIPLE_ILIS_MISMATCH"
                is_real_violation = "TRUE"
                confidence = 85
                recommendation = f"REMOVE {low_ili}"
                notes = f"One ILI has low similarity: {low_ili} (sim: {min(s1['token_overlap'], s2['token_overlap'])})"
                
            # Both have medium similarity
            elif s1['token_overlap'] >= 2 and s2['token_overlap'] >= 2:
                category = "MULTIPLE_ILIS_MEDIUM_SIM"
                is_real_violation = "REVIEW"
                confidence = 60
                recommendation = "REVIEW - Check if both ILIs are valid"
                notes = f"Both have medium similarity. Sim: {s1['token_overlap']}, {s2['token_overlap']}"
                
            # Both have low similarity
            else:
                category = "MULTIPLE_ILIS_LOW_SIM"
                is_real_violation = "TRUE"
                confidence = 90
                recommendation = "REMOVE_ONE - Both have low similarity"
                notes = f"Both ILIs have low similarity. Sim: {s1['token_overlap']}, {s2['token_overlap']}"
                
            # Add similarity to notes
            notes += f" | Token overlap: {s1['token_overlap']}, {s2['token_overlap']}"
            
        else:  # 3+ ILIs
            avg_sim = sum(similarity_scores[ii['ili']]['token_overlap'] for ii in ili_info) / num_ilis
            high_sim_count = sum(1 for ii in ili_info if similarity_scores[ii['ili']]['token_overlap'] >= 4)
            
            if high_sim_count >= num_ilis - 1:
                category = "MULTIPLE_ILIS_MOST_VALID"
                is_real_violation = "FALSE"
                confidence = 80
                recommendation = "KEEP_ALL - Mostly valid"
                notes = f"{high_sim_count}/{num_ilis} ILIs have high similarity. Avg: {avg_sim:.1f}"
                
            elif has_pos_conflict:
                category = "MULTIPLE_ILIS_POS_DIFFERENCES"
                is_real_violation = "FALSE"
                confidence = 70
                recommendation = "KEEP_ALL - Different POS"
                pos_info = ', '.join(f"{ii['synset_id']}:{get_pos_from_synset_id(ii['synset_id'])}" for ii in ili_info)
                notes = f"Multiple POS: {pos_info}. Avg sim: {avg_sim:.1f}"
                
            else:
                category = "MULTIPLE_ILIS"
                is_real_violation = "REVIEW"
                confidence = 50
                recommendation = "REVIEW - Complex case"
                notes = f"{num_ilis} ILIs. Avg similarity: {avg_sim:.1f}"
        
        # Add category info to each row
        for row in qid_rows:
            row_copy = row.copy()
            row_copy['category'] = category
            row_copy['is_real_violation'] = is_real_violation
            row_copy['confidence'] = str(confidence)
            row_copy['recommendation'] = recommendation
            row_copy['categorization_notes'] = notes
            row_copy['def_desc_similarity'] = ', '.join(
                f"{ii['ili']}:{similarity_scores[ii['ili']]['token_overlap']}" 
                for ii in ili_info
            )
            categorized_rows.append(row_copy)
    
    # Process unique_value: One ILI, multiple QIDs
    for ili, ili_rows in ili_groups.items():
        # Get ILI info
        # All rows should have same ILI
        
        # Get all QIDs for this ILI
        qid_info = []
        for row in ili_rows:
            qid = row['qid']
            label = row['wikidata_label']
            description = (row.get('wikidata_description') or '').strip()
            synset_def = row.get('synset_definition', '')
            qid_info.append({
                'qid': qid,
                'label': label,
                'description': description,
                'synset_definition': synset_def,
            })
        
        # Remove duplicates
        unique_qids = {qi['qid']: qi for qi in qid_info}
        qid_info = list(unique_qids.values())
        num_qids = len(qid_info)
        
        # Compute similarity
        similarity_scores = {}
        for qi in qid_info:
            # For unique_value, we compare QID descriptions to each other
            pass
        
        # For unique_value, we need to check if QIDs are similar
        # Compute pairwise similarities
        pairwise_sims = []
        for i in range(num_qids):
            for j in range(i+1, num_qids):
                q1, q2 = qid_info[i], qid_info[j]
                sim = compute_similarity(q1['description'], q2['description'])
                label_sim = compute_similarity(q1['label'], q2['label'])
                pairwise_sims.append((q1['qid'], q2['qid'], sim, label_sim))
        
        avg_sim = sum(s[2] for s in pairwise_sims) / len(pairwise_sims) if pairwise_sims else 0
        
        # Check if any QIDs are redirects (same label)
        label_groups = defaultdict(list)
        for qi in qid_info:
            label_groups[qi['label'].lower()].append(qi['qid'])
        
        has_duplicate_labels = any(len(v) > 1 for v in label_groups.values())
        
        # Decision logic
        category = "UNIQUE_VALUE_VIOLATION"
        is_real_violation = "REVIEW"
        confidence = 50
        recommendation = "REVIEW"
        notes = f"ILI {ili} maps to {num_qids} QIDs"
        
        if has_duplicate_labels:
            category = "DUPLICATE_LABELS"
            is_real_violation = "REVIEW"
            confidence = 70
            recommendation = "CHECK_REDIRECTS - Same label for multiple QIDs"
            for label, qids in label_groups.items():
                if len(qids) > 1:
                    notes += f" | Label '{label}': {', '.join(qids)}"
            
        elif avg_sim >= 4:
            category = "SIMILAR_QIDS"
            is_real_violation = "FALSE"
            confidence = 80
            recommendation = "KEEP_ALL - QIDs are similar"
            notes += f" | Avg description similarity: {avg_sim:.1f}"
            
        elif avg_sim >= 2:
            category = "MEDIUM_SIMILAR_QIDS"
            is_real_violation = "REVIEW"
            confidence = 60
            recommendation = "REVIEW - Medium similarity"
            notes += f" | Avg description similarity: {avg_sim:.1f}"
            
        else:
            category = "DISSIMILAR_QIDS"
            is_real_violation = "TRUE"
            confidence = 85
            recommendation = "REMOVE_DUPLICATES - Low similarity"
            notes += f" | Avg description similarity: {avg_sim:.1f}"
        
        # Add similarity info
        sim_str = '; '.join(f"{s[0]}-{s[1]}:{s[2]}" for s in pairwise_sims[:5])
        if len(pairwise_sims) > 5:
            sim_str += f" +{len(pairwise_sims)-5} more"
        notes += f" | Pairwise sims: {sim_str}"
        
        # Add category info to each row
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


def main():
    print("=" * 70)
    print("ENHANCED VIOLATION CATEGORIZATION")
    print("=" * 70)
    
    # Process P8814
    print("\nProcessing P8814 violations...")
    with open(P8814_INPUT, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        p8814_rows = list(reader)
    
    print(f"  Loaded {len(p8814_rows)} rows")
    categorized_p8814 = categorize_p8814_enhanced(p8814_rows)
    write_csv(P8814_OUTPUT, categorized_p8814)
    
    # Process P5063
    print("\nProcessing P5063 violations...")
    with open(P5063_INPUT, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        p5063_rows = list(reader)
    
    print(f"  Loaded {len(p5063_rows)} rows")
    categorized_p5063 = categorize_p5063_enhanced(p5063_rows)
    write_csv(P5063_OUTPUT, categorized_p5063)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    def print_summary(rows, name):
        cats = defaultdict(int)
        real_count = 0
        review_count = 0
        false_count = 0
        for row in rows:
            cat = row.get('category', 'UNKNOWN')
            cats[cat] += 1
            if row.get('is_real_violation') == 'TRUE':
                real_count += 1
            elif row.get('is_real_violation') == 'REVIEW':
                review_count += 1
            else:
                false_count += 1
        
        print(f"\n{name} Violations ({len(rows)} rows):")
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            real_pct = sum(1 for r in rows if r['category'] == cat and r['is_real_violation'] == 'TRUE') / count * 100 if count > 0 else 0
            print(f"  {cat}: {count}")
        
        print(f"\n  Real: {real_count} ({real_count/len(rows)*100:.1f}%)")
        print(f"  Review: {review_count} ({review_count/len(rows)*100:.1f}%)")
        print(f"  False: {false_count} ({false_count/len(rows)*100:.1f}%)")
    
    print_summary(categorized_p8814, "P8814")
    print_summary(categorized_p5063, "P5063")
    
    print("\nDone! Enhanced files written to:")
    print(f"  {P8814_OUTPUT}")
    print(f"  {P5063_OUTPUT}")


if __name__ == "__main__":
    main()
