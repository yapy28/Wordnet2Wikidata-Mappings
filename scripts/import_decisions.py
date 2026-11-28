#!/usr/bin/env python3
"""
Turn the filled review sheet into manual_review/decisions.csv.

Download the Google Sheet as .xlsx (File -> Download) and pass it in. Decisions are read from the
'Groups' tab (older sheets: 'Review queue' and 'All groups'). Rows with an empty Decision are
ignored; the old words keep / leave / remove / defer are accepted and rewritten to the new ones.
Validates every row against the real duplicate groups.

Usage:
    python scripts/import_decisions.py review_sheet.xlsx [data/output/<date>]
Requires: pip install openpyxl
"""
import csv
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_review_sheet import BASE_DIR, build_groups  # noqa: E402
from generate_proposals_v2 import DECISION_ACTIONS, normalize_action  # noqa: E402

TABS = ("Groups", "Review queue", "All groups")  # the last two: sheets exported before the single tab


def read_decisions(xlsx, known):
    """(prop, value) -> (action, keep_qid, note) from the sheet; exits on any invalid row."""
    decided = {}
    wb = load_workbook(xlsx, read_only=True, data_only=True)
    if not set(TABS) & set(wb.sheetnames):  # never write an empty decisions.csv over the real one
        sys.exit(f"No decision tab in the sheet (expected 'Groups'); found {wb.sheetnames}")
    for title in TABS:
        if title not in wb.sheetnames:
            continue
        rows = wb[title].iter_rows(values_only=True)
        head = [str(h or "").strip() for h in next(rows)]
        idx = {h: head.index(h) for h in ("Property", "Synset / ILI", "Decision", "Keep QID", "Note")}
        for r in rows:
            r = list(r) + [None] * len(head)  # exports trim empty trailing cells
            action = normalize_action(str(r[idx["Decision"]] or ""))
            if not action:
                continue
            prop, value = str(r[idx["Property"]]).strip(), str(r[idx["Synset / ILI"]]).strip()
            keep, note = str(r[idx["Keep QID"]] or "").strip(), str(r[idx["Note"]] or "").strip()
            if action not in DECISION_ACTIONS:
                sys.exit(f"{title}: {prop} {value}: unknown decision '{action}'")
            group = known.get((prop, value))
            if group is None:
                sys.exit(f"{title}: {prop} {value} is not a known duplicate group")
            if action == "keep one" and keep not in group["items"]:
                sys.exit(f"{title}: {prop} {value}: Keep QID '{keep}' is not one of the group's items")
            if action != "keep one":
                keep = ""
            if (prop, value) in decided and decided[(prop, value)] != (action, keep, note):
                sys.exit(f"{prop} {value} appears twice with different decisions; fix the sheet")
            decided[(prop, value)] = (action, keep, note)
    return decided


def main(xlsx, run_dir=None):
    if run_dir:
        run_dir = Path(run_dir)
    else:
        runs = sorted(p for p in (BASE_DIR / "data" / "output").glob("*") if (p / "keep_decisions.csv").exists())
        run_dir = runs[-1]
    decided = read_decisions(xlsx, {(g["prop"], g["value"]): g for g in build_groups(run_dir)})

    out = run_dir / "manual_review" / "decisions.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["prop", "value", "action", "keep_qid", "note"])
        for (prop, value), (action, keep, note) in sorted(decided.items()):
            w.writerow([prop, value, action, keep, note])
    print(f"Wrote {out}: {len(decided)} decisions. Now re-run: python scripts/run_pipeline.py --from proposals")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
