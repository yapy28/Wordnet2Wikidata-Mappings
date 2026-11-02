# Workflow: lineage, status, to-do

Last updated: 2026-11-01. Everything here is derived from the repo, the two source repos
(`english-wordnet`, `english-namenet`) and the session notes. Items marked **(confirm)** are
things the repo cannot show and need the maintainer's input.

## 1. Lineage

| Stage | When | What happened | Evidence |
|---|---|---|---|
| 1. Review existing mappings | before 2026-08-16 | Extract OEWN/OENN synsets with a QID, compare with Wikidata's P8814/P5063 (22,670 candidate pairs, 70.95% already on Wikidata). Backlog worked through manually in Google Sheets, cleaned, converted to QuickStatements. | `docs/comparison_pipeline.md`, `data/backlogs/`, `data/output/20260701/` |
| 1b. Import | 2026-08-16 | Three QuickStatements batches: 11,402 statements done, 20 errors (404 item missing, 409 item redirected). Match rate after: 96.01%. | `data/output/20260816/batch-*-report.csv` |
| 2. Changes to WordNet / Namenet / CILI | Aug-Sep 2026 | PRs to the source repos and CILI **(confirm: which PRs, which are merged)**. Known: a QID-redirect sync commit in each source repo on 2026-09-29. Neither commit is in upstream `main` yet. | `english-wordnet` `affb746`, `english-namenet` `24490a6` (fork branches only) |
| 3. Violation analysis | 2026-09-29 | Fetch P5063/P8814 unique-value violations from Wikidata SPARQL; classify as real error vs valid duplicate (three passes). | `scripts/fetch_violations.py`, `categorize_*.py`, `*_violations_final.csv` |
| 4. Proposals + dashboard | 2026-11-01 | Removal proposals, comparison table, single dashboard, source cross-check, tests. | this commit set |

## 2. The pipeline today

```bash
# violation analysis (data/output/20260929/)
python scripts/fetch_violations.py
python scripts/categorize_violations.py && python scripts/categorize_violations_enhanced.py && python scripts/categorize_all_final.py
python scripts/crosscheck_sources.py          # what english-wordnet / english-namenet say for each duplicate group
python scripts/generate_proposals_v2.py       # keep/remove proposals + keep_decisions.csv (source repos win)
python scripts/build_full_comparison.py       # legacy export
python scripts/generate_dashboard.py          # violations_dashboard.html
python3 -m unittest discover -s tests -t .    # consistency checks
```

Keep decision priority: **human decisions > source repos > label in synset members > similarity score > fallback**.
`keep_decisions.csv` records the reason for every group; `tie` and `fallback` are "weak" and go to the review queue.
Human decisions live in `manual_review/decisions.csv` (section 5) — the review tab of the dashboard
lets you record them interactively and export the file.

## 3. Done

- Import of the backlog to Wikidata (Aug 2026) and verification (`verify_import.py`).
- Violations fetched, classified, and reconciled: 2,354 statements = 1,351 valid + 488 keep + 515 remove (P5063 counted per unique QID/ILI pair).
- Import vs violations: 84% of flagged statements were already on Wikidata before our import; 158 involve a statement our import asserted.
- One dashboard (replaces two): full searchable tables, Wikidata vs WordNet columns, names instead of codes, verified links, dark mode, sticky tabs, review queue, fixes with copyable QuickStatements.
- Source cross-check: 192 of 416 P8814 groups are confirmed by the source repos; 52 removal lines that contradicted the source were flipped; 44 of 72 P5063 keeps found to be ties/no evidence.
- 27 unit/consistency tests (`tests/`).
- Docs and README brought in line; dead links fixed.

## 4. To do

### Before any removal is run on Wikidata
1. **Review the weak decisions** (review queue tab): P8814 groups where no QID matches the synset and the source has no QID (80), and P5063 ties (44).
2. **57 P5063 ILIs**: the source repos map the ILI to *both* QIDs. Decide per case: valid duplicate, or a source-side fix by PR (stage 2 type work).
3. **7 P8814 synsets** where the source names a QID that is not one of the duplicated Wikidata items: that QID may be missing the statement.
4. **Fix the QuickStatements format**: removals must be `-QID|P8814|"value"` (quoted, no `S248` source). The dashboard's Fixes tab already shows the correct lines; the generator still writes the old format.
5. **Test batch**: run 5-10 removals where the source repos are silent and both statements pre-date our import; check on Wikidata.
6. **decisions.csv**: done — implemented (section 5). New contributors start in the dashboard's
   **Review queue** tab: record keep/leave/defer per group, export, commit — or edit the
   downloadable template in Google Sheets.

