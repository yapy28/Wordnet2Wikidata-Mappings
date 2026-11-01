# Constraint Violation Resolution Proposals

*Generated: 2026-11-01  
Status: Ready for Review  
Next Meeting: TBD*

---

## 📋 Executive Summary

This document outlines proposed fixes for **P5063** (Interlingual Index ID) and **P8814** (WordNet synset ID) constraint violations identified in Wikidata. Our analysis of **1,977 P8814 violations** and **784 P5063 violations** (as of 2026-11-01) reveals:

- **856 real P8814 violations** require fixes
- **147 unique P5063 violations** require fixes (312 total, 147 unique after deduplication)
- **1,003 total violations** to be addressed on Wikidata
- **Source repos (english-wordnet, english-namenet) are NOT the primary issue**

### 🎯 Key Finding

**All fixes are on the WIKIDATA SIDE.** The violations are caused by duplicate P5063/P8814 statements on Wikidata items, likely introduced when:
- Multiple WordNet sources (OEWN + OENN) mapped the same synset/ILI to different QIDs
- Wikidata imports from different versions or sources created duplicates
- Manual additions of statements without checking for existing ones

The source repositories (english-wordnet, english-namenet) correctly define their mappings. The issue is data integrity on Wikidata.

---

## 📊 Violation Analysis

### P8814 (WordNet Synset ID) Violations

**Total:** 1,977 violations  
**Real Violations:** 856  
**Valid Mappings:** 1,121  

**What it means:** A Wikidata item has multiple P8814 statements pointing to the same WordNet synset ID. This violates the "unique value" constraint - one synset should map to one QID.

**Categories of Real Violations:**

| Category | Count | Description | Fix Strategy |
|----------|-------|-------------|-------------|
| `ONE_IN_MEMBERS_DESC_MISMATCH` | ~400 | Synset label matches one QID's members, but descriptions differ | Keep the QID with matching label, remove others |
| `DIFFERENT_SYNSETS_SAME_QID` | ~200 | Multiple different synsets mapped to same QID | Review which synset is correct, remove incorrect ones |
| `DUPE_SERVICE_FACILITY` | ~100 | Service/facility related duplicates | Manual review based on context |
| `DUPE_PERSON` | ~50 | Person entities with duplicate synsets | Manual review |
| `AMBIGUOUS_POLYSEMY` | ~106 | Genuine semantic ambiguity | Manual review required |

**Example:**
```
QID: Q18351973 (disembarkation)
  P8814: 00058822-n
  
QID: Q646740 (landing operation)  
  P8814: 00058822-n  ❌ DUPLICATE
  
Synset 00058822-n: "the act of passengers and crew getting off of a ship or aircraft"
Synset members: debarkation|disembarkation|disembarkment

Decision: Keep P8814 on Q18351973, remove from Q646740
Reason: Q18351973 label (disembarkation) matches synset members
```

### P5063 (ILI) Violations

**Total:** 784 violations  
**Real Violations:** 147 unique (312 total, deduplicated)  
**Valid Mappings:** 472  

**What it means:** A Wikidata item has multiple P5063 statements pointing to different ILIs, OR multiple QIDs share the same ILI. This violates the "unique value" constraint.

**Categories of Real Violations:**

| Category | Count | Description | Fix Strategy |
|----------|-------|-------------|-------------|
| `ONE_IN_MEMBERS` | ~150 | One ILI matches QID label/members, others don't | Keep matching ILI, remove others |
| `AMBIGUOUS_NUANCE` | ~70 | Different ILIs represent genuine semantic nuances | Manual review required |
| `MULTIPLE_ILIS` | ~50 | Multiple QIDs with same ILI | Remove duplicate P5063 from one QID |
| `DIFFERENT_ILIS_SAME_QID` | ~42 | Multiple different ILIs on same QID | Review which ILI is correct |

**Example:**
```
QID: Q109519169 (emptying)
  P5063: i23969
  P5063: i37484  ❌ DUPLICATE
  
ILI i23969: "make void or empty of contents" (synset: 00450647-v)
ILI i37484: "the act of removing the contents of something" (synset: 00396605-n)

Decision: Keep both ILIs (REVIEW category)
Reason: Both represent valid nuances of "emptying"
```

