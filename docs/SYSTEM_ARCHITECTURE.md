# System Architecture - WordNet2Wikidata Mapping Ecosystem

*Version: 1.0  
Last Updated: 2026-11-01  
Status: Active Development*

---

## 🏗️ Overview

This document describes the **system architecture** for tracking, analyzing, and resolving constraint violations in the WordNet ↔ Wikidata mapping ecosystem. The system provides a **comprehensive mission control dashboard** that monitors all mappings, detects drift, identifies violations, proposes fixes, and tracks progress.

### 🎯 Purpose

The WordNet2Wikidata-Mappings repository maintains the connection between:
- **Open English WordNet (OEWN)** - WordNet synsets mapped to Wikidata QIDs
- **Open English NameNet (OENN)** - Name synsets mapped to Wikidata QIDs
- **Wikidata** - Items with P5063 (ILI) and P8814 (WordNet synset ID) properties

### 📊 Problem Statement

Wikidata has two key properties for WordNet integration:
- **P5063 (Interlingual Index ID)**: Maps Wikidata items to Global WordNet ILIs
- **P8814 (WordNet synset ID)**: Maps Wikidata items to WordNet synsets

**The Problem:** Wikidata's "unique value" constraint on these properties is frequently violated:
- Multiple Wikidata QIDs share the same P5063 (ILI)
- Multiple Wikidata QIDs share the same P8814 (synset ID)

These violations can be caused by:
1. Multiple WordNet sources (OEWN + OENN) mapping to different QIDs
2. Wikidata imports from different versions
3. Manual additions without checking existing statements
4. Legitimate cases (polysemy, synonyms) that appear as violations

---

## 🏢 Architecture Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MISSION CONTROL DASHBOARD                       │
│                  (comprehensive_dashboard.html)                        │
└─────────────────────────────────────────────────────────────────────┘
                                       ▲
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
          ▼                            ▼                            ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   DATA COLLECTION    │  │   ANALYSIS PIPELINE  │  │    FIX PROPOSAL      │
│                      │  │                      │  │                      │
│ • SPARQL Queries     │  │ • Categorization     │  │ • QuickStatements    │
│ • YAML Extraction     │  │ • Similarity Matching│  │ • Wikidata Bulk Edit│
│ • CSV Processing      │  │ • Drift Detection    │  │ • Progress Tracking │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
          ▲                            ▲                            ▲
          │                            │                            │
          └────────────────────────────┼────────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA STORAGE                                    │
