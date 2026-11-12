# FINDINGS

Findings with evidence links: `### Finding YYYY-MM-DD: title`.

Started 2026-11-01. Open work: `TODO.md`; finished: `DONE.md`.

### Finding 2026-11-01: QuickStatements parsing bug fixed

- **Issue**: `build_full_comparison.py` was incorrectly parsing QuickStatements, using property name (P8814/P5063) as the key instead of synset_id/ili
- **Impact**: Comparison table showed 0 fixes proposed even though 515 QuickStatements were generated
- **Root cause**: In QuickStatement format `-Q646740|P8814|00058822-n|S248|Q18351973`, the code was using parts[1] (P8814) as synset_id instead of parts[2] (00058822-n)
- **Fix**: Updated indexing to use correct positions: synset_id = parts[2], ili = parts[2] for P5063
- **Verification**: Comparison table now correctly shows 515 fixes proposed (440 P8814 + 75 P5063)
- **Files**: `scripts/build_full_comparison.py`

### Finding 2026-11-01: Dashboard overlay issue

- **Issue**: Tab content appeared overlaid/crowded
- **Root cause**: Missing padding on tab-content divs and sections
- **Fix**: Added `.tab-content { padding: 0; }` and `.tab-content.active { padding: 20px 0; }` to CSS
- **Impact**: Dashboard now displays properly with proper spacing between sections
- **Files**: `scripts/generate_comprehensive_dashboard.py`

### Finding 2026-11-01: Unnatural category names

- **Issue**: Category names like `ONE_IN_MEMBERS_DESC_MISMATCH` are hard to read and understand
- **Impact**: Difficult for manual reviewers to understand what each category means
- **Fix**: Created `CATEGORY_LABELS` mapping with human-readable names:
  - `ONE_IN_MEMBERS_DESC_MISMATCH` → One QID in members, definition mismatch
  - `BOTH_IN_MEMBERS` → Both QIDs in synset members
  - `DIFFERENT_CONCEPTS` → Different concepts
  - `MULTIPLE_ILIS_POS_DIFFERENCE` → Multiple ILIs, different POS
  - `DISSIMILAR_QIDS` → Dissimilar QIDs
  - And all other categories
- **Files**: `scripts/build_full_comparison.py`
- **Result**: Comparison table now shows both human-readable category and original category_raw

### Finding 2026-09-29: Constraint violation categories

- **P8814 Categories** (8 total):
  1. **BOTH_IN_MEMBERS**: Both QIDs found in synset members - valid duplicate (1,121 cases)
  2. **ONE_IN_MEMBERS_DESC_MISMATCH**: One QID in members but definition mismatch - needs fix (many cases)
  3. **ONE_IN_MEMBERS_MEDIUM_SIM**: One QID in members with medium similarity - needs review
  4. **DIFFERENT_CONCEPTS**: QIDs represent fundamentally different concepts - needs fix
  5. **MULTIPLE_QIDS_ALL_IN_MEMBERS**: Multiple QIDs all in synset members - valid
  6. **MULTIPLE_QIDS_MIXED**: Multiple QIDs with mixed matches - needs review
  7. **MULTIPLE_QIDS_WITH_MISMATCHES**: Multiple QIDs with definition mismatches - needs fix
  8. **NEITHER_IN_MEMBERS_BUT_SIMILAR**: Neither QID in members but definitions similar - needs review

- **P5063 Categories** (6 total):
  1. **MULTIPLE_ILIS_POS_DIFFERENCE**: Same ILI on multiple QIDs with different POS - valid (17 cases from Wikidata report)
  2. **MULTIPLE_ILIS_HIGH_SIM**: Multiple ILIs with high similarity - needs review
  3. **DISSIMILAR_QIDS**: QIDs with low similarity scores - needs fix (312 cases)
  4. **SIMILAR_QIDS**: QIDs with high similarity - likely valid
  5. **MEDIUM_SIMILAR_QIDS**: QIDs with medium similarity - needs review
  6. **DUPLICATE_LABELS**: QIDs with duplicate labels - needs fix

- **Key insight**: 0% REVIEW rate achieved - all violations automatically categorized
- **Files**: `data/output/20260929/p8814_violations_final.csv`, `data/output/20260929/p5063_violations_final.csv`

### Finding 2026-09-29: Wikidata constraint violations source

- **Data source**: SPARQL queries against Wikidata for P5063 (ILI) and P8814 (synset ID) constraint violations
- **Query approach**: Uses `?p5063 wdt:P5063 ?ili` and `?p8814 wdt:P8814 ?synset_id` patterns
- **Total violations found**:
  - P8814: 1,977 violations (from SPARQL)
  - P5063: 784 violations (from SPARQL)
- **Wikidata report**: P5063 has 178 "unique value" violations and 17 "single value" violations as of 2026-09-03
- **Note**: Wikidata reports may include false positives that don't need fixing
- **Files**: `scripts/fetch_violations.py`

### Finding 2026-09-29: QuickStatements fix generation

- **Format**: `-QID|PXX|value|S248|keep_qid` for removal commands
- **P8814**: Remove duplicate synset_id from QID, keep on canonical QID
- **P5063**: Remove duplicate ILI from QID, keep on canonical QID
- **Total generated**:
  - P8814: 440 QuickStatements
  - P5063: 75 QuickStatements
- **Strategy**: For each violation group, determine "best QID" based on:
  1. Similarity scores from notes
  2. QID label in synset members
  3. Definition matching
- **Files**: `scripts/generate_proposals_v2.py`

### Finding 2026-09-29: English-wordnet QID updates

- **Updates made**: 7 QIDs that redirect to new IDs
  - noun.communication.yaml: Q57982892 → Q19877481 (06931708-n)
  - noun.person.yaml: Q2101433 → Q1685165 (09828217-n)
  - noun.person.yaml: Q10384150 → Q9304839 (10745683-n)
  - noun.state.yaml: Q6901506 → Q1313618 (14268208-n)
  - noun.artifact.yaml: Q67183571 → Q25635419 (04420036-n)
  - noun.artifact.yaml: Q17087190 → Q3771516 (04552265-n)
  - noun.animal.yaml: Removed duplicate Q40658797 (01563434-n)
- **Status**: Committed and pushed to fork, ready for PR to upstream
- **Files**: english-wordnet repo PR

### Finding 2026-09-29: System architecture decisions

- **Decision**: All fixes are Wikidata-side, not source repos
  - Rationale: Source repos (english-wordnet, english-namenet) are authoritative
  - Wikidata mappings should sync to source, not vice versa
- **Decision**: Maintain violation data + QuickStatements + comparison table in one ecosystem
  - Rationale: Simplifies tracking and ensures consistency
- **Decision**: Use tab-based navigation for dashboard
  - Rationale: Broken scroll-based ToC was unusable
- **Files**: `docs/SYSTEM_ARCHITECTURE.md`

### Finding 2026-09-29: Comparison table design

- **Purpose**: Track ALL mappings between WordNet synsets/ILIs and Wikidata QIDs
- **Scope**: Currently includes violations + proposed fixes (2,354 rows)
- **Future**: Should expand to include ALL mappings for drift detection
- **Columns**: entity_type, qid, wd_label, wd_description, synset_id, synset_definition, synset_members, synset_source, ili, category, category_raw, is_violation, violation_type, has_fix_proposed, fix_qid, fix_applied, confidence_score, status
- **Links**: All QIDs, ILIs, and synsets now have clickable links to external resources
- **Files**: `scripts/build_full_comparison.py`, `data/output/20260929/full_comparison_table.csv`
