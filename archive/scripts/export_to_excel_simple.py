#!/usr/bin/env python3
"""
Simple script to create Excel-ready CSV files with a Notes sheet.
No external dependencies needed.
"""

import csv
from pathlib import Path

# Configuration
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data/output/20260929"
OUTPUT_DIR = DATA_DIR

# Column explanations
COLUMN_NOTES = """
COLUMN EXPLANATIONS (for all sheets):

1. entity_type - Which Wikidata property this is about (P8814 = synset ID, P5063 = ILI)

2. qid - The Wikidata item identifier (e.g., Q18351973)

3. wd_label - The name or label of the Wikidata item (e.g., "disembarkation")

4. wd_description - The description from Wikidata (e.g., "process of unloading a watercraft...")

5. synset_id - The WordNet synset identifier (e.g., 00058822-n)

6. synset_definition - What the WordNet synset means (e.g., "the act of passengers getting off...")

7. synset_members - Words in this WordNet synset, separated by | (e.g., "debarkation|disembarkation|disembarkment")

8. synset_source - Where the synset comes from: OEWN (Open English WordNet) or OENN (Open English Namenet)

9. ili - Interlingual Index identifier for cross-lingual concepts (e.g., i35710)

10. category - Human-readable category explaining what kind of issue this is:
    - "Both QIDs in synset members" - Both QIDs are valid members of the synset
    - "Different concepts" - The QIDs represent fundamentally different things
    - "One QID in members, definition mismatch" - One QID is in the synset but the definitions don't match
    - "Multiple QIDs, all in synset members" - Multiple QIDs are all valid synset members
    - "Neither QID in members but similar definitions" - Neither QID is in members but definitions are similar

11. category_raw - The technical category code (e.g., ONE_IN_MEMBERS_DESC_MISMATCH)

12. is_violation - Is this a real problem? TRUE = real violation that needs fixing, FALSE = valid duplicate

13. violation_type - Type of violation:
    - DUPLICATE_P8814 = duplicate synset ID mapping
    - DUPLICATE_P5063 = duplicate ILI mapping
    - VALID = not actually a violation

14. has_fix_proposed - Do we have a QuickStatements fix ready? TRUE or FALSE

15. fix_qid - If we're removing a mapping from one QID, this is the QID that should KEEP the mapping

16. fix_applied - Has the fix been applied to Wikidata? TRUE or FALSE (currently all FALSE)

17. confidence_score - How confident we are in the fix (0-10 scale, 10 = most confident)

18. status - Current status of this row:
    - FIX_PROPOSED = We have a fix ready
    - NEEDS_FIX = This needs a fix but we haven't generated one
    - VALID = This is actually fine, not a real violation

---

QUICK REFERENCE:

For P8814 (synset ID violations):
- Same synset ID is mapped to multiple Wikidata QIDs
- We need to decide which QID should keep the synset ID

For P5063 (ILI violations):
- Same ILI is mapped to multiple Wikidata QIDs
- We need to decide which QID should keep the ILI

DECISION GUIDANCE:
- If category = "Both QIDs in synset members" → LEAVE (keep both)
- If category = "Different concepts" → REMOVE one
- If category = "One QID in members, definition mismatch" → Needs review
- If category = "Multiple ILIs, different POS" → LEAVE (different parts of speech)
"""

def create_notes_csv():
    """Create a CSV with column explanations."""
    notes_file = OUTPUT_DIR / "COLUMN_NOTES.csv"
    
    # Split the notes into lines
    lines = COLUMN_NOTES.strip().split('\n')
    
    # Write to CSV (one column)
    with open(notes_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Notes'])  # Header
        for line in lines:
            writer.writerow([line])
    
    return notes_file

def create_data_csv(filename, data, headers):
    """Create a CSV file with data."""
    filepath = OUTPUT_DIR / filename
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    return filepath

def load_csv_file(filepath):
    """Load CSV file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def main():
    print("Creating Excel-ready CSV files...")
    print("=" * 60)
    
    # Load data
    full_comparison = load_csv_file(DATA_DIR / "full_comparison_table.csv")
    
    # Separate by entity type
    p8814_data = [r for r in full_comparison if r.get('entity_type') == 'P8814']
    p5063_data = [r for r in full_comparison if r.get('entity_type') == 'P5063']
    
    # Get headers
    headers = list(full_comparison[0].keys()) if full_comparison else []
    
    # Create CSV files
    files_created = []
    
    # 1. All Violations
    filepath = create_data_csv("01_All_Violations.csv", full_comparison, headers)
    files_created.append(filepath)
    print(f"✓ Created: {filepath.name}")
    
    # 2. P8814 Violations
    if p8814_data:
        filepath = create_data_csv("02_P8814_Violations.csv", p8814_data, headers)
        files_created.append(filepath)
        print(f"✓ Created: {filepath.name}")
    
    # 3. P5063 Violations
    if p5063_data:
        filepath = create_data_csv("03_P5063_Violations.csv", p5063_data, headers)
        files_created.append(filepath)
        print(f"✓ Created: {filepath.name}")
    
    # 4. Decisions
    decisions_file = DATA_DIR / "manual_review" / "decisions.csv"
    if decisions_file.exists():
        decisions_data = load_csv_file(decisions_file)
        decisions_headers = list(decisions_data[0].keys()) if decisions_data else []
        filepath = create_data_csv("04_Decisions.csv", decisions_data, decisions_headers)
        files_created.append(filepath)
        print(f"✓ Created: {filepath.name}")
    
    # 5. Column Notes
    notes_file = create_notes_csv()
    files_created.append(notes_file)
    print(f"✓ Created: {notes_file.name}")
    
    print("\n" + "=" * 60)
    print("✅ All CSV files created in:")
    print(f"   {OUTPUT_DIR}/")
    print("\n📊 Files to import into Google Sheets:")
    for f in files_created:
        print(f"   - {f.name}")
    
    print("\n🎯 How to import into Google Sheets:")
    print("   1. Open your Google Sheet:")
    print("      https://docs.google.com/spreadsheets/d/10SdnHpZoFOwB46yjKAvMDLzP0uh0bOXwKVpy07zQ-ag/edit")
    print("   2. For each CSV file above:")
    print("      - File → Import → Upload → Select the CSV")
    print("      - Create a NEW TAB for each file")
    print("   3. Rename tabs to match the filenames (without .csv)")
    print("   4. Share the sheet with your collaborator")

if __name__ == '__main__':
    main()
