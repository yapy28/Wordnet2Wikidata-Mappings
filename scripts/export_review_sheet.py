#!/usr/bin/env python3
"""
Build the review workbook (XLSX) that collaborators fill in via Google Sheets.

One row per duplicate group (a synset ID on P8814, an ILI on P5063), built from the same
data as the dashboard (keep_decisions.csv, source_crosscheck.csv, *_violations_final.csv).
Collaborators only touch the yellow columns: Decision, Keep QID, Note.
Every header has a hover note. Feed the filled sheet back with import_decisions.py.

Usage:
    python scripts/export_review_sheet.py [data/output/<date>]
Requires: pip install openpyxl
"""
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_dashboard import CATEGORY_LABELS, build_rows, load_csv, load_fixes  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent

REASON = {
    "source": "Source repos name it", "decision": "Human decision", "decision_leave": "Human decision: keep both",
    "defer": "Deferred", "members_note": "Label is in synset members", "similarity_note": "Best similarity score",
    "label_in_members": "Label is in synset members", "label_in_definition": "Label appears in definition",
    "score": "Best label/definition score", "score_tie": "Tie - no clear winner", "fallback": "No evidence (first listed)",
}
ROLE = {"keep": "KEEP", "remove": "REMOVE", "valid": "VALID", "deferred": "DEFERRED", "unresolved": "UNRESOLVED"}

HEADER_NOTES = {
    "Property": "P8814 = the same WordNet synset ID is on several Wikidata items. P5063 = the same ILI (Interlingual Index) is on several items.",
    "Synset / ILI": "The duplicated value. Each group is one synset ID (P8814) or one ILI (P5063).",
    "WordNet definition": "What the WordNet synset means.",
    "WordNet members": "The words in the synset. WordNet groups synonyms, so a Wikidata item whose label is here is a good match.",
    "Category": "Automatic classification of the group, e.g. 'Different concepts' (neither item matches the synset) or 'Both in members' (polysemy).",
    "Wikidata items": "Every item that carries the value. KEEP = proposed to keep it, REMOVE = proposed to lose it, VALID = legitimate duplicate.",
    "Source repos say": "What english-wordnet / english-namenet map this value to. These are the original source of the mappings, the strongest evidence we have.",
    "Why this keep": "Why the proposal keeps this item. 'Tie' and 'No evidence' are weak: a human should look.",
    "Weak?": "YES = the proposal rests on weak signals (no source QID and no clear winner). Check these first.",
    "Decision": "keep = keep the QID in 'Keep QID' and remove the value from the others. leave = valid duplicate, remove nothing. defer = not sure, hold. Empty = no decision, the proposal stands.",
    "Keep QID": "Only for 'keep': the item that keeps the value (must be one of the items in the group). Prefilled with the current proposal.",
    "Note": "Why you decided this. Shown in the dashboard.",
}
GUIDE = [
    ("What this is", "Duplicate WordNet-to-Wikidata mappings (P8814 synset IDs, P5063 ILIs). Each row is one group of Wikidata items that share the same value."),
    ("What to do", "Go to 'Review queue'. For each row pick a Decision (keep / leave / defer), set Keep QID if you chose keep, add a Note. Only the yellow columns are yours."),
    ("Rule of thumb", "WordNet is a lumper, Wikidata is a splitter: synsets deliberately group synonyms, so a duplicate is often a legitimate synonym pair. When in doubt: leave."),
    ("Redirects", "Keep redirects (e.g. Q272388 redirects to Q202526). Never remove the statement a redirect depends on."),
    ("Defunct / new items", "Wikidata has items for defunct names that WordNet picked up. New Wikidata IDs are taken with a grain of salt: prefer established items as the keep."),
    ("Different concepts", "If the items are genuinely different (cholestasis vs acholia), leave both and say so in the Note: we propose a WordNet-side synset split instead of removing anything."),
    ("Tabs", "Review queue = weak proposals, check first. All groups = every group, if you want to overrule any other proposal. Decisions made so far are prefilled."),
]


def lines(rows, group_value):
    out = []
    for r in sorted(rows, key=lambda x: x["q"]):
        label = f'{r["q"]} - {r["lab"]}' + (f' - {r["desc"]}' if r["desc"] else "")
        out.append(f'{label}  [{ROLE[r["role"]]}]')
    return "\n".join(out)


