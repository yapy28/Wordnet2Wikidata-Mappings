#!/usr/bin/env python3
"""
Run the whole violation analysis, step by step or in one go.

Stages (in order):
  fetch      pull the live P8814 / P5063 violations from Wikidata SPARQL   (network; off by default)
  classify   real error vs valid duplicate                                  categorize_all_final.py
  crosscheck what english-wordnet / english-namenet say per group          crosscheck_sources.py (needs the local repos; off by default)
  proposals  keep / remove per group; human decisions win                   generate_proposals_v2.py
  dashboard  index.html (repo root, always the latest run)                  generate_dashboard.py
  sheet      data/output/<run>/review_sheet.xlsx for Google Sheets          export_review_sheet.py
  test       consistency tests

Usage:
    python scripts/run_pipeline.py                      # classify -> proposals -> dashboard -> sheet -> test
    python scripts/run_pipeline.py --from proposals     # after new decisions.csv (what CI does)
    python scripts/run_pipeline.py --with fetch crosscheck   # full refresh
    python scripts/run_pipeline.py --only dashboard
    python scripts/run_pipeline.py --run-dir data/output/20261101
Requires: pip install openpyxl (sheet stage), requests pyyaml (fetch stage)
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

# name -> (command builder, runs by default)
STAGES = {
    "fetch": (lambda d: [PY, "scripts/fetch_violations.py", d], False),
    "classify": (lambda d: [PY, "scripts/categorize_all_final.py", d], True),
    "crosscheck": (lambda d: [PY, "scripts/crosscheck_sources.py", "--run-dir", d], False),
    "proposals": (lambda d: [PY, "scripts/generate_proposals_v2.py", d], True),
    "dashboard": (lambda d: [PY, "scripts/generate_dashboard.py", d], True),
    "sheet": (lambda d: [PY, "scripts/export_review_sheet.py", d], True),
    "test": (lambda d: [PY, "-m", "unittest", "discover", "-s", "tests", "-t", "."], True),
}


def latest_run_dir():
    runs = sorted(p for p in (ROOT / "data" / "output").glob("*") if (p / "p8814_violations_from_wd.csv").exists())
    if not runs:
        sys.exit("No data/output/*/ with p8814_violations_from_wd.csv. Run with --with fetch --run-dir <dir> first.")
    return runs[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", type=Path, help="default: latest data/output/*/ that holds fetched violations")
    ap.add_argument("--from", dest="start", choices=list(STAGES), help="run this stage and everything after it")
    ap.add_argument("--only", nargs="+", choices=list(STAGES), help="run just these stages")
    ap.add_argument("--with", dest="extra", nargs="+", choices=list(STAGES), default=[],
                    help="also run these normally-off stages (fetch, crosscheck)")
    args = ap.parse_args()

    run_dir = (args.run_dir or latest_run_dir()).resolve()
    names = list(STAGES)
    if args.only:
        chosen = [n for n in names if n in args.only]
    elif args.start:
        chosen = names[names.index(args.start):]
        chosen = [n for n in chosen if STAGES[n][1] or n in args.extra or n == args.start]
    else:
        chosen = [n for n in names if STAGES[n][1] or n in args.extra]

    print(f"Run folder: {run_dir}\nStages: {' -> '.join(chosen)}\n")
    for name in chosen:
        cmd = STAGES[name][0](str(run_dir))
        print(f"=== {name}: {' '.join(Path(c).name if i == 1 and c.endswith('.py') else c for i, c in enumerate(cmd[1:], 1))}")
        t = time.time()
        if subprocess.run(cmd, cwd=ROOT).returncode:
            sys.exit(f"\nStage '{name}' failed. Nothing after it was run.")
        print(f"--- {name} ok ({time.time() - t:.1f}s)\n")
    print("Done.")


if __name__ == "__main__":
    main()
