#!/usr/bin/env python3
"""
Verification script for QuickStatements import.

This script compares old vs new comparison tables to verify that imported
statements (P8814 and P5063) now appear in Wikidata and are reflected in
the comparison table as flag_qid_join_found = "1".

Usage:
    python scripts/verify_import.py \
        --old output/comparison_table.csv.backup \
        --new output/comparison_table.csv

    python scripts/verify_import.py \
        --old output/comparison_table.csv.backup \
        --new output/comparison_table.csv \
        --import-file output/wikidata_import.tsv

Author: Generated for Wikidata backlog import pipeline
"""

import argparse
import csv
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


@dataclass
class ComparisonRow:
    """Represents a row from the comparison table."""
    synset_id: str
    definition: str
    ili: str
    members: str
    wikidata_qid_original: str
    qid_candidate: str
    qid_count_original: str
    multi_qid_original: str
    review_status_original: str
    in_oewn: str
    in_oenn: str
    entity_uri: str
    qid: str
    entity_label: str
    entity_description: str
    wd_ili: str
    wd_ssid: str
    flag_qid_join_found: str
    flag_match_ssid_exact: str
    flag_match_ili_exact: str
    flag_label_in_members_exact: str
    flag_label_in_members_norm: str
    flag_def_desc_overlap_any: str
    def_desc_overlap_count: str
    
    # Key for matching across old/new tables
    def match_key(self) -> str:
        """Return a key that uniquely identifies this synset-QID pair."""
        return f"{self.synset_id}|{self.qid_candidate}"
    
    def is_join_found(self) -> bool:
        """Check if QID join was found."""
        return self.flag_qid_join_found == "1"
    
    def source(self) -> str:
        """Determine source from flags."""
        if self.in_oewn == "TRUE":
            return "OEWN"
        elif self.in_oenn == "TRUE":
            return "OENN"
        return "Unknown"


@dataclass
class ImportStatement:
    """Represents a statement from the QuickStatements import file."""
    qid: str
    property: str
    value: str


@dataclass
class VerificationResult:
    """Results of verification."""
    total_rows_old: int = 0
    total_rows_new: int = 0
    total_join_found_old: int = 0
    total_join_found_new: int = 0
    
    # Track changes per synset-QID pair
    successfully_inserted: List[str] = field(default_factory=list)
    still_missing: List[str] = field(default_factory=list)
    newly_missing: List[str] = field(default_factory=list)  # Were found, now missing
    new_mismatches: List[str] = field(default_factory=list)
    
    # For detailed reporting
    inserted_details: Dict[str, Dict] = field(default_factory=dict)
    missing_details: Dict[str, Dict] = field(default_factory=dict)


def read_comparison_csv(filepath: Path) -> List[ComparisonRow]:
    """Read comparison table CSV."""
    rows = []
    
    if not filepath.exists():
        raise FileNotFoundError(f"Comparison table not found: {filepath}")
    
    with filepath.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                comp_row = ComparisonRow(
                    synset_id=row.get("synset_id", "").strip(),
                    definition=row.get("definition", "").strip(),
                    ili=row.get("ili", "").strip(),
                    members=row.get("members", "").strip(),
                    wikidata_qid_original=row.get("wikidata_qid_original", "").strip(),
                    qid_candidate=row.get("qid_candidate", "").strip(),
                    qid_count_original=row.get("qid_count_original", "").strip(),
                    multi_qid_original=row.get("multi_qid_original", "").strip(),
                    review_status_original=row.get("review_status_original", "").strip(),
                    in_oewn=row.get("in_oewn", "").strip(),
                    in_oenn=row.get("in_oenn", "").strip(),
                    entity_uri=row.get("entity_uri", "").strip(),
                    qid=row.get("qid", "").strip(),
                    entity_label=row.get("entity_label", "").strip(),
                    entity_description=row.get("entity_description", "").strip(),
                    wd_ili=row.get("wd_ili", "").strip(),
                    wd_ssid=row.get("wd_ssid", "").strip(),
                    flag_qid_join_found=row.get("flag_qid_join_found", "0").strip(),
                    flag_match_ssid_exact=row.get("flag_match_ssid_exact", "0").strip(),
                    flag_match_ili_exact=row.get("flag_match_ili_exact", "0").strip(),
                    flag_label_in_members_exact=row.get("flag_label_in_members_exact", "0").strip(),
                    flag_label_in_members_norm=row.get("flag_label_in_members_norm", "0").strip(),
                    flag_def_desc_overlap_any=row.get("flag_def_desc_overlap_any", "0").strip(),
                    def_desc_overlap_count=row.get("def_desc_overlap_count", "0").strip(),
                )
                rows.append(comp_row)
            except Exception as e:
                print(f"Warning: Error parsing row: {e}", file=sys.stderr)
                continue
    
    print(f"Read {len(rows)} rows from {filepath}")
    return rows


