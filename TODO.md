# TODO

## Now
Updated 2026-11-01. Current priorities for WordNet2Wikidata constraint violation analysis and mapping management.

| Priority | Work | Status | Next Step |
|---|---|---|---|
| P1 | Review and apply QuickStatements fixes | Ready | Manually review proposed fixes in comprehensive dashboard, then apply via QuickStatements |
| P1 | Verify fixes on Wikidata | Pending | After applying fixes, re-run fetch_violations.py to confirm violations resolved |
| P2 | Set up drift detection baseline | Pending | Run full scan and save baseline state for future comparison |
| P2 | Schedule periodic re-scans | Pending | Automate weekly/monthly violation scans |
| P3 | Manual review of edge cases | Pending | Review MULTIPLE_ILIS_POS_DIFFERENCE and MULTIPLE_QIDS_WITH_MISMATCHES categories |
| P3 | Propose new ILIs for missing mappings | Pending | Review missingILIs.csv and prepare proposals for GWA |

## Backlog

- **Google Sheets integration**: Connect comparison table to Google Sheets for easier manual review (user requested this)
- **Enhanced similarity matching**: Improve confidence scoring with better semantic similarity metrics
- **Automated fix application**: Build script to automatically apply QuickStatements fixes (with manual approval gate)
- **Cross-repo synchronization**: Sync fixes across english-wordnet, english-namenet, and wikidata
- **Dashboard improvements**: Add filters, search, and better visualization to comprehensive dashboard
- **Missing ILIs**: Review and propose new ILIs from missingILIs.csv (80+ entries identified)

## Detail

### Current State (2026-11-01)

**Constraint Violation Analysis:**
- P8814 violations: 1,977 total, 856 real violations identified
- P5063 violations: 784 total, 312 real violations identified
- QuickStatements generated: 515 total (440 P8814 + 75 P5063)
- Comparison table: 2,354 rows with fix tracking
- Comprehensive dashboard: 6 tabs with all data

**Files Generated:**
- `data/output/20260929/p8814_violations_final.csv` - Final P8814 violations with categorization
- `data/output/20260929/p5063_violations_final.csv` - Final P5063 violations with categorization
- `data/output/20260929/full_comparison_table.csv` - Complete comparison with 2,354 rows
- `data/output/20260929/comprehensive_dashboard.html` - Interactive HTML dashboard
- `data/output/20260929/quickstatements/p8814_fixes_quickstatements.txt` - 440 QuickStatements
- `data/output/20260929/quickstatements/p5063_fixes_quickstatements.txt` - 75 QuickStatements

**Category Breakdown:**
- ONE_IN_MEMBERS_DESC_MISMATCH: QID in members but definition doesn't match → **One QID in members, definition mismatch**
- BOTH_IN_MEMBERS: Both QIDs found in synset members → **Both QIDs in synset members**
- DIFFERENT_CONCEPTS: QIDs represent different concepts → **Different concepts**
- MULTIPLE_ILIS_POS_DIFFERENCE: Same ILI on multiple QIDs with different POS → **Multiple ILIs, different POS**
- DISSIMILAR_QIDS: QIDs with low similarity → **Dissimilar QIDs**

### Next Actions

1. **Review proposed fixes** (P1): Open `comprehensive_dashboard.html`, go to Comparison tab, review rows with "FIX_PROPOSED" status
2. **Apply fixes** (P1): Use QuickStatements files to apply fixes to Wikidata
3. **Verify** (P1): Re-run `fetch_violations.py` to confirm fixes worked
4. **Baseline for drift** (P2): Save current state as baseline for future drift detection
5. **Schedule scans** (P2): Set up cron or GitHub Actions for periodic re-scans

### Open Questions

- Should we automatically apply fixes or always require manual review?
- How often should we re-scan for new violations? (Weekly? Monthly?)
- Should we track which fixes have been applied vs just proposed?
- Do we need to sync with english-wordnet and english-namenet repos, or are all fixes Wikidata-side?

### References

- System architecture: See `docs/SYSTEM_ARCHITECTURE.md`
- Constraint violation methodology: See `docs/constraint_violation_analysis.md`
- Previous work: See `DONE.md`
- Detailed findings: See `FINDINGS.md`