def build_groups(run_dir):
    p8814_raw = load_csv(run_dir / "p8814_violations_final.csv")
    p5063_raw = load_csv(run_dir / "p5063_violations_final.csv")
    seen, p5063 = set(), []
    for v in p5063_raw:  # the SPARQL join repeats each (QID, ILI) pair
        if (v["qid"], v["ili"]) not in seen:
            seen.add((v["qid"], v["ili"]))
            p5063.append(v)

    crosscheck = {(r["prop"], r["value"]): {"source_qids": [q for q in r["source_qids"].split("|") if q]}
                  for r in load_csv(run_dir / "source_crosscheck.csv")}
    kd = load_csv(run_dir / "keep_decisions.csv")
    reasons = {(r["prop"], r["value"]): r["reason"] for r in kd}
    dnotes = {(r["prop"], r["value"]): r.get("note", "") for r in kd}
    fixes8814 = load_fixes(run_dir / "quickstatements" / "p8814_fixes_quickstatements.txt")
    fixes5063 = load_fixes(run_dir / "quickstatements" / "p5063_fixes_quickstatements.txt")

    rows = {
        "P8814": build_rows(p8814_raw, fixes8814, "synset_id", "P8814", crosscheck, reasons, dnotes),
        "P5063": build_rows(p5063, fixes5063, "ili", "P5063", crosscheck, reasons, dnotes),
    }
    keys = {"P8814": [v["synset_id"] for v in p8814_raw], "P5063": [v["ili"] for v in p5063]}

    decisions = {}
    dpath = run_dir / "manual_review" / "decisions.csv"
    if dpath.exists():
        decisions = {(r["prop"], r["value"]): r for r in load_csv(dpath) if r.get("action")}

    groups = []
    for prop in ("P8814", "P5063"):
        by_value = defaultdict(list)
        for key, r in zip(keys[prop], rows[prop]):
            by_value[key].append(r)
        for value, rs in by_value.items():
            if not any(r["role"] in ("keep", "remove", "deferred", "unresolved") for r in rs) \
                    and (prop, value) not in decisions:
                continue  # all-valid groups need no decision
            keep = next((r["q"] for r in rs if r["role"] == "keep"), "") or \
                next((r["keep"] for r in rs if r["role"] == "remove"), "")
            first = rs[0]
            d = decisions.get((prop, value), {})
            groups.append({
                "prop": prop, "value": value, "sdef": first["sdef"], "mem": first["mem"],
                "cat": CATEGORY_LABELS.get(first["cat"], first["cat"]),
                "items": lines(rs, value),
                "source": ", ".join(first["src"]) if first["src"] else "(no QID in source repos)",
                "reason": REASON.get(first["reason"], first["reason"]) + (f' - {first["dnote"]}' if first["dnote"] else ""),
                "weak": "YES" if any(r["rev"] for r in rs) and d.get("action") not in ("keep", "leave") else "",
                "action": d.get("action", ""), "keep_qid": d.get("keep_qid") or keep, "note": d.get("note", ""),
            })
    return groups


COLUMNS = [("Property", "prop", 10), ("Synset / ILI", "value", 16), ("WordNet definition", "sdef", 45),
           ("WordNet members", "mem", 30), ("Category", "cat", 28), ("Wikidata items", "items", 70),
           ("Source repos say", "source", 22), ("Why this keep", "reason", 28), ("Weak?", "weak", 8),
           ("Decision", "action", 12), ("Keep QID", "keep_qid", 12), ("Note", "note", 40)]
INPUT_COLS = {"Decision", "Keep QID", "Note"}


def add_note(cell, text):
    c = Comment(text, "Wordnet2Wikidata")
    c.width, c.height = 320, 140
    cell.comment = c


def write_groups(wb, title, groups):
    ws = wb.create_sheet(title)
    ws.append([c[0] for c in COLUMNS])
    for g in groups:
        ws.append([g[c[1]] for c in COLUMNS])
    grey, yellow = PatternFill("solid", fgColor="DDEBF7"), PatternFill("solid", fgColor="FFF2CC")
    for idx, (name, _, width) in enumerate(COLUMNS, start=1):
        head = ws.cell(row=1, column=idx)
        head.font = Font(bold=True)
        head.fill = yellow if name in INPUT_COLS else grey
        add_note(head, HEADER_NOTES[name])
        ws.column_dimensions[get_column_letter(idx)].width = width
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row=row, column=idx)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if name in INPUT_COLS:
                cell.fill = yellow
    dv = DataValidation(type="list", formula1='"keep,leave,defer"', allow_blank=True, showErrorMessage=True,
                        errorTitle="Decision", error="Pick keep, leave or defer (or clear the cell).")
    ws.add_data_validation(dv)
    dv.add(f"J2:J{max(ws.max_row, 2)}")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def main(run_dir=None):
    if run_dir:
        run_dir = Path(run_dir)
    else:
        runs = sorted(p for p in (BASE_DIR / "data" / "output").glob("*")
                      if p.is_dir() and (p / "keep_decisions.csv").exists())
        if not runs:
            sys.exit("No data/output/*/ run with keep_decisions.csv found. Run the pipeline first.")
        run_dir = runs[-1]

    groups = build_groups(run_dir)
    weak = [g for g in groups if g["weak"]]

    wb = Workbook()
    guide = wb.active
    guide.title = "Read me"
    guide.column_dimensions["A"].width = 22
    guide.column_dimensions["B"].width = 110
    for k, v in GUIDE:
        guide.append([k, v])
    for row in guide.iter_rows():
        row[0].font = Font(bold=True)
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    write_groups(wb, "Review queue", weak)
    write_groups(wb, "All groups", groups)

    summary = wb.create_sheet("Summary")
    summary.column_dimensions["A"].width = 38
    for k, v in [
        ("Groups needing a decision (all)", len(groups)),
        ("  of which weak (review queue)", len(weak)),
        ("  P8814 groups", sum(g["prop"] == "P8814" for g in groups)),
        ("  P5063 groups", sum(g["prop"] == "P5063" for g in groups)),
        ("Already decided", sum(bool(g["action"]) for g in groups)),
        ("Run folder", run_dir.name),
    ]:
        summary.append([k, v])

    out = run_dir / "review_sheet.xlsx"
    wb.save(out)
    print(f"Saved {out}: {len(groups)} groups, {len(weak)} in the review queue")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
