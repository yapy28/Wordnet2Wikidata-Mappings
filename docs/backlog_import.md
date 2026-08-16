# Wikidata Backlog Import Guide

## Overview

This document describes the methodology and workflow for importing validated Open English WordNet (OEWN) and Open English Namenet (OENN) synset-to-Wikidata mappings into Wikidata via QuickStatements.

The workflow addresses **missing Wikidata links** identified by the comparison pipeline: synsets that have validated QID mappings in the YAML source but lack corresponding P8814 (synset ID) or P5063 (ILI) statements in Wikidata.

## Background

### Pipeline Results (as of current snapshot)

| Metric                                     | Count  | Percentage |
| ------------------------------------------ | ------ | ---------- |
| Total candidate pairs                      | 22,670 | 100%       |
| QID join found (in Wikidata)               | 16,085 | 70.95%     |
| QID join**missing** (backlog target) | 6,585  | 29.05%     |
| Strong deterministic evidence              | 11,758 | 51.87%     |
| Multi-QID rows                             | 1,252  | 5.52%      |
| Single-QID but join missing                | 5,822  | 25.68%     |

### Source Breakdown

| Source | Rows   | Join Found | Join Missing | Multi-QID | Strong Evidence |
| ------ | ------ | ---------- | ------------ | --------- | --------------- |
| OEWN   | 9,913  | 63.43%     | 36.57%       | 11.5%     | 41.19%          |
| OENN   | 12,757 | 76.8%      | 23.2%        | 0.88%     | 60.16%          |

## File Formats

### Input Files: Backlog CSVs