def read_import_tsv(filepath: Path) -> List[ImportStatement]:
    """Read QuickStatements import TSV file."""
    statements = []
    
    if not filepath.exists():
        print(f"Warning: Import file not found: {filepath}", file=sys.stderr)
        return statements
    
    with filepath.open("r", encoding="utf-8", newline="") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            parts = line.split("\t")
            if len(parts) >= 3:
                qid = parts[0].strip()
                prop = parts[1].strip()
                value = parts[2].strip()
                # Remove quotes if present
                value = value.strip('"')
                statements.append(ImportStatement(qid=qid, property=prop, value=value))
            else:
                print(f"Warning: Invalid line format at line {line_num}: {line}", file=sys.stderr)
    
    print(f"Read {len(statements)} statements from {filepath}")
    return statements


def build_lookup(rows: List[ComparisonRow]) -> Dict[str, ComparisonRow]:
    """Build a lookup dictionary by match_key."""
    lookup = {}
    for row in rows:
        key = row.match_key()
        if key in lookup:
            # Handle duplicates - keep the one with join found
            existing = lookup[key]
            if existing.is_join_found() and not row.is_join_found():
                continue  # keep existing
            elif not existing.is_join_found() and row.is_join_found():
                lookup[key] = row  # replace with found version
        else:
            lookup[key] = row
    return lookup


def verify_import(
    old_rows: List[ComparisonRow],
    new_rows: List[ComparisonRow],
    import_statements: List[ImportStatement]
) -> VerificationResult:
    """Verify the import by comparing old vs new comparison tables."""
    result = VerificationResult()
    
    # Build lookups
    old_lookup = build_lookup(old_rows)
    new_lookup = build_lookup(new_rows)
    
    result.total_rows_old = len(old_rows)
    result.total_rows_new = len(new_rows)
    result.total_join_found_old = sum(1 for r in old_rows if r.is_join_found())
    result.total_join_found_new = sum(1 for r in new_rows if r.is_join_found())
    
    # Get all keys from both old and new
    all_keys = set(old_lookup.keys()) | set(new_lookup.keys())
    
    # Build a set of (qid, value) pairs from import statements
    # We expect P8814 to have synset_id and P5063 to have ili
    imported_pairs = set()
    imported_ilis = set()
    for stmt in import_statements:
        if stmt.property == "P8814":
            imported_pairs.add((stmt.qid, stmt.value))  # (qid, synset_id)
        elif stmt.property == "P5063":
            imported_ilis.add((stmt.qid, stmt.value))  # (qid, ili)
    
    # For each key (synset_id|qid_candidate), check old vs new
    for key in all_keys:
        synset_id, qid_candidate = key.split("|", 1)
        
        old_row = old_lookup.get(key)
        new_row = new_lookup.get(key)
        
        old_found = old_row.is_join_found() if old_row else False
        new_found = new_row.is_join_found() if new_row else False
        
        # Check if this was in the import
        was_imported_synset = (qid_candidate, synset_id) in imported_pairs
        was_imported_ili = False
        # Find ILI for this synset from old row
        old_ili = old_row.ili if old_row else ""
        if old_ili and (qid_candidate, old_ili) in imported_ilis:
            was_imported_ili = True
        
        was_imported = was_imported_synset or was_imported_ili
        
        # Case 1: Was not found before, now found -> success
        if not old_found and new_found:
            result.successfully_inserted.append(key)
            if new_row:
                result.inserted_details[key] = {
                    "synset_id": new_row.synset_id,
                    "qid": new_row.qid_candidate,
                    "ili": new_row.ili,
                    "source": new_row.source(),
                    "was_imported": was_imported
                }
        
        # Case 2: Still not found -> still missing
        elif not old_found and not new_found:
            result.still_missing.append(key)
            if old_row:
                result.missing_details[key] = {
                    "synset_id": old_row.synset_id,
                    "qid": old_row.qid_candidate,
                    "ili": old_row.ili,
                    "source": old_row.source(),
                    "was_imported": was_imported
                }
        
        # Case 3: Was found, now not found -> regression
        elif old_found and not new_found:
            result.newly_missing.append(key)
        
    # Check for new mismatches (rows that changed from match to non-match)
    # This would be in the old table but not in new table with same key
    for key in all_keys:
        old_row = old_lookup.get(key)
        new_row = new_lookup.get(key)
        
        if old_row and not new_row:
            # Row disappeared
            result.new_mismatches.append(f"{key} (disappeared)")
        elif old_row and new_row:
            # Check if structural matches changed
            old_ssid = old_row.flag_match_ssid_exact
            new_ssid = new_row.flag_match_ssid_exact
            old_ili = old_row.flag_match_ili_exact
            new_ili = new_row.flag_match_ili_exact
            
            if old_ssid != new_ssid or old_ili != new_ili:
                result.new_mismatches.append(key)
    
    return result


