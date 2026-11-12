#!/usr/bin/env python3
"""
Transform OEWN/OENN backlog CSVs into QuickStatements TSV format.

This script reads backlog CSV files containing validated synset-to-QID mappings
that are missing from Wikidata and converts them into QuickStatements batch
import format with P8814 (synset ID) and P5063 (ILI) statements.

Usage:
    python scripts/backlog_to_quickstatements.py \
        --oenn wikidata/OENN_backlog.csv \
        --oewn wikidata/OEWN-Backlog.csv \
        --output wikidata/output/wikidata_import.tsv

    python scripts/backlog_to_quickstatements.py --validate-only

Author: Generated for Wikidata backlog import pipeline
"""

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Regex patterns
QID_RE = re.compile(r"^Q[1-9][0-9]*$")
SYNSET_RE = re.compile(r"^[0-9]+-[a-z]$|^[0-9]+-[a-z]-[a-z]$|^[0-9]+-[a-z]-[0-9]+$")
ILI_RE = re.compile(r"^i[0-9]+$")

# Wikidata properties
PROP_SYNSET_ID = "P8814"  # WordNet synset ID
PROP_ILI = "P5063"  # Interlingual Index (ILI)


class BacklogEntry:
    """Represents a single backlog entry from CSV."""
    
    def __init__(self, row: Dict[str, str], source: str):
        self.source = source  # 'OENN' or 'OEWN'
        self.synset_id = row.get("wn_synset", "").strip()
        self.definition = row.get("wn_definition", "").strip()
        self.ili = row.get("wn_ili", "").strip()
        self.members = row.get("wn_members", "").strip()
        self.qid = row.get("wn_wd_qid", "").strip()
        
    def is_valid(self) -> Tuple[bool, List[str]]:
        """Validate entry and return (is_valid, error_messages)."""
        errors = []
        
        if not self.qid:
            errors.append("Missing QID")
        elif not QID_RE.match(self.qid):
            errors.append(f"Invalid QID format: {self.qid}")
            
        if not self.synset_id:
            errors.append("Missing synset ID")
        # Note: We don't strictly validate synset format as it can vary
            
        # ILI is optional but preferred
        if self.ili and not ILI_RE.match(self.ili):
            errors.append(f"Invalid ILI format: {self.ili}")
            
        return (len(errors) == 0, errors)
    
    def to_quickstatements(self) -> List[Tuple[str, str, str]]:
        """Generate QuickStatements rows for this entry."""
        statements = []
        
        # Always add P8814 (synset ID) if available
        if self.synset_id:
            statements.append((self.qid, PROP_SYNSET_ID, self.synset_id))
            
        # Add P5063 (ILI) if available
        if self.ili:
            statements.append((self.qid, PROP_ILI, self.ili))
            
        return statements
    
    def __repr__(self) -> str:
        return f"BacklogEntry(qid={self.qid}, synset={self.synset_id}, ili={self.ili}, source={self.source})"


def read_backlog_csv(filepath: Path, source: str) -> List[BacklogEntry]:
    """Read a backlog CSV file and return list of entries."""
    entries = []
    
    if not filepath.exists():
        print(f"Warning: {filepath} not found, skipping.", file=sys.stderr)
        return entries
    
    with filepath.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # start=2 to account for header
            entry = BacklogEntry(row, source)
            entries.append(entry)
    
    print(f"Read {len(entries)} entries from {filepath} ({source})")
    return entries


def validate_entries(entries: List[BacklogEntry]) -> Tuple[List[BacklogEntry], Dict[str, List[str]]]:
    """Validate all entries and return (valid_entries, errors_dict)."""
    valid_entries = []
    errors_dict = defaultdict(list)
    
    for entry in entries:
        is_valid, errors = entry.is_valid()
        if is_valid:
            valid_entries.append(entry)
        else:
            errors_dict[str(entry)].extend(errors)
    
    return valid_entries, dict(errors_dict)


def check_duplicates(entries: List[BacklogEntry]) -> Dict[str, List[BacklogEntry]]:
    """Check for duplicate (qid, synset_id, ili) combinations."""
    seen: Dict[str, List[BacklogEntry]] = defaultdict(list)
    
    for entry in entries:
        key = (entry.qid, entry.synset_id, entry.ili)
        seen[key].append(entry)
    
    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    return duplicates


def load_multi_qid_review(filepath: Path) -> Set[str]:
    """Load set of (synset_id, qid) pairs that are in multi-QID review."""
    review_set = set()
    
    if not filepath.exists():
        print(f"Warning: {filepath} not found, no multi-QID exclusions applied.", file=sys.stderr)
        return review_set
    
    with filepath.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            synset_id = row.get("wn_synset", "").strip()
            qid = row.get("wn_wd_qid", "").strip()
            if synset_id and qid:
                # Handle multi-QID entries (pipe-separated)
                for q in qid.split("|"):
                    q = q.strip()
                    if q:
                        review_set.add((synset_id, q))
    
    print(f"Loaded {len(review_set)} multi-QID review entries for exclusion")
    return review_set


def filter_excluded(entries: List[BacklogEntry], review_set: Set[str]) -> Tuple[List[BacklogEntry], List[BacklogEntry]]:
    """Filter out entries that are in multi-QID review. Returns (included, excluded)."""
    included = []
    excluded = []
    
    for entry in entries:
        key = (entry.synset_id, entry.qid)
        if key in review_set:
            excluded.append(entry)
        else:
            included.append(entry)
    
    return included, excluded


