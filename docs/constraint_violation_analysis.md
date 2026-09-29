# P5063 and P8814 Constraint Violation Analysis

**Date:** 2026-09-29  
**Status:** Analysis in progress  
**Author:** Yapy28

## Overview

This document describes the analysis of Wikidata constraint violations for properties P5063 (Interlingual Index ID) and P8814 (WordNet synset ID), which are used to link WordNet synsets to Wikidata entities.

Constraint violations occur when Wikidata's data integrity rules are broken. For single-value properties like P5063 and unique-value properties like P8814, violations indicate duplicate mappings that need investigation.

## Background

### Properties

- **P5063**: Interlingual Index (ILI) - A single-value property linking a Wikidata entity to a concept in the Global WordNet Association's Collaborative Interlingual Index
- **P8814**: WordNet 3.1 Synset ID - A unique-value property linking a Wikidata entity to a WordNet synset

### Constraint Types

| Property | Constraint | Meaning | Violation Type |
|----------|------------|---------|----------------|
| P5063 | Single value | Each Wikidata item should have at most one ILI | Item has multiple ILIs |
| P5063 | Unique value | Each ILI should map to only one Wikidata item | ILI maps to multiple items |
| P8814 | Unique value | Each synset ID should map to only one Wikidata item | Synset maps to multiple items |

## Problem Statement

