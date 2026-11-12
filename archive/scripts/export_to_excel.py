#!/usr/bin/env python3
"""
Export violation data to one XLSX file (one tab per table).
Every column header carries a hover note explaining it in plain language.
Requires: pip install openpyxl
Upload with: Google Sheets -> File -> Import -> Upload -> Replace spreadsheet.
"""

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data/output/20260929"
EXCEL_FILE = DATA_DIR / "wordnet2wikidata_violations.xlsx"

HEADER_NOTES = {
    "entity_type": "Which Wikidata property this row is about: P8814 (WordNet synset ID) or P5063 (Interlingual Index, ILI).",
    "qid": "The Wikidata item ID (e.g. Q18351973).",
    "wd_label": "The name of the Wikidata item (e.g. 'disembarkation').",
    "wd_description": "The short description of the item on Wikidata.",
    "synset_id": "The WordNet synset identifier (e.g. 00058822-n). A synset is one meaning shared by a group of words.",
    "synset_definition": "What the WordNet synset means, in WordNet's own words.",
    "synset_members": "The words in this synset, separated by | (e.g. debarkation|disembarkation|disembarkment).",
    "synset_source": "Which WordNet the synset comes from: OEWN (Open English WordNet) or OENN (Open English Namenet).",
    "ili": "Interlingual Index ID: a cross-language concept ID that links WordNets in different languages (e.g. i35710).",
    "category": "Plain-language type of problem. 'Both QIDs in synset members' = both are valid, keep both. "
                "'Different concepts' = the QIDs are different things. "
                "'One QID in members, definition mismatch' = one QID fits the synset, the definition doesn't match. "
                "'Neither QID in members but similar definitions' = neither matches by name, but meanings look alike.",
    "category_raw": "Technical code behind 'category' (e.g. ONE_IN_MEMBERS_DESC_MISMATCH). Same information, for filtering.",
    "is_violation": "TRUE = a real problem that needs fixing. FALSE = the duplicate is legitimate.",
    "violation_type": "DUPLICATE_P8814 = same synset ID on several QIDs. DUPLICATE_P5063 = same ILI on several QIDs. VALID = not a real violation.",
    "has_fix_proposed": "TRUE if a QuickStatements fix has already been generated for this row.",
    "fix_qid": "The QID that should KEEP the mapping; the mapping gets removed from the other QID(s).",
    "fix_applied": "TRUE once the fix has been applied on Wikidata.",
    "confidence_score": "How sure we are about the proposed fix, on a 0-10 scale (higher = more sure).",
    "status": "FIX_PROPOSED = fix ready in QuickStatements. NEEDS_FIX = problem found, no fix generated yet. VALID = nothing to fix.",
    # Decisions tab
    "prop": "The Wikidata property the decision is about (P8814 or P5063).",
    "value": "The synset ID or ILI the decision applies to.",
    "action": "What to do: 'leave' = keep everything as is; otherwise the removal rule to apply.",
    "keep_qid": "The QID that keeps the mapping (empty when action is 'leave').",
    "note": "Why this decision was made (e.g. from the WordNet community discussion).",
    # Summary tab
    "Metric": "What is being counted.",
    "Count": "The number of rows matching the metric.",
}


def load_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_sheet(wb, title, rows, headers=None):
    ws = wb.create_sheet(title)
    headers = headers or (list(rows[0].keys()) if rows else ["No data"])
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])

    fill = PatternFill("solid", fgColor="DDEBF7")
    for idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=idx)
        cell.font = Font(bold=True)
        cell.fill = fill
        note = HEADER_NOTES.get(header)
        if note:
            comment = Comment(note, "Wordnet2Wikidata")
            comment.width, comment.height = 320, 140
            cell.comment = comment
        width = max(len(str(header)), *(len(str(c.value or "")) for c in ws[get_column_letter(idx)][1:200]), 8)
        ws.column_dimensions[get_column_letter(idx)].width = min(width + 2, 60)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def main():
    full = load_csv(DATA_DIR / "full_comparison_table.csv")
    p8814 = [r for r in full if r.get("entity_type") == "P8814"]
    p5063 = [r for r in full if r.get("entity_type") == "P5063"]

    wb = Workbook()
    del wb["Sheet"]

    write_sheet(wb, "All Violations", full)
    write_sheet(wb, "P8814 Violations", p8814)
    write_sheet(wb, "P5063 Violations", p5063)

    decisions_file = DATA_DIR / "manual_review" / "decisions.csv"
    if decisions_file.exists():
        write_sheet(wb, "Decisions", load_csv(decisions_file))

    summary = [
        {"Metric": "Total rows", "Count": len(full)},
        {"Metric": "P8814 rows", "Count": len(p8814)},
        {"Metric": "P5063 rows", "Count": len(p5063)},
        {"Metric": "Real violations", "Count": sum(r.get("is_violation") == "TRUE" for r in full)},
        {"Metric": "Fixes proposed", "Count": sum(r.get("has_fix_proposed") == "TRUE" for r in full)},
    ]
    write_sheet(wb, "Summary", summary)

    wb.save(EXCEL_FILE)
    print(f"Saved {EXCEL_FILE}")


if __name__ == "__main__":
    main()