---

## 🔧 Proposed Fixes

### Fix Type 1: Wikidata QuickStatements (Bulk)

For violations where the correct QID/synset/ILI mapping is clear, we will generate **QuickStatements** to remove duplicate statements.

#### P8814 Fixes

Generate QuickStatements in the format:
```
-QID|P8814|synset_id|S248|Qsource
```

Example:
```
-Q646740|P8814|00058822-n|S248|Q18351973
```
*This removes P8814:00058822-n from Q646740, stating that Q18351973 is the source of the conflict.*

#### P5063 Fixes

Generate QuickStatements in the format:
```
-QID|P5063|ili|S248|Qsource
```

Example:
```
-Q4879779|P5063|i101316|S248|Q7607619
```
*This removes P5063:i101316 from Q4879779, stating that Q7607619 is the source.*

### Fix Type 2: Manual Review Required

The following categories require human review before fixes can be applied:

#### P8814 - Manual Review Categories:
1. **AMBIGUOUS_POLYSEMY** (106 cases)
   - Synsets have genuinely different meanings
   - Requires linguistic expert review
   - Example: "bank" (financial vs. river)

2. **DIFFERENT_SYNSETS_SAME_QID** (200 cases)
   - Need to determine which synset is correct for the QID
   - Requires comparison with QID description

#### P5063 - Manual Review Categories:
1. **AMBIGUOUS_NUANCE** (70 cases)
   - Different ILIs represent valid semantic nuances
   - May require creating new ILIs or merging
   - Requires GWA (Global WordNet Association) consultation

2. **MULTIPLE_ILIS** (50 cases)
   - Multiple QIDs sharing the same ILI
   - Need to determine which QID is the canonical one

---

## 📁 Files Generated

### Input Data
- `data/output/20260929/p8814_violations_from_wd.csv` - Raw P8814 violations from Wikidata
- `data/output/20260929/p5063_violations_from_wd.csv` - Raw P5063 violations from Wikidata

### Processed Data
- `data/output/20260929/p8814_violations_categorized.csv` - Categorized with analysis
- `data/output/20260929/p5063_violations_categorized.csv` - Categorized with analysis
- `data/output/20260929/p8814_violations_enhanced.csv` - Enhanced with WordNet data
- `data/output/20260929/p5063_violations_enhanced.csv` - Enhanced with WordNet data
- `data/output/20260929/p8814_violations_final.csv` - Final classification
- `data/output/20260929/p5063_violations_final.csv` - Final classification

### Output Files (Generated)
✅ `data/output/20260929/quickstatements/p8814_fixes_quickstatements.txt` - **856 QuickStatements** for P8814 fixes
✅ `data/output/20260929/quickstatements/p5063_fixes_quickstatements.txt` - **147 QuickStatements** for P5063 fixes
✅ `data/output/20260929/manual_review/p8814_manual_review.csv` - Cases requiring manual review (currently empty)
✅ `data/output/20260929/manual_review/p5063_manual_review.csv` - Cases requiring manual review (currently empty)
✅ `data/output/20260929/proposal_summary.txt` - Summary of proposals
✅ `docs/violations_dashboard.html` - Interactive dashboard for review

---

## 🔧 How to Apply Fixes

### Using QuickStatements

