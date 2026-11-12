#!/usr/bin/env python3
"""
Clean OENN and OEWN backlog CSVs by removing entries with empty or invalid ILI values.

Removes rows where wn_ili is:
- Empty string
- "?"
- " ?" or "? " (with whitespace)

Usage:
    python3 scripts/clean_backlogs.py \
        --oenn OENN_backlog.csv \
        --oewn OEWN-Backlog.csv \
        --output-oenn OENN_backlog_cleaned.csv \
        --output-oewn OEWN-Backlog_cleaned.csv
"""

import argparse
import csv
from pathlib import Path


def clean_backlog_csv(input_path: Path, output_path: Path) -> int:
    """Clean a backlog CSV file, removing entries with invalid ILI values.
    Returns the number of rows removed."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    input_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    removed_count = 0
    kept_count = 0
    
    with input_path.open("r", encoding="utf-8", newline="") as infile, \
         output_path.open("w", encoding="utf-8", newline="") as outfile:
        
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in reader:
            ili = row.get("wn_ili", "").strip()
            
            # Skip rows where ILI is empty or just "?"
            if not ili or ili == "?":
                removed_count += 1
                continue
            
            writer.writerow(row)
            kept_count += 1
    
    print(f"  {input_path.name}: {kept_count} kept, {removed_count} removed")
    return removed_count


def main():
    parser = argparse.ArgumentParser(
        description="Clean backlog CSVs by removing entries with invalid ILI values"
    )
    parser.add_argument(
        "--oenn",
        type=Path,
        default=Path("OENN_backlog.csv"),
        help="Path to OENN backlog CSV"
    )
    parser.add_argument(
        "--oewn",
        type=Path,
        default=Path("OEWN-Backlog.csv"),
        help="Path to OEWN backlog CSV"
    )
    parser.add_argument(
        "--output-oenn",
        type=Path,
        default=Path("OENN_backlog_cleaned.csv"),
        help="Output path for cleaned OENN backlog"
    )
    parser.add_argument(
        "--output-oewn",
        type=Path,
        default=Path("OEWN-Backlog_cleaned.csv"),
        help="Output path for cleaned OEWN backlog"
    )
    
    args = parser.parse_args()
    
    print("Cleaning backlog CSVs...")
    oenn_removed = clean_backlog_csv(args.oenn, args.output_oenn)
    oewn_removed = clean_backlog_csv(args.oewn, args.output_oewn)
    
    total_removed = oenn_removed + oewn_removed
    print(f"\nTotal removed: {total_removed} rows")
    print("Done!")


if __name__ == "__main__":
    main()
