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
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path("data/output/20261101")
QUICKSTATEMENTS_DIR = OUTPUT_DIR / "quickstatements"
MANUAL_REVIEW_DIR = OUTPUT_DIR / "manual_review"


WEAK_REASONS = {"fallback", "score_tie"}  # keep chosen without real evidence -> needs a human
DECISION_ACTIONS = {"keep", "leave", "defer"}


def load_decisions(path=None):
    """Human decisions from manual_review/decisions.csv (optional; one row per duplicate group).

    action=keep: keep keep_qid, remove the statement from every other QID in the group.
    action=leave: no removals - the group is treated as a valid duplicate.
    action=defer: no removals yet - the group stays in the review queue.
    Rows with an empty action are template placeholders and are ignored.
    Decisions beat the source pick, which beats the heuristics (reason 'decision').
    """
    path = path or OUTPUT_DIR / "manual_review" / "decisions.csv"
    decisions = {}
    if not Path(path).exists():
        return decisions
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row.get("prop", "").strip(), row.get("value", "").strip())
            action = (row.get("action") or "").strip().lower()
            if not action:
                continue
            if action not in DECISION_ACTIONS:
                raise ValueError(f"decisions.csv: unknown action {action!r} for {key[0]} {key[1]}")
            if key in decisions:
                raise ValueError(f"decisions.csv: duplicate decision for {key[0]} {key[1]}")
            decisions[key] = {"action": action,
                              "keep_qid": (row.get("keep_qid") or "").strip(),
                              "note": (row.get("note") or "").strip()}
    return decisions


def check_unknown_decisions(decisions, seen_groups):
    """Every decision must name a real duplicate group; error instead of ignoring."""
    unknown = sorted(set(decisions) - seen_groups)
    if unknown:
        raise ValueError("decisions.csv names groups with no real violation: "
                         + "; ".join(f"{p} {v}" for p, v in unknown))


def apply_decision(decision, qid_data_list, decision_key):
    """Turn a group's decision into (keep_qid, reason) or a hold action.

    Returns ('hold', reason) for leave/defer; ('keep'/'remove' handling stays with the caller).
    """
    if decision["action"] == "leave":
        return "hold", "decision_leave"
    if decision["action"] == "defer":
        return "hold", "defer"
    if decision["action"] == "keep":
        group_qids = [q["qid"] for q in qid_data_list]
        if decision["keep_qid"] not in group_qids:
            raise ValueError(f"decisions.csv: keep_qid {decision['keep_qid']} is not in the "
                             f"group {decision_key[0]} {decision_key[1]} {group_qids}")
        return decision["keep_qid"], "decision"
    raise ValueError(f"unknown action {decision['action']!r}")


def load_source_picks(path=None):
    """(prop, value) -> QID that english-wordnet / english-namenet name, from crosscheck_sources.py."""
    path = path or OUTPUT_DIR / "source_crosscheck.csv"
    picks = {}
    if Path(path).exists():
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["source_pick"]:
                    picks[(row["prop"], row["value"])] = row["source_pick"]
    return picks


def choose_keep_p8814(qid_data_list, source_pick=None):
    """Return (qid_to_keep, reason). The source repos' QID wins; heuristics only fill the gaps."""
    qids = [q["qid"] for q in qid_data_list]
    if source_pick in qids:
        return source_pick, "source"

    notes = qid_data_list[0].get("notes", "")

    # Notes name the QID that is in the synset members
    if "QID in members:" in notes:
        try:
            return notes.split("QID in members:")[1].strip().split(",")[0].strip(), "members_note"
        except (IndexError, AttributeError):
            pass

    # Similarity scores from the notes
    if "Similarity:" in notes:
        try:
            similarities = {}
            for part in notes.split("Similarity:")[1].strip().split(","):
                part = part.strip()
                if ":" in part:
                    similarities[part.split(":")[0].strip()] = int(part.split(":")[1].strip().split("|")[0].strip())
            if similarities:
                return max(similarities, key=similarities.get), "similarity_note"
        except (IndexError, ValueError):
            pass

    members = qid_data_list[0].get("synset_members", "").lower()
    if members:
        for qd in qid_data_list:
            label = qd.get("wd_label", "").lower()
            if label and label in members:
                return qd["qid"], "label_in_members"

    definition = qid_data_list[0].get("synset_definition", "").lower()
    if definition:
        for qd in qid_data_list:
            label = qd.get("wd_label", "").lower()
            if label and label in definition:
                return qd["qid"], "label_in_definition"

    return qid_data_list[0]["qid"], "fallback"


