# WordNet to Wikidata Mappings

A pipeline for validating and importing synset-to-Wikidata mappings from Open English WordNet (OEWN) and Open English Namenet (OENN).

**[Open the interactive dashboard](https://yapy28.github.io/Wordnet2Wikidata-Mappings/data/output/20260929/violations_dashboard.html)** — the full mappings table (26,695 pairs), the P8814/P5063 constraint-violation analysis, review queue, and proposed fixes in one self-contained page. Served via GitHub Pages; the identical file also works offline from `data/output/20260929/violations_dashboard.html`.

## Repository Structure

```
Wordnet2Wikidata-Mappings/
├── LICENSE                                    # MIT License for the project
├── tests/                                     # Consistency and unit tests (python3 -m unittest discover -s tests -t .)
├── docs/
│   ├── WORKFLOW.md                            # Lineage, done vs to-do, proposed decisions.csv, plan for adding new mappings
│   ├── backlog_import.md                      # Detailed workflow and methodology for importing validated mappings via QuickStatements
│   ├── comparison_pipeline.md                 # Pipeline design documentation with mermaid diagrams and use cases
│   ├── constraint_violation_analysis.md        # Methodology and findings for P5063/P8814 constraint violation analysis
│   └── SYSTEM_ARCHITECTURE.md                 # Complete system architecture documentation
├── scripts/
│   ├── backlog_to_quickstatements.py         # Transforms cleaned backlog CSVs into QuickStatements TSV format for Wikidata import
│   ├── build_comparison_table.py             # Builds verification comparison table from merged_mapped.csv and wikidata_wordnet_links.csv
│   ├── build_full_comparison.py              # Builds comprehensive comparison table from violations + QuickStatements with fix tracking
│   ├── categorize_all_final.py               # Final categorization with 100% coverage (0% REVIEW) for all violations
│   ├── categorize_violations.py              # Initial categorization of P5063/P8814 violations as real errors vs valid duplicates
│   ├── categorize_violations_enhanced.py     # Enhanced categorization with similarity matching and confidence scores
│   ├── check_qids.py                         # Validates that QIDs in the import file still exist on Wikidata
│   ├── clean_backlogs.py                     # Removes entries with empty, missing, or invalid ILI values from backlog CSVs
│   ├── crosscheck_sources.py                 # Cross-checks every duplicate group against what english-wordnet / english-namenet say (read from a git ref, nothing checked out)
│   ├── enhance_multiqid_review.py            # Adds hypernym chain column and semantic scores to multi_qid_review.csv
│   ├── extract_yaml.py                       # Extracts synset entries with Wikidata mappings from OEWN/OENN YAML sources
│   ├── fetch_violations.py                   # Queries Wikidata SPARQL for P5063/P8814 constraint violations, joins with OEWN/OENN data
│   ├── fetch_wikidata.py                     # Queries Wikidata SPARQL endpoint to fetch all entities linked via P5063 (ILI) or P8814 (synset ID)
│   ├── generate_dashboard.py                 # Generates the single HTML dashboard (all-mappings table, violation tables, review queue, fixes, dark mode)
│   ├── generate_proposals_v2.py              # Generates QuickStatements fixes for constraint violations (v2 with improved logic)
│   ├── refresh_mappings.py                   # One-command refresh of the dashboard's All mappings tab (repos -> comparison -> dashboard)
│   ├── submit_to_quickstatements.sh          # Shell script to submit QuickStatements batch via API for automated Wikidata import
│   └── verify_import.py                      # Compares old vs new comparison tables to verify successful import of statements
└── data/
    ├── backlogs/                              # Files generated after manual work in Google Sheets
    │   
    └── output/
        ├── 20260929/                          # Date-stamped output for constraint violation analysis
        │   ├── p5063_violations_from_wd.csv         # P5063 violations with synset data from SPARQL
        │   ├── p5063_violations_categorized.csv     # P5063 with category/is_real_violation columns
        │   ├── p5063_violations_enhanced.csv        # P5063 with similarity matching and confidence scores
        │   ├── p5063_violations_final.csv           # P5063 final categorization (0% REVIEW)
        │   ├── p8814_violations_from_wd.csv         # P8814 violations with synset data from SPARQL
        │   ├── p8814_violations_categorized.csv     # P8814 with category/is_real_violation columns
        │   ├── p8814_violations_enhanced.csv        # P8814 with similarity matching and confidence scores
        │   ├── p8814_violations_final.csv           # P8814 final categorization (0% REVIEW)
        │   ├── missing_ilis.csv                     # Synsets with QIDs but no ILI values
        │   ├── missing_ilis_verified.csv           # Missing ILIs with verification columns
        │   ├── violations_dashboard.html           # The dashboard: overview, all-mappings table, P8814/P5063 tables, review queue, fixes, missing ILIs
        │   ├── full_comparison_table.csv           # Comparison table tracking all violations + proposed fixes (2,354 rows)
        │   ├── proposal_summary_v2.txt             # Summary of all proposed fixes
        │   └── quickstatements/                    # QuickStatements for applying fixes
        │       ├── p5063_fixes_quickstatements.txt
        │       └── p8814_fixes_quickstatements.txt
        └── comparison_table.csv               # Main comparison table with 22,670 candidate pairs and match signals
```

## Overview

This project provides a complete pipeline for:

1. **Extracting** synset entries with Wikidata mappings from OEWN and OENN YAML sources
2. **Comparing** these mappings against current Wikidata links to identify missing connections
3. **Validating** mappings using deterministic match signals (synset ID, ILI, label, definition)
4. **Generating** QuickStatements batch files for importing missing links into Wikidata
5. **Verifying** successful import by regenerate comparison tables
6. **Analyzing constraint violations** for P5063 (ILI) and P8814 (synset ID) to identify and resolve duplicate mappings

## Key Statistics on 01.07.2026

- **Total candidate pairs**: 22,670
- **QID join found (in Wikidata)**: 16,085 (70.95%)
- **QID join missing (backlog target)**: 6,585 (29.05%)
- **Strong deterministic evidence**: 11,758 (51.87%)
- **Single-QID but join missing**: 5,822 (25.68%)
- **Multi-QID synsets**: 1,252 (5.52%)

## Key Statistics on 16.08.2026

- **Total candidate pairs**: 22,691
- **QID join found (in Wikidata)**: 21,785 (96.01%)
- **QID join missing (backlog target)**: 906 (3.99%)
- **Strong deterministic evidence**: 18,592 (81.94%)
- **Single-QID but join missing**: 140 (0.62%)
- **Multi-QID synsets**: 1,255 (5.53%)

## Key Statistics on 02.11.2026

- **Total candidate pairs**: 26,695
- **QID join found (in Wikidata)**: 24,960 (93.50%)
- **QID join missing (backlog target)**: 1,735 (6.50%)
- **Strong deterministic evidence**: 24,337 (91.17%)
- Refreshed with one command: `python scripts/refresh_mappings.py` (current source repos + live Wikidata)

## Workflow

### Core Import Pipeline

```
1. Extract:  extract_yaml.py → merged_mapped.csv
2. Fetch:    fetch_wikidata.py → wikidata_wordnet_links.csv  
3. Compare:  build_comparison_table.py → comparison_table.csv
4. Identify: Backlog CSVs (entries missing from Wikidata)
5. Clean:    clean_backlogs.py → cleaned backlog files
6. Transform: backlog_to_quickstatements.py → import TSV files
7. Validate: check_qids.py (verify QIDs exist)
8. Import:   submit_to_quickstatements.sh (batch upload)
9. Verify:   verify_import.py (confirm successful import)
```

### Constraint Violation Analysis

```
1. Fetch violations:    fetch_violations.py → p5063_violations_from_wd.csv, p8814_violations_from_wd.csv
2. Categorize:           categorize_violations.py → p5063_violations_categorized.csv, p8814_violations_categorized.csv
3. Enhanced analysis:    categorize_violations_enhanced.py → Similarity matching with confidence scores
4. Final categorization: categorize_all_final.py → 100% coverage with 0% REVIEW
5. Generate dashboard:   generate_dashboard.py → Static HTML dashboard (violations_dashboard.html)
6. Review:              Manually review categories via dashboard (optional)
7. Generate fixes:       Create QuickStatements removal commands for real violations
8. Apply fixes:         Submit to Wikidata via QuickStatements
```

## Properties Used

- **P8814**: WordNet synset ID - Links Wikidata entity to WordNet synset
- **P5063**: Interlingual Index (ILI) - Links Wikidata entity to cross-lingual concept

## Constraint Violation Analysis

The system includes comprehensive analysis of Wikidata constraint violations for P5063 and P8814 properties:

### Key Features

- **Automated Fetching**: SPARQL queries fetch live violation data from Wikidata
- **Categorization**: Automatic classification of violations as real errors or valid duplicates
- **Similarity Matching**: Uses semantic similarity (label, definition, synset members) to score mappings
- **Proposal Generation**: Generates QuickStatements to fix real violations
- **Comprehensive Tracking**: Full comparison table tracks all violations and their proposed fixes

### Statistics (as of current data)

- **P8814 Violations**: 1,977 total, 856 real violations identified
- **P5063 Violations**: 377 unique (QID, ILI) pairs (784 raw SPARQL rows), 147 real violations identified
- **QuickStatements Generated**: 440 P8814 fixes + 75 P5063 fixes = 515 total
- **Reconciliation**: 2,354 statements = 1,351 valid + 488 keep + 515 remove

### Workflow

See the [Constraint Violation Analysis](#constraint-violation-analysis) section below for detailed commands.

## Quick Start

### Core Pipeline

```bash
# Extract mapped synsets from YAML sources
python scripts/extract_yaml.py

# Fetch Wikidata entities with WordNet links
python scripts/fetch_wikidata.py

# Build comparison table
python scripts/build_comparison_table.py

# Clean backlog files
python scripts/clean_backlogs.py \
  --oenn data/backlogs/OENN_backlog.csv \
  --oewn data/backlogs/OEWN-Backlog.csv \
  --output-oenn data/backlogs/OENN_backlog_cleaned.csv \
  --output-oewn data/backlogs/OEWN-Backlog_cleaned.csv

# Generate QuickStatements import
python scripts/backlog_to_quickstatements.py \
  --oenn data/backlogs/OENN_backlog_cleaned.csv \
  --oewn data/backlogs/OEWN-Backlog_cleaned.csv \
  --multi-qid-review data/output/multi_qid_review.csv \
  --output data/output/wikidata_import_cleaned.tsv

# Verify QIDs exist
python scripts/check_qids.py

# Submit to QuickStatements (after manual OAuth setup)
./scripts/submit_to_quickstatements.sh \
  --username YOUR_USERNAME \
  --token YOUR_TOKEN \
  --file data/output/wikidata_import_cleaned.tsv \
  --batchname "OEWN_OENN_Import_$(date +%Y%m%d)"

# After import, verify results
python scripts/verify_import.py \
  --old data/output/comparison_table.csv.backup \
  --new data/output/comparison_table.csv
```

### Constraint Violation Analysis

```bash
# Fetch live violations from Wikidata SPARQL
python scripts/fetch_violations.py

# Categorize violations (identifies real vs false positives)
python scripts/categorize_violations.py

# Enhanced categorization with similarity matching
python scripts/categorize_violations_enhanced.py

# Final categorization with 100% coverage (0% REVIEW)
python scripts/categorize_all_final.py

# Cross-check duplicate groups against the source repos (reads upstream/main via git archive)
python scripts/crosscheck_sources.py

# Generate QuickStatements fixes for violations (source repos win; reasons in keep_decisions.csv)
python scripts/generate_proposals_v2.py

# Build comprehensive comparison table with fix tracking
python scripts/build_full_comparison.py

# Run the tests
python3 -m unittest discover -s tests -t .

# Generate the dashboard (reads the *_final.csv, quickstatements/, manual_review/ and missing_ilis_verified.csv outputs)
python scripts/generate_dashboard.py

# Output files in data/output/20260929/:
# - p5063_violations_from_wd.csv
# - p5063_violations_categorized.csv
# - p5063_violations_enhanced.csv
# - p5063_violations_final.csv
# - p8814_violations_from_wd.csv
# - p8814_violations_categorized.csv
# - p8814_violations_enhanced.csv
# - p8814_violations_final.csv
# - violations_dashboard.html
# - full_comparison_table.csv
# - quickstatements/p5063_fixes_quickstatements.txt
# - quickstatements/p8814_fixes_quickstatements.txt
# - proposal_summary_v2.txt
```

## Documentation

- See `docs/WORKFLOW.md` for the lineage, what is done vs to do, and the plan for adding new mappings
- See `docs/backlog_import.md` for detailed import methodology
- See `docs/comparison_pipeline.md` for pipeline architecture and design decisions
- See `docs/constraint_violation_analysis.md` for P5063/P8814 constraint violation analysis methodology
- See `docs/SYSTEM_ARCHITECTURE.md` for complete system architecture and component interactions
- See `data/output/20260929/violations_dashboard.html` for the dashboard (all-mappings table, violation tables, review queue, fixes, missing ILIs). Title and project link: [Wikidata:WikiProject WordNet](https://www.wikidata.org/wiki/Wikidata:WikiProject_WordNet).