### Later
- **CI/CD (proposed)**: contributors work only through `decisions.csv` (or the dashboard's review
  tab export); a GitHub Actions workflow then re-runs the pipeline
  (`generate_proposals_v2.py`, `generate_dashboard.py`, tests) and commits the regenerated
  outputs, so GitHub Pages always serves the current dashboard. Prerequisites: one `--run-dir`
  parameter for all scripts, and no absolute paths. The heavy steps (SPARQL fetch, source
  cross-check) can stay manual and out of CI.
- Closing loop: re-fetch violations after fixes, log what was applied and when (`fix_applied` is currently `FALSE` everywhere).
- Hygiene: one `--run-dir` parameter for all scripts (paths are hardcoded to `20260929`), retire `categorize_violations.py` / `generate_proposals.py` (v1), rename the run folder (data was fetched 2026-11-01), drop the legacy `full_comparison_table.csv` (it labels keepers `NEEDS_FIX`).
- Stage 2 record: write down which PRs went to WordNet / Namenet / CILI and their state **(confirm)**. Check whether the 2026-09-29 QID-sync commits should be PR'd.
- 127 synsets with a QID but no ILI (`missing_ilis_verified.csv`): needs CILI work.
- Add new mappings (see section 6).

## 5. `manual_review/decisions.csv` (implemented)

One row per **duplicate group** (so a group cannot be half-decided):

```csv
prop,value,action,keep_qid,note
P8814,01445613-n,keep,Q214278,source names it
P5063,i107547,leave,,both valid per source
P8814,00123481-n,defer,,ask on talk page
```

| Column | Meaning |
|---|---|
| `prop`, `value` | `P8814` + synset id, or `P5063` + ILI. Must match a real duplicate group. |
| `action` | `keep`: keep `keep_qid`, remove it from every other QID in the group. `leave`: no removals, group treated as valid. `defer`: no removals yet, stays in the review queue. Empty = undecided template row, ignored. |
| `keep_qid` | Required for `keep`; must be one of the group's QIDs. |
| `note` | Free text, shown in the dashboard. |

Rules: decisions beat the source pick, which beats the heuristics (reason `decision` /
`decision_leave` / `defer`); an unknown group or a `keep_qid` outside the group is an error,
not silently ignored; the file is optional and only lists groups you decided.

Workflow: the dashboard's **Review queue** tab records decisions in the browser
(keep QID / leave group / defer + note), exports `decisions.csv`; or download the template
(all review groups, pre-filled with the current proposal) and edit it in Google Sheets.
Save the result to `manual_review/decisions.csv`, re-run `generate_proposals_v2.py` and
`generate_dashboard.py`. The first three decisions came out of the presentation
(2026-11-02): caracara (deliberate synonym pair), the Portuguese man-of-war redirect
(we keep redirects), and cholestasis/acholia (two different conditions).

### Review guidance (from the presentation, 2026-11-02)

- **WordNet is a lumper, Wikidata is a splitter.** Synsets deliberately group synonyms;
  a duplicate on Wikidata is often a legitimate synonym pair, not a mapping error. When in
  doubt, `leave`.
- **Wikidata contains items for defunct names** — WordNet picked some up. Statements
  pointing at defunct/old items are not automatically wrong.
- **Redirects are kept** (e.g. Q272388 → Q202526): removals must never target the statement
  the redirect depends on.
- **New Wikidata IDs are taken with a grain of salt** — prefer established items as keeps.
- **Genuinely different concepts** (e.g. cholestasis Q1075923 vs acholia Q8187550): keep both
  statements and propose a WordNet-side **synset split** instead of removing anything.
- **Hedgehog vs porcupine**: separate concepts; if a source synset lumps them, propose a split
  in the source repo (not currently a violation group).

## 6. Adding new mappings (after the clean-up)

Only nouns carry QIDs in the source repos: 13,301 OEWN nouns linked vs 58,571 unlinked (OENN: 12,700 vs 345);
no adjective, verb or adverb synset has one. Most unlinked nouns are ordinary concepts without a Wikidata item,
so the hard part is **precision**, not coverage.

1. **Candidates**: unlinked noun synsets (prioritise entity-like ones: species, places, people, organisations, products).
2. **Match**: search Wikidata by lemma, then score with the same evidence used here (label in members, definition vs description, instance-of/hypernym agreement).
3. **Validate** with the shared check "would this statement create a duplicate or conflict?" (the logic behind `crosscheck_sources.py`), so we never add what we are cleaning up.
4. **Human review** of every proposed pair; auto-accept only exact label + hypernym agreement.
5. **Write both sides**: QuickStatements to Wikidata, PRs to the source repos (same loop as the stage 1 import).
6. **Verify** with a re-fetch (the closing loop above).
