# Plan: interactive review in the Wikidata ecosystem

Status: proposal (2026-11-12). Today collaborators review in a Google Sheet (`review_sheet.xlsx`); the dashboard is read-only.

## Decisions made
- **Reviewers**: only people with WordNet and Wikidata experience (invited, not open to anyone).
- **Edits**: the tool never edits Wikidata. It exports QuickStatements that the maintainer or another person runs.

## Why not "inside Wikidata"
Wikidata does not run third-party code. What the ecosystem offers instead: the edit API with OAuth login,
Toolforge (free Wikimedia cloud hosting, includes a database), and on-wiki pages for scripts and JSON.
Starting points: oauth-hello-world.toolforge.org, the Toolforge "My first Flask OAuth tool" tutorial,
the `mwoauth2` library. The host `minitechnicus.eu` (static Astro site on Cloudflare) has no backend and
can at most serve the static dashboard.

## Phases
0. **Now**: Google Sheet. Pipeline: `export_review_sheet.py` -> sheet -> `import_decisions.py` -> `run_pipeline.py --from proposals`.
1. **Toolforge review app**
   - Login with a Wikimedia account, restricted to an allowlist of invited reviewers (no abuse handling needed).
   - The Review queue becomes live: definition, members, items, source evidence, keep / leave / defer + note.
   - Decisions stored with username and timestamp; a group is accepted when two reviewers agree.
   - Replaces the xlsx round trip and `import_decisions.py`. The pipeline in this repo keeps producing the groups.
2. **QuickStatements export**
   - "Export accepted removals" button: V1 commands in the valid format `-QID|P8814|"value"` (quoted, no source).
   - The maintainer runs a 5-10 removal test batch first, then the rest.
   - After a run, the tool (or `fetch_violations.py`) re-checks Wikidata and marks groups as applied (`fix_applied` is `FALSE` everywhere today).
3. **Use Wikidata's own mechanisms where they fit**
   - Valid duplicates: the qualifier `exception to constraint` (P2303) on the property's unique-value constraint. Known limits: stored on the property page, does not scale well, not tracked in item history. Fine for a few dozen items, not for 488 groups.
   - Wikidata Distributed Game (yes/no tiles, sub-games added as JSON) for easy cases. API docs not yet read; code reportedly moved to Codeberg.
   - Optional user script on item pages: "this item shares P8814 with Q...", keep / leave links.

## To verify before building
- Toolforge access: current signup steps for a developer account.
- OAuth grants needed, and whether the app needs to edit at all (it does not, with QuickStatements exports).
- Whether non-admins can edit a property's constraint statement (for P2303).
- Community expectation for ~500 removals: raise it on Wikidata:WikiProject WordNet before the first batch.