The [Wikidata constraint report for P5063](https://www.wikidata.org/wiki/Wikidata:Database_reports/Constraint_violations/P5063) showed:
- **17 single-value violations**: Wikidata items with multiple ILI values
- **178 unique-value violations**: ILI values used on multiple Wikidata items

Additionally, a review of P8814 revealed **2,146 violations** (synsets with multiple QIDs).

## Initial Approach (Discarded)

Initially, we attempted to parse static markdown files (`P5063violations.md`, `P8814violations.md`) from the Wikidata constraint report page. This approach was abandoned because:

1. **Static data**: Markdown files don't update automatically
2. **Parsing complexity**: Requires fragile regex patterns
3. **Maintenance burden**: Files must be manually downloaded and updated

**Obsolete files created and later deleted:**
- `scripts/analyze_p5063_violations.py`
- `scripts/build_violation_tables.py`
- `scripts/simple_p5063_analysis.py`
- `scripts/build_violation_tables_v2.py`
- `data/output/p5063_violations.csv`
- `data/output/p5063_violations_with_labels.csv`
- `data/output/p8814_violations.csv`
- `P5063violations.md`
- `P8814violations.md`
- `missingILIs.csv`

## Current Approach: Direct SPARQL Queries

We created `scripts/fetch_violations.py` which queries Wikidata SPARQL endpoint directly to retrieve live violation data. This approach:

- **Always current**: Data is fresh from Wikidata
- **Automated**: Can be re-run anytime
- **Structured**: Returns proper JSON that's easy to process
- **Joins with sources**: Cross-references with OEWN/OENN YAML to get synset definitions, members, and metadata

### SPARQL Queries Used

#### P5063 Single-Value Violations
Finds Wikidata items with multiple P5063 (ILI) statements:
```sparql
SELECT ?entity ?entityLabel ?ili1 ?ili2 WHERE {
  ?entity wdt:P5063 ?ili1 .
  ?entity wdt:P5063 ?ili2 .
  FILTER(?ili1 != ?ili2)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

#### P5063 Unique-Value Violations
Finds ILIs used on multiple Wikidata items:
```sparql
SELECT ?ili ?entity1 ?entity1Label ?entity2 ?entity2Label WHERE {
  ?entity1 wdt:P5063 ?ili .
  ?entity2 wdt:P5063 ?ili .
  FILTER(?entity1 != ?entity2)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

#### P8814 Violations
Finds synsets with multiple Wikidata items:
```sparql
SELECT ?ssid ?entity ?entityLabel WHERE {
  ?entity1 wdt:P8814 ?ssid .
  ?entity2 wdt:P8814 ?ssid .
  FILTER(?entity1 != ?entity2)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

## Results

### P5063 Violations (784 rows)

**File:** `data/output/20260929/p5063_violations_from_wd.csv`

**Columns:**
- `ili`: Interlingual Index ID
- `qid`: Wikidata entity ID
- `wikidata_label`: English label of the Wikidata entity
- `synset_id`: WordNet synset ID (from OEWN/OENN)
- `synset_definition`: Definition from OEWN/OENN
- `synset_members`: Lemma/members from OEWN/OENN
- `synset_ili`: ILI from OEWN/OENN (should match the violation ILI)
- `synset_source`: OEWN or OENN
- `synset_wikidata_qids`: QIDs associated with this synset in source
- `violation_type`: single_value or unique_value

**Key Findings:**

Many "violations" are actually **valid mappings** representing different perspectives on the same concept:

1. **Same entity, different names:**
   - Q9219 (United States Military Academy) has both i81219 (OEWN: "school for training officers") and i84577 (OENN: "West Point")
   - Both describe the same real-world entity

2. **Same concept, different parts of speech:**
   - Q320553 (cut) has both i37954 (noun: "division of cards") and i29506 (verb: "divide cards")
   - Different grammatical categories for the same concept

3. **Same concept, different senses:**
   - Many cases where multiple valid synsets describe facets of the same Wikidata entity

**True Errors (to be identified):**
- Duplicate ILIs added by mistake
- Stale mappings where Wikidata items have changed
- Incorrect ILI assignments

### P8814 Violations (2,146 rows)

**File:** `data/output/20260929/p8814_violations_from_wd.csv`

**Columns:** Similar structure to P5063, with synset information joined.

**Key Findings:**

Synsets mapping to multiple Wikidata items often indicate:
- **Synonyms that are distinct entities**: e.g., "abstraction" maps to multiple philosophical concepts
- **Polysemy**: Single word with multiple meanings
- **Mapping errors**: Incorrect QID assignments

### Missing ILIs Backlog

**File:** `data/output/20260929/missing_ilis.csv`

**Source:** Synsets from OEWN/OENN that have Wikidata QIDs but **no ILI value** assigned.

**Count:** 100+ entries

**Issue:** These synsets cannot be properly linked to the Global WordNet ILI system. They need ILI assignments from the Global WordNet Association.

**Example entries:**
- 90002371-n (waterboarding) → Q2552748
- 90015801-n (paywall) → Q910845
- 92461089-n (quantum computer) → Q176555
- 88898629-n (Chinese Communist Revolution) → Q32993

## Analysis Methodology

### Data Pipeline

```
1. Query Wikidata SPARQL for violations
   └── scripts/fetch_violations.py

2. Build lookup tables from OEWN/OENN
   ├── ili → synsets
   ├── qid → synsets
   └── synset_id → synset info

3. Join violation data with source data
   └── Enrich with definitions, members, source

4. Output CSV tables
   ├── p5063_violations_from_wd.csv
   └── p8814_violations_from_wd.csv
```

### Matching Logic

For each violation, we:
1. Extract the QID/ILI/synset_id from Wikidata
2. Look up the synset in OEWN/OENN by ILI or QID
3. Add source definition, members, and metadata
4. Mark whether the synset has a wikidata field matching the QID

This allows us to see **which violations are from source mappings** vs **which are manual additions** to Wikidata.

## Next Steps

### Immediate Actions

1. **Review P5063 single-value violations** (17 cases from original report)
   - Identify which are valid (different names/senses for same entity)
   - Identify which are errors (duplicate ILIs that shouldn't coexist)
   - Create removal QuickStatements for errors

2. **Review P5063 unique-value violations** (178 cases)
   - Identify ILIs that legitimately map to multiple entities (e.g., historical names)
   - Identify mapping errors
   - Create correction QuickStatements

3. **Review P8814 violations** (2,146 cases)
   - Identify which represent valid polysemy
   - Identify which are mapping errors
   - Create correction QuickStatements

4. **Process missing ILIs**
   - Submit to Global WordNet for ILI assignment
   - Or identify if they should be excluded from mapping

### Workflow

```
For each violation:
    1. Check if both sides (QID ↔ synset) have matching definitions
    2. Check if they share hypernyms/taxonomy
    3. Check if one is a redirect of the other in Wikidata
    4. Check if one is deprecated/obsolete
    5. Decide: KEEP BOTH, REMOVE ONE, or NEEDS REVIEW
    
For true errors:
    6. Generate QuickStatements removal commands
    7. Submit to Wikidata via QuickStatements batch
    8. Verify removal was successful
```

### Decision Criteria

**Keep both mappings if:**
- Different parts of speech (noun vs verb)
- Different senses of the same word
- Synonyms that are distinct entities
- Same concept with different names (West Point = United States Military Academy)

**Remove one mapping if:**
- Duplicate entry (same synset-ILI-QID combination)
- Stale/outdated mapping
- Incorrect ILI assignment
- Wikidata redirect (old QID pointing to new one)

## Files Generated

| File | Location | Rows | Description |
|------|---------|------|-------------|
| p5063_violations_from_wd.csv | data/output/20260929/ | 784 | All P5063 violations with synset info |
| p8814_violations_from_wd.csv | data/output/20260929/ | 2,146 | All P8814 violations with synset info |
| missing_ilis.csv | data/output/20260929/ | 100+ | Synsets with QIDs but no ILIs |

## Scripts Used

| Script | Purpose |
|--------|---------|
| `scripts/fetch_violations.py` | Queries Wikidata SPARQL for live violation data, joins with OEWN/OENN |

## References

- [Wikidata Constraint Reports](https://www.wikidata.org/wiki/Wikidata:Database_reports/Constraint_violations)
- [Property:P5063](https://www.wikidata.org/wiki/Property:P5063) - Interlingual Index ID
- [Property:P8814](https://www.wikidata.org/wiki/Property:P8814) - WordNet 3.1 Synset ID
- [Global WordNet Association](https://globalwordnet.github.io/) - ILI authority

## Changelog

| Date | Action | Details |
|------|--------|---------|
| 2026-09-29 | Initial violation analysis | Created fetch_violations.py, generated comparison tables |
| 2026-09-29 | Cleanup | Removed obsolete markdown parsers, organized output |
| 2026-09-29 | Documentation | Created this document |
