# Draft: post for Wikidata:WikiProject WordNet talk page

Status: draft, not posted. Edit freely; numbers are from `data/output/20261101/` and change as decisions come in.
Post it (or a shortened version) before any removal batch runs, as the plan in `docs/INTERACTIVE_PLAN.md` asks.

---

## Cleaning up duplicate WordNet mappings (P8814 / P5063): plan and request for feedback

Hello all,

I maintain a pipeline that compares the synset-to-Wikidata mappings in Open English WordNet (OEWN) and
Open English Namenet (OENN) with what Wikidata holds. After the August 2026 import I looked at the
unique-value constraint violations on [[Property:P8814|WordNet 3.1 synset ID]] and
[[Property:P5063|Interlingual Index ID]].

**What I found**
- 488 duplicate groups: 416 on P8814 (one synset ID on several items) and 72 on P5063 (one ILI on several items).
- For each group the pipeline proposes which item keeps the value, in this order of trust: a human decision,
  then what the english-wordnet / english-namenet repositories say, then whether the label is among the synset's members,
  then a similarity score. About 125 groups rest on weak evidence (no source QID and no clear winner).
- That would mean roughly 500 statement removals. **None have been made.** I will not make any before this discussion.

**What I am not going to do**
- Treat every duplicate as an error. WordNet lumps synonyms, Wikidata splits, so many duplicates are legitimate
  (for example the two items for the crested caracara). Those are marked "leave".
- Remove statements that a redirect depends on, or that point at items for defunct names, without a look.
- Remove anything where two genuinely different concepts share a synset (for example cholestasis and acholia).
  Those are better fixed by splitting the synset on the WordNet side, and I would open that PR instead.

**What I would like from you**
1. Is this approach acceptable for the group types above? Anything I should treat differently?
2. Would you review groups? I am setting up a small review tool (Wikimedia login, invited reviewers only;
   it never edits Wikidata). A group counts as settled when two reviewers agree. For now a shared spreadsheet does the same job.
3. Before the full run I plan a **test batch of 5 to 10 removals** (cases where the source repositories are silent and both
   statements pre-date my import), then a re-check of the constraint report. Objections to that order?

**Where things are**
- Dashboard (all groups, evidence, proposed fixes): https://yapy28.github.io/Wordnet2Wikidata-Mappings/
- Code and notes: https://github.com/Yapy28/Wordnet2Wikidata-Mappings

Removals will be run with QuickStatements from my account, in small batches, with a link to the batch in the edit summary.

Thanks, and corrections are very welcome.
