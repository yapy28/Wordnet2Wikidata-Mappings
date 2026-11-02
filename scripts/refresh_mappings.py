#!/usr/bin/env python3
"""
One-command refresh of the dashboard's "All mappings" tab.

Re-runs the import-pipeline comparison against the current OEWN/OENN repos and
live Wikidata, then regenerates the dashboard so it embeds the fresh table:

  1. Materialise the source repos (git archive of a local ref, default HEAD)
     into scripts/data_sources/ (gitignored) — extract_yaml.py reads them there.
  2. extract_yaml.py            -> scripts/output/merged_mapped.csv
  3. fetch_wikidata.py          -> scripts/output/wikidata_wordnet_links.csv (live SPARQL)
  4. build_comparison_table.py  -> scripts/output/comparison_table.csv
  5. Copy it to data/output/<YYYYMMDD>/comparison_table.csv (today's run dir)
  6. generate_dashboard.py      -> picks the newest comparison table automatically

The violation tabs are untouched: generate_dashboard.py still reads the latest
data/output/<date>/ that contains p8814_violations_final.csv.

Usage:
    python scripts/refresh_mappings.py [--wordnet-repo DIR] [--namenet-repo DIR]
                                       [--wordnet-ref REF] [--namenet-ref REF]
                                       [--run-dir DIR] [--skip-fetch]

    --skip-fetch reuses the existing scripts/output/wikidata_wordnet_links.csv.
"""
import argparse
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parent
SOURCES = BASE / "data_sources"
OUT = BASE / "output"
DATA_OUT = REPO / "data" / "output"


def materialise(repo: Path, ref: str, dest: Path) -> None:
    """Export `ref` of the local repo into dest/ via git archive (no checkout needed)."""
    archive = subprocess.run(["git", "-C", str(repo), "archive", ref],
                             check=True, capture_output=True).stdout
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=BytesIO(archive), mode="r:") as tar:
        tar.extractall(dest, filter="data")
    print(f"materialised {repo.name} @ {ref} -> {dest}")


def run(script: str) -> None:
    print(f"-- {script}")
    subprocess.run([sys.executable, str(BASE / script)], check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wordnet-repo", type=Path, default=Path.home() / "GIT" / "english-wordnet")
    ap.add_argument("--namenet-repo", type=Path, default=Path.home() / "GIT" / "english-namenet")
    ap.add_argument("--wordnet-ref", default="HEAD", help="local ref to compare from (default: HEAD)")
    ap.add_argument("--namenet-ref", default="HEAD", help="local ref to compare from (default: HEAD)")
    ap.add_argument("--run-dir", type=Path, default=None,
                    help="destination run dir (default: data/output/<today>)")
    ap.add_argument("--skip-fetch", action="store_true",
                    help="reuse scripts/output/wikidata_wordnet_links.csv")
    args = ap.parse_args()

    materialise(args.wordnet_repo, args.wordnet_ref, SOURCES / "english-wordnet")
    materialise(args.namenet_repo, args.namenet_ref, SOURCES / "english-namenet")

    run("extract_yaml.py")
    if not args.skip_fetch:
        run("fetch_wikidata.py")
    run("build_comparison_table.py")

    run_dir = args.run_dir or DATA_OUT / datetime.now().strftime("%Y%m%d")
    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / "comparison_table.csv"
    shutil.copy2(OUT / "comparison_table.csv", dest)
    print(f"copied comparison table -> {dest}")

    run("generate_dashboard.py")
    print("done — the dashboard now embeds the fresh All mappings table.")


if __name__ == "__main__":
    main()
