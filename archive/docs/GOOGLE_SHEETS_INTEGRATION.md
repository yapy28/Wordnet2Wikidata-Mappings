# Google Sheets Integration Plan

## Overview

This document describes how to integrate Google Sheets with the WordNet2Wikidata dashboard for easier collaborative review, and set up CI/CD for automated dashboard regeneration.

## Quick Solution for Tomorrow's Call

### Option A: Manual Export/Import (Fastest - 5 minutes)

**Before the call:**
1. Run the comparison table builder:
   ```bash
   python scripts/build_full_comparison.py
   ```
2. Export to CSV: `data/output/20260929/full_comparison_table.csv`
3. Import into Google Sheets:
   - Go to Google Sheets
   - File → Import → Upload → Select the CSV file
   - Or: Create new sheet → File → Import → Select CSV

**During the call:**
- Collaborator can:
  - Filter and sort by any column
  - Add comments to specific rows
  - Use data validation to add dropdowns for decisions
  - Color-code rows by status

**After the call:**
1. Export from Google Sheets as CSV
2. Replace `full_comparison_table.csv`
3. Regenerate dashboard:
   ```bash
   python scripts/generate_comprehensive_dashboard.py
   ```

### Option B: Use Existing Google Sheet

You already have a Google Sheet at:
https://docs.google.com/spreadsheets/d/1AnqYF8XDgEdS1qpUomRsTV8JSxLPEKD5CdpCtrSqL6k/edit

We can:
1. Export our comparison table to CSV
2. Import into a new tab in your existing sheet
3. Set up formulas to link between tabs

## Recommended Google Sheets Structure

Create tabs:

### Tab 1: `P8814_Violations`
- All P8814 violation rows from comparison table
- Columns: QID, WD Label, WD Description, Synset ID, Synset Definition, Category, Status, Decision (dropdown), Notes

### Tab 2: `P5063_Violations`
- All P5063 violation rows
- Same structure as P8814 tab

### Tab 3: `Decisions`
- Reference table for manual decisions
- Columns: Property, Value, Action (keep/leave/defer), Keep QID, Note
- Matches `data/output/20260929/manual_review/decisions.csv`

### Tab 4: `Summary`
- Dashboard metrics
- Counts by category
- Progress tracking

## CI/CD Automation (GitHub Actions)

### Workflow File: `.github/workflows/update-dashboard.yml`

```yaml
name: Update Dashboard

on:
  # Manual trigger
  workflow_dispatch:
  # Scheduled trigger (daily at 8am UTC)
  schedule:
    - cron: '0 8 * * *'

jobs:
  update-dashboard:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          
      - name: Fetch violations from Wikidata
        run: python scripts/fetch_violations.py
        
      - name: Categorize violations
        run: |
          python scripts/categorize_violations.py
          python scripts/categorize_violations_enhanced.py
          python scripts/categorize_all_final.py
          
      - name: Generate proposals
        run: python scripts/generate_proposals_v2.py
        
      - name: Build comparison table
        run: python scripts/build_full_comparison.py
        
      - name: Generate comprehensive dashboard
        run: python scripts/generate_comprehensive_dashboard.py
        
      - name: Commit changes
        run: |
          git config --global user.name "GitHub Actions"
          git config --global user.email "actions@github.com"
          git add data/output/20260929/
          git add scripts/
          git add docs/
          git commit -m "Auto-update: Dashboard and violation data [$(date +%Y-%m-%d)]"
          git push
```

### Google Sheets Sync (Advanced)

To automatically sync with Google Sheets, add these steps:

```yaml
      - name: Upload to Google Sheets
        uses: satackey/action-google-sheets@v1
        with:
          credentials: ${{ secrets.GOOGLE_SHEETS_CREDENTIALS }}
          spreadsheet-id: '1AnqYF8XDgEdS1qpUomRsTV8JSxLPEKD5CdpCtrSqL6k'
          sheet-name: 'P8814_Violations'
          data: ${{ steps.export-csv.outputs.data }}
```

Requires:
1. Google Service Account with Sheets API access
2. Secrets configured in GitHub repo
3. Sheet shared with service account email

## Implementation Roadmap

### Phase 1: Tomorrow's Call (Manual)
- [ ] Export current comparison table to CSV
- [ ] Import into Google Sheets
- [ ] Share with collaborator for review
- [ ] Document their feedback

### Phase 2: Basic CI/CD (Next week)
- [ ] Set up GitHub Actions workflow
- [ ] Test scheduled runs
- [ ] Verify data consistency

### Phase 3: Google Sheets Sync (Future)
- [ ] Set up Google Service Account
- [ ] Configure GitHub Secrets
- [ ] Implement two-way sync
- [ ] Add change tracking

## Manual Review Process

For collaborators reviewing in Google Sheets:

1. **Filter by status**: Use "FIX_PROPOSED", "NEEDS_FIX", "VALID"
2. **Review categories**: Focus on "Different concepts", "Dissimilar QIDs" first
3. **Make decisions**: 
   - Mark "LEAVE" to keep both mappings
   - Mark "REMOVE" to remove duplicate
   - Add notes explaining rationale
4. **Export decisions**: Download as CSV when done

## File Mapping

| Local File | Google Sheets Tab | Purpose |
|------------|------------------|---------|
| `full_comparison_table.csv` | P8814_Violations + P5063_Violations | All violations for review |
| `decisions.csv` | Decisions | Manual override decisions |
| `p8814_violations_final.csv` | P8814_Raw | Raw P8814 data |
| `p5063_violations_final.csv` | P5063_Raw | Raw P5063 data |

## Quick Start for Tomorrow

```bash
# 1. Generate latest data
python scripts/fetch_violations.py
python scripts/categorize_violations.py
python scripts/categorize_violations_enhanced.py
python scripts/categorize_all_final.py
python scripts/generate_proposals_v2.py
python scripts/build_full_comparison.py

# 2. Copy the file you need
ecp data/output/20260929/full_comparison_table.csv ~/Downloads/

# 3. Import to Google Sheets
#    - Open Google Sheets
#    - File -> Import -> Upload -> Select the CSV
#    - Share with collaborator

# 4. After review, regenerate
python scripts/generate_comprehensive_dashboard.py
```

## Notes

- The current dashboard has 2,354 rows total
- 1,977 P8814 violations (856 real, 1,121 valid)
- 377 P5063 violations (312 real, 65 valid)
- 515 QuickStatements proposed
- All category names are now human-readable
- Links to Wikidata, ILIs, and synsets are included
