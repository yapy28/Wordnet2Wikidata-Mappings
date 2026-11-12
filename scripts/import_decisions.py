#!/usr/bin/env python3
"""
Turn the filled review sheet into manual_review/decisions.csv.

Download the Google Sheet as .xlsx (File -> Download) and pass it in. Rows with an empty
Decision are ignored. Validates every row against the real duplicate groups.

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

VALID_ACTIONS = {"keep", "leave", "defer"}


def main(xlsx, run_dir=None):
    if run_dir:
        run_dir = Path(run_dir)
    else:
        runs = sorted(p for p in (BASE_DIR / "data" / "output").glob("*") if (p / "keep_decisions.csv").exists())
        run_dir = runs[-1]
    known = {(g["prop"], g["value"]): g for g in build_groups(run_dir)}

    decided = {}
    wb = load_workbook(xlsx, read_only=True, data_only=True)
    for title in ("Review queue", "All groups"):
        if title not in wb.sheetnames:
            continue
        rows = wb[title].iter_rows(values_only=True)
        head = [str(h or "").strip() for h in next(rows)]
        idx = {h: head.index(h) for h in ("Property", "Synset / ILI", "Decision", "Keep QID", "Note")}
        for r in rows:
            action = str(r[idx["Decision"]] or "").strip().lower()
            if not action:
                continue
            prop, value = str(r[idx["Property"]]).strip(), str(r[idx["Synset / ILI"]]).strip()
            keep, note = str(r[idx["Keep QID"]] or "").strip(), str(r[idx["Note"]] or "").strip()
            if action not in VALID_ACTIONS:
                sys.exit(f"{title}: {prop} {value}: unknown decision '{action}'")
            group = known.get((prop, value))
            if group is None:
                sys.exit(f"{title}: {prop} {value} is not a known duplicate group")
            if action == "keep" and keep not in group["items"]:
                sys.exit(f"{title}: {prop} {value}: Keep QID '{keep}' is not one of the group's items")
            if action != "keep":
                keep = ""
            if (prop, value) in decided and decided[(prop, value)] != (action, keep, note):
                sys.exit(f"{prop} {value} is decided differently in two tabs; fix the sheet")
            decided[(prop, value)] = (action, keep, note)

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
