# WordNet to Wikidata Mappings

A pipeline for validating and importing synset-to-Wikidata mappings from Open English WordNet (OEWN) and Open English Namenet (OENN).

## Repository Structure

```
Wordnet2Wikidata-Mappings/
├── LICENSE                                    # MIT License for the project
├── docs/
│   ├── BACKLOG_IMPORT.md                      # Detailed workflow and methodology for importing validated mappings via QuickStatements
│   └── comparison_pipeline.md                 # Pipeline design documentation with mermaid diagrams and use cases
├── scripts/
│   ├── backlog_to_quickstatements.py         # Transforms cleaned backlog CSVs into QuickStatements TSV format for Wikidata import
│   ├── build_comparison_table.py             # Builds verification comparison table from merged_mapped.csv and wikidata_wordnet_links.csv
│   ├── check_qids.py                         # Validates that QIDs in the import file still exist on Wikidata
│   ├── clean_backlogs.py                     # Removes entries with empty, missing, or invalid ILI values from backlog CSVs
│   ├── enhance_multiqid_review.py            # Adds hypernym chain column and semantic scores to multi_qid_review.csv
│   ├── extract_yaml.py                       # Extracts synset entries with Wikidata mappings from OEWN/OENN YAML sources
│   ├── fetch_wikidata.py                     # Queries Wikidata SPARQL endpoint to fetch all entities linked via P5063 (ILI) or P8814 (synset ID)
│   ├── submit_to_quickstatements.sh          # Shell script to submit QuickStatements batch via API for automated Wikidata import
│   └── verify_import.py                      # Compares old vs new comparison tables to verify successful import of statements
└── data/
    ├── backlogs/
    │   ├── OENN_backlog.csv                   # OENN entries with validated QID mappings missing from Wikidata (original)
    │   ├── OENN_backlog_cleaned.csv           # OENN backlog with invalid ILI entries removed
    │   ├── OEWN-Backlog.csv                   # OEWN entries with validated QID mappings missing from Wikidata (original)
    │   └── OEWN-Backlog_cleaned.csv           # OEWN backlog with invalid ILI entries removed
    └── output/
        ├── comparison_table.csv               # Main comparison table with 22,670 candidate pairs and match signals
        ├── multi_qid_review.csv               # Synsets with multiple candidate QIDs requiring manual adjudication
        ├── multi_qid_review_with_scores.csv   # Enhanced multi-QID review with semantic similarity scores
        ├── wikidata_import_oenn.csv            # QuickStatements import file generated from OENN backlog
        ├── wikidata_import_oenn.tsv            # TSV format QuickStatements import for OENN
        ├── wikidata_import_oewn.csv            # QuickStatements import file generated from OEWN backlog
        ├── wikidata_import_oewn.tsv            # TSV format QuickStatements import for OEWN
        ├── wikidata_import_cleaned.csv         # Combined cleaned QuickStatements import (CSV format)
        └── wikidata_import_cleaned.tsv          # Combined cleaned QuickStatements import (TSV format, ready for batch upload)
```

## Overview

This project provides a complete pipeline for:

1. **Extracting** synset entries with Wikidata mappings from OEWN and OENN YAML sources
2. **Comparing** these mappings against current Wikidata links to identify missing connections
3. **Validating** mappings using deterministic match signals (synset ID, ILI, label, definition)
4. **Generating** QuickStatements batch files for importing missing links into Wikidata
5. **Verifying** successful import by regenerate comparison tables

## Key Statistics

- **Total candidate pairs**: 22,670
- **QID join found (in Wikidata)**: 16,085 (70.95%)
- **QID join missing (backlog target)**: 6,585 (29.05%)
- **Strong deterministic evidence**: 11,758 (51.87%)
- **Single-QID but join missing**: 5,822 (25.68%)
- **Multi-QID synsets**: 1,252 (5.52%)

## Workflow

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

## Properties Used

- **P8814**: WordNet synset ID - Links Wikidata entity to WordNet synset
- **P5063**: Interlingual Index (ILI) - Links Wikidata entity to cross-lingual concept

## Quick Start

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

## Documentation

- See `docs/BACKLOG_IMPORT.md` for detailed import methodology
- See `docs/comparison_pipeline.md` for pipeline architecture and design decisions