def print_verification_report(result: VerificationResult, import_statements: List[ImportStatement]) -> None:
    """Print a detailed verification report."""
    print("\n" + "=" * 70)
    print("QUICKSTATEMENTS IMPORT VERIFICATION REPORT")
    print("=" * 70)
    
    # Basic stats
    print("\n## Basic Statistics")
    print("-" * 70)
    print(f"Old comparison table rows:    {result.total_rows_old:,}")
    print(f"New comparison table rows:    {result.total_rows_new:,}")
    print(f"Difference:                  {result.total_rows_new - result.total_rows_old:+,}")
    print()
    print(f"QID joins found (old):       {result.total_join_found_old:,} ({100*result.total_join_found_old/max(1,result.total_rows_old):.1f}%)")
    print(f"QID joins found (new):       {result.total_join_found_new:,} ({100*result.total_join_found_new/max(1,result.total_rows_new):.1f}%)")
    print(f"Improvement:                 {result.total_join_found_new - result.total_join_found_old:+,}")
    
    # Import stats
    print(f"\nImport file statements:      {len(import_statements):,}")
    
    # Results
    print("\n## Import Results")
    print("-" * 70)
    print(f"Successfully inserted (was 0, now 1):  {len(result.successfully_inserted):,}")
    print(f"Still missing (remains 0):            {len(result.still_missing):,}")
    print(f"Newly missing (regression):           {len(result.newly_missing):,}")
    print(f"New mismatches:                      {len(result.new_mismatches):,}")
    
    if result.total_join_found_old > 0:
        insertion_rate = 100 * len(result.successfully_inserted) / (
            len(result.successfully_inserted) + len(result.still_missing)
        ) if (len(result.successfully_inserted) + len(result.still_missing)) > 0 else 0
        print(f"Insertion rate:                      {insertion_rate:.1f}%")
    
    # Sample of successfully inserted
    if result.successfully_inserted:
        print("\n## Successfully Inserted (sample of first 20)")
        print("-" * 70)
        for i, key in enumerate(result.successfully_inserted[:20]):
            details = result.inserted_details.get(key, {})
            synset = details.get("synset_id", "")
            qid = details.get("qid", "")
            ili = details.get("ili", "")
            source = details.get("source", "")
            was_imported = details.get("was_imported", False)
            marker = " [IMPORTED]" if was_imported else ""
            print(f"  {i+1:2d}. {synset} -> {qid} (ILI: {ili}, {source}){marker}")
        if len(result.successfully_inserted) > 20:
            print(f"  ... and {len(result.successfully_inserted) - 20} more")
    
    # Still missing
    if result.still_missing:
        print("\n## Still Missing (sample of first 20)")
        print("-" * 70)
        for i, key in enumerate(result.still_missing[:20]):
            details = result.missing_details.get(key, {})
            synset = details.get("synset_id", "")
            qid = details.get("qid", "")
            ili = details.get("ili", "")
            source = details.get("source", "")
            was_imported = details.get("was_imported", False)
            marker = " [WAS IMPORTED]" if was_imported else ""
            print(f"  {i+1:2d}. {synset} -> {qid} (ILI: {ili}, {source}){marker}")
        if len(result.still_missing) > 20:
            print(f"  ... and {len(result.still_missing) - 20} more")
    
    # Newly missing (regressions)
    if result.newly_missing:
        print("\n## Newly Missing (REGRESSIONS - needs investigation)")
        print("-" * 70)
        for i, key in enumerate(result.newly_missing[:20]):
            print(f"  {i+1:2d}. {key}")
        if len(result.newly_missing) > 20:
            print(f"  ... and {len(result.newly_missing) - 20} more")
    
    # New mismatches
    if result.new_mismatches:
        print("\n## New Mismatches (structural changes)")
        print("-" * 70)
        for i, key in enumerate(result.new_mismatches[:20]):
            print(f"  {i+1:2d}. {key}")
        if len(result.new_mismatches) > 20:
            print(f"  ... and {len(result.new_mismatches) - 20} more")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if len(result.newly_missing) == 0 and len(result.new_mismatches) == 0:
        status = "SUCCESS"
        if len(result.still_missing) == 0:
            status = "COMPLETE SUCCESS"
    else:
        status = "PARTIAL SUCCESS (has regressions)"
    
    print(f"Status: {status}")
    print(f"Imported statements: {len(import_statements):,}")
    print(f"Inserted: {len(result.successfully_inserted):,}")
    print(f"Still missing: {len(result.still_missing):,}")
    print(f"Regressions: {len(result.newly_missing):,}")
    print(f"Mismatches: {len(result.new_mismatches):,}")
    
    # Advice
    print("\n## Recommendations")
    print("-" * 70)
    
    if result.still_missing:
        imported_but_still_missing = sum(
            1 for d in result.missing_details.values() if d.get("was_imported")
        )
        if imported_but_still_missing > 0:
            print(f"  - {imported_but_still_missing} entries were imported but still show as missing.")
            print(f"    This may be due to Wikidata propagation delay (24-48 hours).")
            print(f"    Re-run verification after waiting.")
    
    if result.newly_missing:
        print(f"  - {len(result.newly_missing)} regressions detected.")
        print(f"    Investigate if these QIDs were merged or deleted in Wikidata.")
    
    if result.new_mismatches:
        print(f"  - {len(result.new_mismatches)} new mismatches detected.")
        print(f"    Review structural match flags for these entries.")
    
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Verify QuickStatements import by comparing old vs new comparison tables"
    )
    parser.add_argument(
        "--old",
        type=Path,
        required=True,
        help="Path to old (pre-import) comparison table CSV"
    )
    parser.add_argument(
        "--new",
        type=Path,
        required=True,
        help="Path to new (post-import) comparison table CSV"
    )
    parser.add_argument(
        "--import-file",
        type=Path,
        default=None,
        help="Path to QuickStatements import TSV (for tracking which entries were imported)"
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only print summary statistics, not detailed lists"
    )
    
    args = parser.parse_args()
    
    # Read comparison tables
    print("Reading comparison tables...")
    old_rows = read_comparison_csv(args.old)
    new_rows = read_comparison_csv(args.new)
    
    # Read import file if provided
    import_statements = []
    if args.import_file:
        import_statements = read_import_tsv(args.import_file)
    
    # Verify import
    print("\nVerifying import...")
    result = verify_import(old_rows, new_rows, import_statements)
    
    # Print report
    if args.summary_only:
        print("\n## Summary Statistics")
        print(f"Old joins: {result.total_join_found_old:,}")
        print(f"New joins: {result.total_join_found_new:,}")
        print(f"Improvement: {result.total_join_found_new - result.total_join_found_old:+,}")
        print(f"Inserted: {len(result.successfully_inserted):,}")
        print(f"Still missing: {len(result.still_missing):,}")
        print(f"Regressions: {len(result.newly_missing):,}")
        print(f"Mismatches: {len(result.new_mismatches):,}")
    else:
        print_verification_report(result, import_statements)
    
    # Exit with error code if there are problems
    if result.newly_missing or result.new_mismatches:
        print("\nWarning: Regressions or mismatches detected. Exit code 1.", file=sys.stderr)
        sys.exit(1)
    elif result.still_missing:
        print("\nNote: Some entries still missing. Exit code 0 (partial success).", file=sys.stderr)
        sys.exit(0)
    else:
        print("\nAll checks passed. Exit code 0.", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