def choose_keep_p5063(qid_data_list, source_pick=None):
    """Return (qid_to_keep, reason): source repos first, then label/description similarity scoring."""
    qids = [q["qid"] for q in qid_data_list]
    if source_pick in qids:
        return source_pick, "source"

    scored = []
    for qd in qid_data_list:
        wd_label = qd.get("wd_label", "").lower()
        wd_desc = qd.get("wd_description", "").lower()
        synset_def = qd.get("synset_definition", "").lower()
        synset_members = qd.get("synset_members", "").lower()

        score = 0
        if wd_label:
            members_list = synset_members.split("|") if synset_members else []
            if any(member.strip() in wd_label or wd_label in member.strip() for member in members_list):
                score += 10
        if wd_label and synset_def and wd_label in synset_def:
            score += 5
        if wd_desc and synset_def and (wd_desc in synset_def or synset_def in wd_desc):
            score += 3
        scored.append((score, qd["qid"]))

    if not scored:
        return None, "none"
    best = max(s for s, _ in scored)
    winners = [q for s, q in scored if s == best]
    reason = "score" if best > 0 and len(winners) == 1 else ("score_tie" if best > 0 else "fallback")
    return winners[0], reason


def write_keep_log(keep_log):
    path = OUTPUT_DIR / "keep_decisions.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["prop", "value", "keep_qid", "reason", "remove_qids", "note"],
                           restval="")
        w.writeheader()
        w.writerows(keep_log)
    print(f"  keep decisions + reasons: {path}")


def process_p8814_violations(source_picks, decisions, keep_log, seen_groups):
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
        seen_groups.add(("P8814", synset_id))
        decision = decisions.get(("P8814", synset_id))
        if decision:
            keep_or_hold, reason = apply_decision(decision, qid_data_list, ("P8814", synset_id))
            if keep_or_hold == "hold":
                keep_log.append({'prop': 'P8814', 'value': synset_id, 'keep_qid': '',
                                 'reason': reason, 'remove_qids': '', 'note': decision['note']})
                continue
            keep_qid, reason = keep_or_hold, reason
        else:
            keep_qid, reason = choose_keep_p8814(qid_data_list, source_picks.get(('P8814', synset_id)))
        keep_log.append({'prop': 'P8814', 'value': synset_id, 'keep_qid': keep_qid, 'reason': reason,
                         'remove_qids': '|'.join(q['qid'] for q in qid_data_list if q['qid'] != keep_qid),
                         'note': decision['note'] if decision else ''})

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


def process_p5063_violations(source_picks, decisions, keep_log, seen_groups):
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
        seen_groups.add(("P5063", ili))
        decision = decisions.get(("P5063", ili))
        if decision:
            keep_or_hold, reason = apply_decision(decision, qid_data_list, ("P5063", ili))
            if keep_or_hold == "hold":
                keep_log.append({'prop': 'P5063', 'value': ili, 'keep_qid': '',
                                 'reason': reason, 'remove_qids': '', 'note': decision['note']})
                continue
            best_qid, reason = keep_or_hold, reason
        else:
            best_qid, reason = choose_keep_p5063(qid_data_list, source_picks.get(('P5063', ili)))

        if best_qid is None:
            # Can't determine - needs manual review
            manual_review.extend(qid_data_list)
            continue
        keep_log.append({'prop': 'P5063', 'value': ili, 'keep_qid': best_qid, 'reason': reason,
                         'remove_qids': '|'.join(q['qid'] for q in qid_data_list if q['qid'] != best_qid),
                         'note': decision['note'] if decision else ''})

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


def main(run_dir=None):
    global OUTPUT_DIR, QUICKSTATEMENTS_DIR, MANUAL_REVIEW_DIR
    if run_dir:
        OUTPUT_DIR = Path(run_dir)
        QUICKSTATEMENTS_DIR = OUTPUT_DIR / "quickstatements"
        MANUAL_REVIEW_DIR = OUTPUT_DIR / "manual_review"
    source_picks = load_source_picks()
    if not source_picks:
        print("WARNING: no source_crosscheck.csv - run scripts/crosscheck_sources.py first; "
              "falling back to similarity heuristics only.")
    decisions = load_decisions()
    if decisions:
        print(f"Loaded {len(decisions)} human decisions from manual_review/decisions.csv "
              f"(decisions override the source pick and the heuristics)")
    seen_groups = set()
    keep_log = []
    print("Processing P8814 violations...")
    p8814_stats = process_p8814_violations(source_picks, decisions, keep_log, seen_groups)
    print(f"  ✓ Generated {p8814_stats['auto_fix']} QuickStatements")
    print(f"  ✓ Manual review: {p8814_stats['manual_review']}")

    print("\nProcessing P5063 violations...")
    p5063_stats = process_p5063_violations(source_picks, decisions, keep_log, seen_groups)
    print(f"  ✓ Generated {p5063_stats['auto_fix']} QuickStatements")
    print(f"  ✓ Manual review: {p5063_stats['manual_review']}")

    check_unknown_decisions(decisions, seen_groups)
    write_keep_log(keep_log)
    print("\n" + generate_summary(p8814_stats, p5063_stats))
    print("Keep decisions by reason:", dict(Counter((k['prop'], k['reason']) for k in keep_log)))
    
    # Save summary to file
    summary_file = OUTPUT_DIR / "proposal_summary_v2.txt"
    with open(summary_file, 'w') as f:
        f.write(generate_summary(p8814_stats, p5063_stats))
    print(f"\n✓ Summary saved to: {summary_file}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else None)