│                  (data/output/20260929/)                               │
│                                                                      │
│  • Raw:         *from_wd.csv                                        │
│  • Enhanced:    *enhanced.csv                                       │
│  • Categorized: *categorized.csv                                     │
│  • Final:       *final.csv                                          │
│  • QuickStats:  quickstatements/*.txt                               │
│  • Manual:      manual_review/*.csv                                  │
│  • Comparison:  comparison_table.csv (future)                       │
└─────────────────────────────────────────────────────────────────────┘
                                       ▲
                                       │
┌─────────────────────────────────────────────────────────────────────┐
│                      SOURCE REPOSITORIES                               │
│                                                                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │  OEWN           │    │  OENN           │    │  Wikidata       │  │
│  │  english-wordnet│    │  english-namenet│    │  wikidata.org   │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Component Details

### 1. Data Collection Layer

**Purpose:** Gather all relevant data from source repositories and Wikidata.

#### Input Sources

| Source | Type | Description | Frequency |
|--------|------|-------------|-----------|
| OEWN YAML | Local Files | WordNet synset → QID mappings | Static |
| OENN YAML | Local Files | Name synset → QID mappings | Static |
| Wikidata SPARQL | API | All P5063/P8814 statements | On-demand |
| Wikidata Dumps | Files | Full Wikidata dataset | Periodic |

#### Key Scripts

```bash
# Fetch all P8814 statements from Wikidata
python scripts/fetch_wikidata.py --property P8814 --output data/output/P8814_all.csv

# Fetch all P5063 statements from Wikidata  
python scripts/fetch_wikidata.py --property P5063 --output data/output/P5063_all.csv

# Extract mappings from OEWN/OENN YAML
python scripts/extract_yaml.py --input ~/git/english-wordnet/src/yaml --output data/output/OEWN_mappings.csv
python scripts/extract_yaml.py --input ~/git/english-namenet/data/curated --output data/output/OENN_mappings.csv
```

#### Data Flow

```
OEWN/OENN YAML → extract_yaml.py → merged_mapped.csv
Wikidata SPARQL → fetch_wikidata.py → wikidata_wordnet_links.csv
                    ↓
            build_comparison_table.py → comparison_table.csv
                    ↓
              (Identify missing mappings)
                    ↓
            backlog_to_quickstatements.py → QuickStatements for import
```

---

### 2. Analysis Pipeline

**Purpose:** Process data to identify violations, categorize them, and determine fixability.

#### Processing Stages

```
Stage 1: Raw Data
├── p8814_violations_from_wd.csv    (1,977 rows)
└── p5063_violations_from_wd.csv    (784 rows)

Stage 2: Enhanced with WordNet Data
├── p8814_violations_enhanced.csv    (1,977 rows + definitions, similarity scores)
└── p5063_violations_enhanced.csv    (784 rows + definitions, similarity scores)

Stage 3: Categorized
├── p8814_violations_categorized.csv (Categorized by type)
└── p5063_violations_categorized.csv (Categorized by type)

Stage 4: Final Classification
├── p8814_violations_final.csv      (856 real errors, 1,121 valid)
└── p5063_violations_final.csv      (147 real errors, 472 valid)
```

#### Categorization Logic

**For P8814 Violations:**

| Category | Description | Fix Needed? | Count |
|----------|-------------|-------------|-------|
| `ONE_IN_MEMBERS_DESC_MISMATCH` | QID label in synset members but description doesn't match | ✅ Yes | 584 |
| `DIFFERENT_CONCEPTS` | Multiple QIDs represent genuinely different concepts | ✅ Yes | 208 |
| `MULTIPLE_QIDS_WITH_MISMATCHES` | Multiple QIDs with various mismatches | ✅ Yes | 64 |
| `SYNONYMS_SAME_CONCEPT` | Synonyms mapping to same concept | ❌ No | 554 |
| `BOTH_IN_MEMBERS_POLYSEMY` | Legitimate polysemy | ❌ No | 392 |
| ... | ... | ... | ... |

**For P5063 Violations:**

| Category | Description | Fix Needed? | Count |
|----------|-------------|-------------|-------|
| `DISSIMILAR_QIDS` | Multiple QIDs with low similarity | ✅ Yes | 147 |
| `MULTIPLE_ILIS_POS_DIFFERENCE` | Same ILI, different parts of speech | ❌ No | 60 |
| `SIMILAR_QIDS` | Similar concepts | ❌ No | 40 |
| ... | ... | ... | ... |

#### Similarity Matching

The system computes semantic similarity between:
- Wikidata labels and synset definitions
- Wikidata descriptions and synset definitions
- Wikidata labels and synset members

**Similarity Score Range:** 0 (no match) to 10 (perfect match)

**Thresholds:**
- Score ≥ 5: Strong match → Likely valid
- Score 2-4: Medium match → Review needed
- Score ≤ 1: Weak match → Likely error

---

### 3. Fix Proposal Layer

**Purpose:** Generate actionable fixes for all real violations.

#### QuickStatements Generation

**Format:**
```
-QID|PROPERTY|value|S248|keep_qid
```

**Examples:**
```bash
# P8814: Remove duplicate synset from Q646740, keep on Q18351973
-Q646740|P8814|00058822-n|S248|Q18351973

# P5063: Remove duplicate ILI from Q4879779, keep on Q7607619
-Q4879779|P5063|i101316|S248|Q7607619
```

**Decision Logic:**

1. **For P8814:**
   - If one QID's label is in synset members → Keep that QID
   - Else, use similarity scores → Keep highest-scoring QID
   - Else, use first QID as fallback
   - Remove P8814 from all other QIDs

2. **For P5063:**
   - Compute score for each QID (label match + description match)
   - Keep QID with highest score
   - Remove P5063 from all other QIDs

#### Output Files

```
quickstatements/
├── p8814_fixes_quickstatements.txt   (440 commands)
└── p5063_fixes_quickstatements.txt   (75 commands)

manual_review/
├── p8814_manual_review.csv           (currently empty)
└── p5063_manual_review.csv           (currently empty)
```

---

### 4. Dashboard Layer

**Purpose:** Provide a unified, interactive view of the entire ecosystem.

#### Main Dashboard: `comprehensive_dashboard.html`

**Features:**

1. **Mega Statistics** - Top-level metrics at a glance
   - Total mappings scanned
   - Violations requiring fixes
   - Proposed QuickStatements
   - Valid mappings (no fix needed)

2. **Progress Overview** - Pipeline status
   - Violation detection ✅
   - Categorization ✅
   - Proposal generation ✅
   - Fix application 🔄

3. **Tab-Based Navigation**
   - **Overview** - Executive summary and progress
   - **P8814 Details** - Deep dive into P8814 violations
   - **P5063 Details** - Deep dive into P5063 violations
   - **Proposed Fixes** - All QuickStatements ready for application
   - **All Data Files** - Downloadable outputs
   - **Comparison Table** - Track ALL mappings (future)
   - **Drift Detection** - Detect changes over time (future)

4. **Interactive Tables**
   - Sortable columns
   - Filterable by category/violation type
   - Clickable links to Wikidata/WordNet/ILI
   - Color-coded by status

5. **Sample Data**
   - First 10 violations per property
   - First 10 QuickStatements per property
   - Download buttons for full datasets

#### Comparison Table Dashboard: `violations_dashboard.html`

**Purpose:** Interactive exploration of violations.

**Features:**
- Collapsible sections
- Filter controls
- Sortable tables
- Export functionality
- ToC for navigation

---

## 🎯 Drift Detection System

**Purpose:** Track changes in Wikidata mappings over time to detect:
- New violations
- Fixed violations
- Mapping drift
- Trends

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DRIFT DETECTION                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Baseline Scan (2026-11-01)                                         │
│  ├── P8814_all_20261101.csv                                         │
│  ├── P5063_all_20261101.csv                                         │
│  └── violations_20261101.csv                                        │
│                                                                     │
│  Periodic Scan (Weekly/Monthly)                                     │
│  ├── P8814_all_20261108.csv                                         │
│  ├── P5063_all_20261108.csv                                         │
│  └── violations_20261108.csv                                        │
│                                                                     │
│  Comparison Engine                                                  │
│  ├── Detect new mappings                                            │
│  ├── Detect removed mappings                                        │
│  ├── Detect new violations                                          │
│  ├── Detect fixed violations                                        │
│  └── Generate drift report                                          │
│                                                                     │
│  Dashboard Integration                                             │
│  ├── Drift Detection tab                                            │
│  ├── Visualizations                                                │
│  └── Alerts                                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Implementation Plan

**Phase 1: Baseline (Complete)**
- ✅ Run complete scan of all P8814/P5063 statements
- ✅ Analyze and categorize all violations
- ✅ Generate fix proposals

**Phase 2: Periodic Scans (Planned)**
- Set up automated weekly scans
- Store each scan with date stamp
- Compare against previous scans

**Phase 3: Drift Detection (Planned)**
- Identify changes between scans
- Classify changes by type
- Generate alerts for new violations

**Phase 4: Dashboard Integration (Planned)**
- Add Drift Detection tab
- Show change history
- Visualize trends
- Send notifications

### Change Types

| Change Type | Description | Severity | Action |
|-------------|-------------|----------|--------|
| New Violation | Duplicate P5063/P8814 added | ⚠️ High | Investigate & fix |
| Fixed Violation | Previously reported violation resolved | ✅ Good | Verify & confirm |
| Mapping Drift | QID changed its P5063/P8814 value | ⚠️ Medium | Review for correctness |
| New Mapping | QID gained a new P5063/P8814 | ℹ️ Low | Monitor |
| Removed Mapping | QID lost a P5063/P8814 | ℹ️ Low | Investigate why |

---

## 🔄 Comparison Table System

**Purpose:** Track ALL mappings between WordNet synsets/ILIs and Wikidata QIDs in a single, comprehensive table.

### Data Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                        COMPARISON TABLE                                │
├─────────────────────────────────────────────────────────────────────┤
│  Column              │ Type    │ Source           │ Description      │
├─────────────────────────────────────────────────────────────────────┤
│  synset_id           │ string  │ OEWN/OENN        │ WordNet synset ID│
│  ili                 │ string  │ OEWN/OENN        │ Interlingual Index│
│  synset_definition   │ string  │ OEWN/OENN        │ Synset definition│
│  synset_members      │ string  │ OEWN/OENN        │ Synset lemmas    │
│  synset_source       │ string  │ OEWN/OENN        │ Source repo      │
│  qid_candidate       │ string  │ OEWN/OENN        │ Proposed QID     │
│  qid_wikidata        │ string  │ Wikidata         │ Actual QID       │
│  wd_label            │ string  │ Wikidata         │ QID label        │
│  wd_description      │ string  │ Wikidata         │ QID description  │
│  p8814_present       │ bool    │ Wikidata         │ Has P8814?       │
│  p5063_present       │ bool    │ Wikidata         │ Has P5063?       │
│  match_type          │ string  │ Computed         │ Match confidence │
│  match_score         │ int     │ Computed         │ Similarity score │
│  violation_type      │ string  │ Computed         │ Violation category│
│  is_violation        │ bool    │ Computed         │ Needs fix?       │
│  fix_proposed        │ bool    │ Generated        │ Has QuickStatement│
│  fix_applied         │ bool    │ Tracked          │ Fixed on Wikidata?│
│  last_scan_date      │ date    │ Tracked          │ When last checked │
│  first_detected      │ date    │ Tracked          │ When first seen  │
│  status              │ string  │ Tracked          │ Current state    │
└─────────────────────────────────────────────────────────────────────┘
```

### Match Types

| Match Type | Score | Description |
|------------|-------|-------------|
| `EXACT` | 10 | QID matches synset exactly |
| `STRONG` | 7-9 | High similarity, label in members |
| `MEDIUM` | 4-6 | Medium similarity |
| `WEAK` | 1-3 | Low similarity |
| `NONE` | 0 | No match |

### Violation Types

| Violation Type | Description |
|----------------|-------------|
| `DUPLICATE_P8814` | Multiple QIDs with same synset |
| `DUPLICATE_P5063` | Multiple QIDs with same ILI |
| `MISSING_P8814` | Synset not mapped on Wikidata |
| `MISSING_P5063` | ILI not mapped on Wikidata |
| `MISMATCH` | Synset/ILI doesn't match QID |
| `NONE` | No violation |

### Implementation

```bash
# Build comparison table from all sources
python scripts/build_comparison_table.py \
    --oewn data/OEWN_mappings.csv \
    --oenn data/OENN_mappings.csv \
    --wikidata data/wikidata_links.csv \
    --output data/output/comparison_table.csv

# Analyze comparison table for violations
python scripts/analyze_comparison.py \
    --input data/output/comparison_table.csv \
    --output data/output/comparison_analysis.csv

# Generate fixes from comparison analysis
python scripts/generate_fixes_from_comparison.py \
    --input data/output/comparison_analysis.csv \
    --output data/output/fixes_from_comparison/
```

---

## 📊 Current Statistics (2026-11-01)

### Pipeline Outputs

| Metric | P8814 | P5063 | Total |
|--------|-------|-------|-------|
| Total Violations from Wikidata | 1,977 | 784 | 2,761 |
| Real Errors (Need Fixes) | 856 | 147 | 1,003 |
| Valid Mappings (No Fix) | 1,121 | 472 | 1,593 |
| % Real Errors | 43.3% | 18.8% | 36.3% |

### Fix Proposals

| Metric | P8814 | P5063 | Total |
|--------|-------|-------|-------|
| QuickStatements Generated | 440 | 75 | 515 |
| Manual Review Cases | 0 | 0 | 0 |
| Unique Synsets with Duplicates | 416 | 72 | 488 |

### Coverage

| Property | Mappings in Wikidata | Mappings in OEWN/OENN | Coverage |
|----------|-----------------------|------------------------|----------|
| P8814 | ~16,000+ | ~22,000+ | ~72% |
| P5063 | ~21,000+ | ~22,000+ | ~95% |

---

## 🚀 Workflow

### Core Import Pipeline

```
1. Extract:    extract_yaml.py → merged_mapped.csv
2. Fetch:     fetch_wikidata.py → wikidata_wordnet_links.csv
3. Compare:   build_comparison_table.py → comparison_table.csv
4. Identify:  Analyze comparison_table.csv for missing mappings
5. Clean:     clean_backlogs.py → cleaned backlog files
6. Transform:  backlog_to_quickstatements.py → QuickStatements
7. Validate:  check_qids.py (verify QIDs exist)
8. Import:    submit_to_quickstatements.sh (batch upload to Wikidata)
9. Verify:    verify_import.py (confirm successful import)
```

### Violation Resolution Pipeline

```
1. Fetch:    fetch_violations.py → *from_wd.csv
2. Enhance:  categorize_violations_enhanced.py → *enhanced.csv
3. Categorize: categorize_violations.py → *categorized.csv
4. Finalize: categorize_all_final.py → *final.csv (0% REVIEW)
5. Propose:  generate_proposals_v2.py → QuickStatements + manual review
6. Verify:   Manual verification of QuickStatements
7. Apply:    QuickStatements Tool → Wikidata
8. Monitor:  Drift detection for new violations
```

---

## 🛠️ Scripts Reference

### Data Collection

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `extract_yaml.py` | Extract mappings from YAML | OEWN/OENN YAML | merged_mapped.csv |
| `fetch_wikidata.py` | Fetch P8814/P5063 from Wikidata | SPARQL endpoint | wikidata_wordnet_links.csv |
| `fetch_violations.py` | Fetch constraint violations | SPARQL endpoint | *violations_from_wd.csv |

### Analysis

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `build_comparison_table.py` | Build comparison table | merged_mapped.csv, wikidata_links.csv | comparison_table.csv |
| `categorize_violations.py` | Initial categorization | *from_wd.csv | *categorized.csv |
| `categorize_violations_enhanced.py` | Enhanced with similarity | *from_wd.csv | *enhanced.csv |
| `categorize_all_final.py` | Final classification | *categorized.csv | *final.csv (0% REVIEW) |

### Fix Generation

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `generate_proposals_v2.py` | Generate QuickStatements | *final.csv | QuickStatements, manual review |
| `backlog_to_quickstatements.py` | Convert backlog to QuickStatements | backlog/*.csv | QuickStatements |

### Verification

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `check_qids.py` | Verify QIDs exist | backlog/*.csv | Validated backlog |
| `verify_import.py` | Verify import success | comparison_table.csv (old/new) | Verification report |

### Dashboard

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `generate_dashboard.py` | Generate violations dashboard | *categorized.csv, *final.csv | violations_dashboard.html |
| `generate_comprehensive_dashboard.py` | Generate mission control dashboard | All output files | comprehensive_dashboard.html |

---

## 📂 File Structure

```
Wordnet2Wikidata-Mappings/
├── README.md                              # Main documentation
├── docs/
│   ├── SYSTEM_ARCHITECTURE.md             # This file
│   ├── PROPOSALS.md                       # Fix proposals documentation
│   ├── backlog_import.md                  # Import workflow
│   ├── comparison_pipeline.md             # Comparison pipeline design
│   ├── constraint_violation_analysis.md   # Violation analysis methodology
│   └── violation_analysis_dashboard.md    # Dashboard documentation
├── scripts/
│   ├── extract_yaml.py
│   ├── fetch_wikidata.py
│   ├── fetch_violations.py
│   ├── build_comparison_table.py
│   ├── categorize_violations.py
│   ├── categorize_violations_enhanced.py
│   ├── categorize_all_final.py
│   ├── generate_proposals.py
│   ├── generate_proposals_v2.py
│   ├── generate_dashboard.py
│   ├── generate_comprehensive_dashboard.py
│   └── ...
└── data/
    └── output/
        └── 20260929/                          # Current analysis
            ├── p8814_violations_from_wd.csv
            ├── p8814_violations_enhanced.csv
            ├── p8814_violations_categorized.csv
            ├── p8814_violations_final.csv
            ├── p5063_violations_from_wd.csv
            ├── p5063_violations_enhanced.csv
            ├── p5063_violations_categorized.csv
            ├── p5063_violations_final.csv
            ├── quickstatements/
            │   ├── p8814_fixes_quickstatements.txt
            │   └── p5063_fixes_quickstatements.txt
            ├── manual_review/
            │   ├── p8814_manual_review.csv
            │   └── p5063_manual_review.csv
            ├── comprehensive_dashboard.html
            └── violations_dashboard.html
```

---

## 🎯 Future Enhancements

### Short Term (1-2 weeks)

- [ ] **Complete Comparison Table**
  - Integrate OEWN/OENN mappings with Wikidata data
  - Add match signals and confidence scores
  - Identify all missing mappings
  
- [ ] **Implement Drift Detection**
  - Create baseline scan
  - Set up periodic scanning
  - Generate drift reports
  
- [ ] **Enhance Dashboard**
  - Add comparison table view
  - Add drift detection visualization
  - Add progress tracking

### Medium Term (1-2 months)

- [ ] **Automated Scanning**
  - Set up GitHub Actions for weekly scans
  - Email notifications for new violations
  - Auto-generate fix proposals
  
- [ ] **Improved Categorization**
  - Machine learning for better classification
  - Confidence scoring for each categorization
  - Reduced manual review
  
- [ ] **Integration with Wikidata**
  - Bot approval for bulk edits
  - Direct API integration
  - Real-time monitoring

### Long Term (3-6 months)

- [ ] **Cross-Project Collaboration**
  - Integrate with other WordNet projects
  - Share violation data with GWA
  - Coordinate fixes across projects
  
- [ ] **Quality Metrics**
  - Track mapping quality over time
  - Identify problematic patterns
  - Improve source repo mappings
  
- [ ] **Advanced Analytics**
  - Trend analysis
  - Predictive modeling
  - Anomaly detection

---

## 📞 References

- [Wikidata P5063 (Interlingual Index ID)](https://www.wikidata.org/wiki/Property:P5063)
- [Wikidata P8814 (WordNet synset ID)](https://www.wikidata.org/wiki/Property:P8814)
- [Wikidata Constraint Violations](https://www.wikidata.org/wiki/Wikidata:Database_reports/Constraint_violations)
- [Global WordNet Association](https://globalwordnet.github.io/)
- [Open English WordNet (OEWN)](https://github.com/globalwordnet/english-wordnet)
- [Open English NameNet (OENN)](https://github.com/globalwordnet/english-namenet)
- [QuickStatements Tool](https://quickstatements.toolforge.org/)

---

## 📝 Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-11-01 | 1.0 | Initial system architecture documentation |
| 2026-11-01 | 1.0 | Added comprehensive dashboard description |
| 2026-11-01 | 1.0 | Added drift detection system design |
| 2026-11-01 | 1.0 | Added comparison table system design |

---

*Document maintained by WordNet2Wikidata-Mappings project*