Two backlog files contain synsets with validated QID mappings that are **missing from Wikidata after they were worked on in Google Sheets: [docs.google.com/spreadsheets/d/1AnqYF8XDgEdS1qpUomRsTV8JSxLPEKD5CdpCtrSqL6k/edit?pli=1&amp;gid=759608002#gid=759608002](https://docs.google.com/spreadsheets/d/1AnqYF8XDgEdS1qpUomRsTV8JSxLPEKD5CdpCtrSqL6k/edit?pli=1&gid=759608002#gid=759608002)**

### Output File: QuickStatements TSV

- **Path**: `/wikidata/output/wikidata_import.tsv`
- **Format**: Tab-separated values (TSV)
- **Schema**: QuickStatements v2 batch format
- **Columns**:
  - `qid`: Wikidata entity ID
  - `property`: Wikidata property ID (P8814 or P5063)
  - `value`: Property value (synset ID or ILI)
  - `reference` (optional): Reference for the statement

#### QuickStatements Format Example

```tsv
Q22111431	P8814	"01372125-n"
Q22111431	P5063	"i42517"
```

Each row represents a single claim to be added to Wikidata.

### Review Queue: multiQID_review.csv

- **Path**: `/wikidata/output/multi_qid_review.csv`
- **Purpose**: Contains synsets with multiple candidate QIDs that require manual adjudication
- **Columns**: Extended with Wikidata label, parent, and description for review context
- **Action**: These require human review before import; not included in automated QuickStatements generation

## Methodology

### Step 0: Preprocessing - Clean Backlog Files

Before transformation, clean the backlog CSV files to remove entries with invalid ILI values:

```bash
python3 scripts/clean_backlogs.py
```

This removes entries where `wn_ili` is:

- Empty string
- "?"
- Any whitespace-only value

**Why**: The transformation script requires valid ILI values for P5063 statements. Entries without valid ILI can still be processed (they'll only get P8814 statements), but cleaning ensures consistency.

### Step 1: Backlog Identification

The comparison pipeline (`build_comparison_table.py`) identifies backlog entries by:

1. **Expanding multi-QID synsets**: Each synset with multiple QID candidates creates separate rows
2. **Joining on QID**: Attempting to match each `qid_candidate` with Wikidata entries
3. **Flagging missing joins**: Rows where `flag_qid_join_found = "0"` indicate missing Wikidata links
4. **Filtering for single-QID backlog**: Entries with `qid_count_original = 1` and `flag_qid_join_found = "0"` are high-confidence missing links

### Step 2: Backlog Validation

Entries are validated based on deterministic match signals:

- **Strong evidence** (auto-accept candidates):

  - `flag_match_ssid_exact = "1"` OR
  - `flag_match_ili_exact = "1"` AND (`flag_label_in_members_exact = "1"` OR `flag_label_in_members_norm = "1"`)
- **Review required**:

  - Multi-QID synsets (`multi_qid_original = "TRUE"`)
  - Conflicting structural evidence
  - Weak text evidence only

### Step 3: QuickStatements Transformation

For each backlog entry, generate **two statements**:

1. **P8814 (synset ID)**: Links Wikidata entity to WordNet synset

   - Format: `{QID}\tP8814\t"{synset_id}"`
2. **P5063 (ILI)**: Links Wikidata entity to Interlingual Index

   - Format: `{QID}\tP5063\t"{ili}"`

**Note**: Both statements are generated for each synset-QID pair. The ILI is the preferred identifier for cross-lingual linking.

### Step 4: Batch Import via QuickStatements

1. Upload the TSV file to [QuickStatements](https://quickstatements.wmflabs.org/)
2. Use batch mode for efficient processing
3. Review the preview for each statement
4. Execute the batch import

### Step 5: Verification

After import, regenerate the comparison table and verify:

1. **Count reduction**: Number of rows with `flag_qid_join_found = "0"` should decrease
2. **Specific verification**: Previously missing QIDs should now show `flag_qid_join_found = "1"`
3. **No regressions**: Existing joins should remain intact

## Transformation Rules

### Inclusion Criteria

A backlog entry is included in the QuickStatements output if:

1. **Has valid QID**: `wn_wd_qid` matches pattern `^Q[1-9][0-9]*$`
2. **Has synset ID**: `wn_synset` is non-empty
3. **Has ILI**: `wn_ili` is non-empty (for OENN; optional for OEWN)
4. **Not in multi-QID review**: Entry is not flagged for multi-QID adjudication

### Exclusion Criteria

A backlog entry is excluded if:

1. **Invalid QID**: Does not match Wikidata QID pattern
2. **Missing synset ID**: No synset identifier available
3. **Multi-QID conflict**: Entry appears in `multi_qid_review.csv` (requires manual review)
4. **Duplicate**: Same (QID, synset_id, ili) combination appears multiple times

### Property Selection

- **P8814**: WordNet synset ID - Always added when synset_id is available
- **P5063**: Interlingual Index (ILI) - Added when ili is available

Both properties serve different purposes:

- P8814: Direct synset-to-entity linkage (instance-level)
- P5063: Cross-lingual concept linkage (concept-level)

## Verification Steps

### Pre-Import Checklist

- [ ] Backlog CSVs exist and are readable
- [ ] All QIDs in backlog are valid Wikidata identifiers
- [ ] All synset IDs follow expected patterns (e.g., `XXXXXXX-n`)
- [ ] No duplicate entries in the output TSV
- [ ] TSV file is properly tab-delimited
- [ ] QuickStatements preview shows expected statements

### Post-Import Verification

1. **Regenerate comparison table**:

   ```bash
   python build_comparison_table.py
   ```
2. **Run verification script**:

   ```bash
   python verify_import.py --old output/comparison_table.csv.backup \
                          --new output/comparison_table.csv
   ```
3. **Manual spot checks**:

   - Select 10 random QIDs from the import TSV
   - Verify they appear in Wikidata with the new properties
   - Check that P8814 and P5063 values are correct

### Verification Report

The verification script produces:

```
=== QuickStatements Import Verification ===

Total rows in new table: 22,670
Successfully inserted (was 0, now 1): 6,500
Still missing (remains 0): 85
New mismatches: 0
Insertion rate: 98.7%

Top 10 successfully inserted:
  Q22111431: flag_qid_join_found changed 0->1
  Q187668: flag_qid_join_found changed 0->1
  ...

Still missing (sample):
  Q123456: synset_id=01234567-n, ili=i12345
  ...
```

## File Locations

All paths are relative to `/Users/gabri/git/testenv/wikidata/`

```
wikidata/
├── BACKLOG_IMPORT.md              # This document
├── OENN_backlog.csv               # OENN entries (original, ~2,958 rows)
├── OEWN-Backlog.csv               # OEWN entries (original, ~2,864 rows)
├── OENN_backlog_cleaned.csv       # OENN entries (cleaned, 2,934 rows)
├── OEWN-Backlog_cleaned.csv       # OEWN entries (cleaned, 2,772 rows)
├── build_comparison_table.py      # Builds comparison_table.csv
├── comparison_pipeline.md         # Pipeline documentation
├── output/
│   ├── comparison_table.csv           # Current comparison (22,670 rows)
│   ├── multi_qid_review.csv           # Multi-QID cases for manual review (959 rows)
│   ├── multi_qid_review_with_scores.csv
│   ├── wikidata_import.tsv            # Generated from original backlogs (11,518 statements)
│   └── wikidata_import_cleaned.tsv   # Generated from cleaned backlogs (11,404 statements)
└── scripts/
    ├── backlog_to_quickstatements.py  # Transformation script
    ├── verify_import.py                # Verification script
    └── clean_backlogs.py               # Removes entries with empty/? ILI
```

## Actual Current Counts (from test run)

### Before Cleaning

- **OENN_backlog.csv**: 2,958 entries
- **OEWN-Backlog.csv**: 2,864 entries
- **Total backlog entries**: 5,822

### After Cleaning (removed entries with empty/? ILI)

- **OENN_backlog_cleaned.csv**: 2,934 entries (24 removed with empty ILI)
- **OEWN-Backlog_cleaned.csv**: 2,772 entries (92 removed: 2 with "?" ILI + 90 with empty ILI)
- **Total cleaned entries**: 5,706
- **Invalid entries**: 4 (bad QID format - P-prefix instead of Q)
- **Valid entries**: 5,702
- **QuickStatements generated**: 11,404
  - P8814 (synset ID) statements: 5,702
  - P5063 (ILI) statements: 5,702
- **Multi-QID exclusions**: 0 (none of the backlog entries are in multi_qid_review.csv)

### Invalid Entries Filtered Out

The 4 invalid entries excluded (P-prefix QIDs):

| Synset ID  | QID   | ILI     | Source | Error                        |
| ---------- | ----- | ------- | ------ | ---------------------------- |
| 08808051-n | n.a   | i83060  | OENN   | Invalid QID format           |
| 09909143-n | P2453 | i88791  | OEWN   | Invalid QID format (P not Q) |
| 10593273-n | P3975 | i92838  | OEWN   | Invalid QID format (P not Q) |
| 15186678-n | P841  | i116888 | OEWN   | Invalid QID format (P not Q) |

**Note**: Some OEWN entries use "P" prefixes instead of "Q" for Wikidata IDs. These appear to be Wikidata property IDs rather than entity IDs and should be investigated.

### Cleaning Summary

- **Empty ILI entries removed**: 24 from OENN, 90 from OEWN = 114 total
- **"?" ILI entries removed**: 2 from OEWN
- **Total removed by cleaning**: 116 rows

## Example Workflow

### Generate QuickStatements TSV

```bash
# Create the import file
python scripts/backlog_to_quickstatements.py \
  --oenn wikidata/OENN_backlog.csv \
  --oewn wikidata/OEWN-Backlog.csv \
  --output wikidata/output/wikidata_import.tsv

# Check the output
head -20 wikidata/output/wikidata_import.tsv
wc -l wikidata/output/wikidata_import.tsv
```

### Import via QuickStatements

#### Option A: Web Interface (Recommended for first use)

1. Go to https://quickstatements.toolforge.org/
2. Click "Batch" mode
3. Upload `wikidata_import_cleaned.tsv`
4. Select "Tab-separated values" format
5. Click "Preview" to review statements
6. If all looks correct, click "Import"
7. **Important**: Submit at least ONE batch manually to initialize OAuth for API access

#### Option B: API Submission (for automation)

Use the provided shell script or curl directly:

```bash
# Using the script
chmod +x scripts/submit_to_quickstatements.sh
./scripts/submit_to_quickstatements.sh \
    --username Yapy28 \
    --token YOUR_TOKEN \
    --file output/wikidata_import_cleaned.tsv \
    --batchname "OEWN_OENN_Import_20260816"

# Or using curl directly
curl -X POST "https://quickstatements.toolforge.org/api.php" \
  -d "action=import" \
  -d "submit=1" \
  -d "format=v1" \
  -d "username=Yapy28" \
  -d "token=URL_ENCODED_TOKEN" \
  -d "batchname=OEWN_OENN_Import" \
  --data-urlencode "data@output/wikidata_import_cleaned.tsv"
```

**Important**: Before using the API, you must:

1. Go to https://quickstatements.toolforge.org/
2. Submit at least one batch manually through the web interface
3. Get your API token from the interface
4. This initializes OAuth permissions for programmatic access

**Note**: The token you provided (`$2y$12$UWfX0F2HPZ4jxSFSTZWkp.AGR3bkJULbkT3zOQSQMLaJ9SU8MDj8S`) needs OAuth initialization. The API returned: "Problem generating OAuth signature; user 'Yapy28' needs to have submitted a batch manually at least once before"

### Verify Import

```bash
# Backup the current comparison table
cp wikidata/output/comparison_table.csv wikidata/output/comparison_table.csv.backup

# Regenerate after import (wait 24-48 hours for Wikidata propagation)
python wikidata/build_comparison_table.py

# Run verification
python scripts/verify_import.py \
  --old wikidata/output/comparison_table.csv.backup \
  --new wikidata/output/comparison_table.csv
```

## Troubleshooting

### Common Issues

1. **QID not found in Wikidata**: The entity may have been deleted or merged. Verify the QID exists at https://www.wikidata.org/wiki/Q12345
2. **Property constraint violation**: P8814 expects a string value (synset ID). P5063 expects an ILI string. Ensure values are properly quoted.
3. **Duplicate statements**: QuickStatements will skip duplicates. This is safe.
4. **Rate limiting**: For large batches (>500 statements), use batch mode and expect processing delays.
5. **Propagation delay**: Wikidata changes may take 24-48 hours to appear in SPARQL queries. The verification script should be run after this delay.

### Error Handling

The transformation script validates all inputs and reports:

- Invalid QID formats
- Missing required fields (synset_id, ili)
- Duplicate entries
- Multi-QID conflicts

Run with `--validate-only` to check without generating output:

```bash
python scripts/backlog_to_quickstatements.py --validate-only
```

## Best Practices

1. **Start small**: Test with a subset of 50-100 entries first
2. **Verify manually**: Check 5-10 imported statements directly in Wikidata
3. **Batch size**: Keep initial batches under 500 statements
4. **Document**: Record date, batch size, and results for each import
5. **Backup**: Always backup comparison tables before and after import

## Quick Reference Commands

### Step 1: Clean backlog files (remove entries with empty/missing ILI)

```bash
python3 scripts/clean_backlogs.py \
  --oenn OENN_backlog.csv \
  --oewn OEWN-Backlog.csv \
  --output-oenn OENN_backlog_cleaned.csv \
  --output-oewn OEWN-Backlog_cleaned.csv
```

### Step 2: Validate cleaned backlog files

```bash
python3 scripts/backlog_to_quickstatements.py \
  --oenn OENN_backlog_cleaned.csv \
  --oewn OEWN-Backlog_cleaned.csv \
  --validate-only
```

### Step 3: Generate QuickStatements TSV

```bash
python3 scripts/backlog_to_quickstatements.py \
  --oenn OENN_backlog_cleaned.csv \
  --oewn OEWN-Backlog_cleaned.csv \
  --multi-qid-review output/multi_qid_review.csv \
  --output output/wikidata_import.tsv
```

### Verify import (after regenerating comparison table)

```bash
# First backup
cp output/comparison_table.csv output/comparison_table_backup.csv

# After import, regenerate
python3 build_comparison_table.py

# Then verify
python3 scripts/verify_import.py \
  --old output/comparison_table_backup.csv \
  --new output/comparison_table.csv \
  --import-file output/wikidata_import.tsv
```

## References

- QuickStatements: https://quickstatements.wmflabs.org/
- QuickStatements documentation: https://www.wikidata.org/w/index.php?title=Help:QuickStatements
- P8814 (WordNet synset ID): https://www.wikidata.org/wiki/Property:P8814
- P5063 (ILI): https://www.wikidata.org/wiki/Property:P5063
- Wikidata editing help: https://www.wikidata.org/wiki/Help:Editing
