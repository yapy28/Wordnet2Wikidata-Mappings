#!/usr/bin/env python3
"""
Export the duplicate groups as toolforge/groups.json, the data the review app serves.

Same groups as the review sheet (build_groups), plus the QIDs of each group so the app can
write QuickStatements removals without parsing text at runtime.

Usage:
    python scripts/export_groups.py [data/output/<date>]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_review_sheet import BASE_DIR, build_groups  # noqa: E402

OUT = BASE_DIR / "toolforge" / "groups.json"


def main(run_dir=None):
    if run_dir:
        run_dir = Path(run_dir)
    else:
        runs = sorted(p for p in (BASE_DIR / "data" / "output").glob("*") if (p / "keep_decisions.csv").exists())
        if not runs:
            sys.exit("No data/output/*/ run with keep_decisions.csv found. Run the pipeline first.")
        run_dir = runs[-1]

    groups = build_groups(run_dir)
    for g in groups:
        g["qids"] = re.findall(r"^(Q\d+)", g["items"], flags=re.M)
    OUT.write_text(json.dumps({"run": run_dir.name, "groups": groups}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {OUT}: {len(groups)} groups ({sum(bool(g['weak']) for g in groups)} weak)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