def write_quickstatements(filepath: Path, statements: List[Tuple[str, str, str]], format_type: str = "tsv") -> None:
    """Write QuickStatements file in TSV or CSV format."""
    # Remove duplicates while preserving order
    unique_statements = []
    seen = set()
    for stmt in statements:
        key = (stmt[0], stmt[1], stmt[2])
        if key not in seen:
            seen.add(key)
            unique_statements.append(stmt)
    
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    delimiter = "\t" if format_type == "tsv" else ","
    
    with filepath.open("w", encoding="utf-8", newline="") as f:
        for qid, prop, value in unique_statements:
            # Always quote the value for QuickStatements
            value = f'"{value}"'
            f.write(f"{qid}{delimiter}{prop}{delimiter}{value}\n")
    
    print(f"Wrote {len(unique_statements)} statements to {filepath}")


def print_summary(
    total_read: int,
    valid_count: int,
    excluded_count: int,
    multi_qid_excluded: int,
    statements_count: int,
    errors: Dict[str, List[str]]
) -> None:
    """Print a summary of the transformation."""
    print("\n" + "=" * 60)
    print("TRANSFORMATION SUMMARY")
    print("=" * 60)
    print(f"Total entries read:          {total_read:,}")
    print(f"Valid entries:               {valid_count:,}")
    print(f"Invalid entries:             {total_read - valid_count:,}")
    print(f"Excluded (multi-QID):        {multi_qid_excluded:,}")
    print(f"Final entries for import:    {valid_count - multi_qid_excluded:,}")
    print(f"QuickStatements generated:   {statements_count:,}")
    
    if errors:
        print(f"\nValidation errors ({len(errors)} entries):")
        for entry_repr, errs in list(errors.items())[:10]:  # Show first 10
            print(f"  {entry_repr}")
            for err in errs:
                print(f"    - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Transform OEWN/OENN backlog CSVs to QuickStatements TSV"
    )
    parser.add_argument(
        "--oenn",
        type=Path,
        default=Path("wikidata/OENN_backlog.csv"),
        help="Path to OENN backlog CSV"
    )
    parser.add_argument(
        "--oewn",
        type=Path,
        default=Path("wikidata/OEWN-Backlog.csv"),
        help="Path to OEWN backlog CSV"
    )
    parser.add_argument(
        "--multi-qid-review",
        type=Path,
        default=Path("wikidata/output/multi_qid_review.csv"),
        help="Path to multi-QID review CSV for exclusion"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("wikidata/output/wikidata_import.tsv"),
        help="Output TSV file path"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate inputs, don't generate output"
    )
    parser.add_argument(
        "--include-multi-qid",
        action="store_true",
        help="Include entries that are in multi-QID review (default: exclude)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run transformation but don't write output file"
    )
    parser.add_argument(
        "--format",
        choices=["tsv", "csv"],
        default="csv",
        help="Output format: tsv (tab-separated) or csv (comma-separated), default: csv"
    )
    
    args = parser.parse_args()
    
    # Step 1: Read backlog files
    print("Reading backlog files...")
    oenn_entries = read_backlog_csv(args.oenn, "OENN")
    oewn_entries = read_backlog_csv(args.oewn, "OEWN")
    
    total_read = len(oenn_entries) + len(oewn_entries)
    all_entries = oenn_entries + oewn_entries
    
    if not all_entries:
        print("Error: No entries found in backlog files.", file=sys.stderr)
        sys.exit(1)
    
    # Step 2: Validate entries
    print("\nValidating entries...")
    valid_entries, errors = validate_entries(all_entries)
    invalid_count = total_read - len(valid_entries)
    
    if errors:
        print(f"Found {len(errors)} entries with validation errors.", file=sys.stderr)
    
    # Step 3: Check for duplicates
    print("\nChecking for duplicates...")
    duplicates = check_duplicates(valid_entries)
    if duplicates:
        print(f"Warning: Found {len(duplicates)} duplicate (qid, synset, ili) combinations.", file=sys.stderr)
        # deduplicate by keeping first occurrence
        seen_keys = set()
        deduped_entries = []
        for entry in valid_entries:
            key = (entry.qid, entry.synset_id, entry.ili)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_entries.append(entry)
        valid_entries = deduped_entries
        print(f"Deduplicated to {len(valid_entries)} unique entries.")
    
    # Step 4: Exclude multi-QID review entries (unless --include-multi-qid)
    print("\nChecking multi-QID review exclusions...")
    if not args.include_multi_qid:
        review_set = load_multi_qid_review(args.multi_qid_review)
        included_entries, excluded_multi = filter_excluded(valid_entries, review_set)
        multi_qid_excluded = len(excluded_multi)
    else:
        included_entries = valid_entries
        excluded_multi = []
        multi_qid_excluded = 0
        print("Including multi-QID entries (not excluding any)")
    
    # Step 5: Generate QuickStatements
    print("\nGenerating QuickStatements...")
    all_statements = []
    for entry in included_entries:
        statements = entry.to_quickstatements()
        all_statements.extend(statements)
    
    statements_count = len(all_statements)
    
    # Step 6: Print summary
    print_summary(
        total_read=total_read,
        valid_count=len(valid_entries),
        excluded_count=invalid_count + len(excluded_multi),
        multi_qid_excluded=multi_qid_excluded,
        statements_count=statements_count,
        errors=errors
    )
    
    # Step 7: Write output (unless validate-only or dry-run)
    if args.validate_only:
        print("\nValidation complete. No output written (--validate-only).")
        sys.exit(0)
    
    if args.dry_run:
        print("\nDry run complete. Would write output but --dry-run specified.")
        sys.exit(0)
    
    # Write the output file
    print(f"\nWriting QuickStatements {args.format.upper()} to {args.output}...")
    write_quickstatements(args.output, all_statements, args.format)
    
    # Print sample
    print("\nSample of first 10 statements:")
    for i, (qid, prop, value) in enumerate(all_statements[:10]):
        print(f"  {qid}\t{prop}\t{value}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