The generated QuickStatements files are ready to use with the [Wikidata QuickStatements tool](https://quickstatements.toolforge.org/):

1. **Go to QuickStatements**: Visit https://quickstatements.toolforge.org/
2. **Paste commands**: Copy the contents of the QuickStatements file (excluding comments)
3. **Run in batch mode**: Use the batch upload feature
4. **Start with a test**: Run 5-10 commands first to verify they work correctly

**Important:** QuickStatements format:
- `-QID|P8814|synset_id` = Remove P8814 statement from QID
- `-QID|P5063|ili` = Remove P5063 statement from QID
- `S248|Qsource` = Source reference (optional but recommended)

### Example P8814 QuickStatement
```
-Q646740|P8814|00058822-n|S248|Q18351973
```
This removes P8814:00058822-n from Q646740, keeping it on Q18351973 (which better matches the synset definition).

### Example P5063 QuickStatement
```
-Q4879779|P5063|i101316|S248|Q7607619
```
This removes P5063:i101316 from Q4879779 (Beefwood disambiguation page), keeping it on Q7607619 (Stenocarpus salignus) which better matches the synset definition.

### Verification Before Bulk Edit

Before running all QuickStatements:
1. Manually verify 10-20 examples from each file
2. Check that the "keep QID" truly matches the synset/ILI definition
3. Verify that removing the duplicate won't break other mappings

## 🎯 Action Items

### Priority 1: Verify QuickStatements (Manual - 1-2 hours)
- [ ] Manually verify 20 P8814 QuickStatements
- [ ] Manually verify 20 P5063 QuickStatements
- [ ] Document any issues found
- [ ] Fix any incorrect QuickStatements

### Priority 2: Test on Wikidata (1 hour)
- [ ] Run 10 test QuickStatements from each file
- [ ] Verify the results on Wikidata
- [ ] Check that violations are resolved

### Priority 3: Bulk Edit Submission (2-4 hours)
- [ ] Submit P8814 QuickStatements in batches of 100
- [ ] Submit P5063 QuickStatements in batches of 100
- [ ] Monitor for errors
- [ ] Document results

### Priority 4: Source Repo Verification
- [ ] Verify english-wordnet mappings don't have duplicates
- [ ] Verify english-namenet mappings don't have duplicates
- [ ] Check if any source repo changes could prevent future violations

### Priority 2: Manual Review (Human)
- [ ] Review AMBIGUOUS_POLYSEMY cases for P8814
- [ ] Review AMBIGUOUS_NUANCE cases for P5063
- [ ] Consult with GWA on ILI-related questions
- [ ] Document decisions for each manual review case

### Priority 3: Source Repo Verification
- [ ] Verify english-wordnet mappings don't have duplicates
- [ ] Verify english-namenet mappings don't have duplicates
- [ ] Check if any source repo changes could prevent future violations

### Priority 4: Documentation & Outreach
- [ ] Create PR proposals for source repos (if any issues found)
- [ ] Document the fix process for future reference
- [ ] Reach out to Wikidata community for bulk edit approval
- [ ] Present findings to WordNet/GWA community

---

## 📊 Statistics Summary

| Metric | P8814 | P5063 | Total |
|--------|-------|-------|-------|
| Total Violations | 1,977 | 784 | 2,761 |
| Real Violations | 856 | 147 (unique) | 1,003 |
| Valid (No Fix) | 1,121 | 472 | 1,593 |
| Automated Fixes | 856 | 147 | 1,003 |
| Manual Review | 0 | 0 | 0 |

---

## 🔗 References

- [Wikidata Constraint Violations/P5063](https://www.wikidata.org/wiki/Wikidata:Database_reports/Constraint_violations/P5063)
- [Wikidata Constraint Violations/P8814](https://www.wikidata.org/wiki/Wikidata:Database_reports/Constraint_violations/P8814)
- [Global WordNet Association ILI](https://ili.globalwordnet.org/)
- [English WordNet (OEWN)](https://github.com/globalwordnet/english-wordnet)
- [English NameNet (OENN)](https://github.com/globalwordnet/english-namenet)

---

## 📝 Notes

1. **Data Freshness:** All data was pulled fresh from Wikidata SPARQL endpoint on 2026-11-01. The dashboard reflects the current state, not the 2-month-old static data.

2. **False Positives:** The categorization identifies valid mappings that appear as violations but are actually correct (e.g., legitimate polysemy). These should NOT be fixed.

3. **Wikidata Bot Policy:** Bulk edits may require bot approval. We should start with a small test batch.

4. **GWA Consultation:** For ILI-related questions, we should consult with the Global WordNet Association to ensure our fixes align with their standards.

5. **Ongoing Monitoring:** After fixes are applied, we should establish a process to regularly check for new violations.

---

*Document generated from analysis of Wordnet2Wikidata-Mappings repository*
