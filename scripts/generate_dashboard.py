#!/usr/bin/env python3
"""
Generate the single static HTML dashboard for the P5063 / P8814 constraint-violation work.

Reads the CSV / QuickStatements outputs in data/output/<run>/ and embeds every row
(no sampling) into one self-contained HTML file with searchable, sortable, filterable
scroll-box tables, a dark mode and a sticky tab bar.

Replaces the former generate_dashboard.py (old layout) and generate_comprehensive_dashboard.py.

Usage:
    python scripts/generate_dashboard.py [data/output/<date>]

Without an argument the latest run under data/output/ that contains
p8814_violations_final.csv is rendered, so the dashboard stays current:
re-run the pipeline scripts, then re-run this one.
"""
import csv
import glob
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_proposals_v2 import WEAK_REASONS  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output" / "20261101"
IMPORT_DIR = BASE_DIR / "data" / "output" / "20260816"
DASHBOARD_PATH = OUTPUT_DIR / "violations_dashboard.html"

# Categories where neither QID matches the synset. If the source repos don't back the keep choice
# either, the decision rests on weak signals -> human review first.
REVIEW_CATEGORIES = {"DIFFERENT_CONCEPTS", "MULTIPLE_QIDS_WITH_MISMATCHES"}

CATEGORY_LABELS = {
    "ONE_IN_MEMBERS_DESC_MISMATCH": "One QID in synset members, definition mismatch",
    "DIFFERENT_CONCEPTS": "Different concepts (neither in members)",
    "MULTIPLE_QIDS_WITH_MISMATCHES": "Multiple QIDs with definition mismatches",
    "BOTH_IN_MEMBERS": "Both QIDs in synset members (polysemy)",
    "ONE_IN_MEMBERS_MEDIUM_SIM": "One QID in members, medium similarity",
    "MULTIPLE_QIDS_ALL_IN_MEMBERS": "Multiple QIDs, all in members",
    "MULTIPLE_QIDS_MIXED": "Multiple QIDs, mixed matches",
    "NEITHER_IN_MEMBERS_BUT_SIMILAR": "Neither in members but similar definitions",
    "DISSIMILAR_QIDS": "Dissimilar QIDs",
    "SIMILAR_QIDS": "Similar QIDs",
    "MEDIUM_SIMILAR_QIDS": "Medium-similar QIDs",
    "DUPLICATE_LABELS": "Duplicate labels",
    "MULTIPLE_ILIS_POS_DIFFERENCE": "Multiple ILIs, different POS",
    "MULTIPLE_ILIS_HIGH_SIM": "Multiple ILIs, high similarity",
}


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def count_lines(path):
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def load_fixes(path):
    """Parse '-QID|Pxxx|value|S248|keep' lines -> list of dicts."""
    fixes = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("-Q"):
                continue
            parts = line.split("|")
            fixes.append({"remove": parts[0][1:], "prop": parts[1], "value": parts[2], "keep": parts[4]})
    return fixes


def load_mappings():
    """The full import-pipeline comparison table: every OEWN/OENN synset with a candidate QID."""
    runs = sorted((BASE_DIR / "data" / "output").glob("*/comparison_table.csv"))
    if not runs:
        return None
    path = runs[-1]
    rows, found, strong = [], 0, 0
    for r in load_csv(path):
        j, s, i = int(r["flag_qid_join_found"]), int(r["flag_match_ssid_exact"]), int(r["flag_match_ili_exact"])
        m = max(int(r["flag_label_in_members_exact"]), int(r["flag_label_in_members_norm"]))
        d = int(r["flag_def_desc_overlap_any"])
        rows.append({
            "sid": r["synset_id"], "def": r["definition"], "ili": r["ili"],
            "mem": r["members"].replace("|", ", "),
            "q": r["qid_candidate"] or r["qid"],
            "lab": r["entity_label"], "desc": r["entity_description"],
            "src": "+".join(name for name in ("OEWN", "OENN") if r[f"in_{name.lower()}"] == "TRUE"),
            "j": j, "s": s, "i": i, "m": m, "d": d, "n": int(r["def_desc_overlap_count"]),
        })
        found += j
        strong += (s or i or m)
    return {"rows": rows, "meta": {
        "path": str(path.relative_to(BASE_DIR)),
        "date": run_date(path.parent, datetime.fromtimestamp(path.stat().st_mtime)),
        "total": len(rows), "found": found, "strong": strong}}


def run_date(dir_path, fallback):
    """Run date from the data/output/<YYYYMMDD> folder name, with an mtime fallback."""
    try:
        return datetime.strptime(dir_path.name, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return fallback.strftime("%Y-%m-%d")


def build_rows(violations, fixes, value_field, prop, crosscheck, reasons, dnotes=None):
    """Attach role (remove / keep / valid / deferred) and the QID to keep to every violation row."""
    dnotes = dnotes or {}
    remove_map = {(x["remove"], x["value"]): x["keep"] for x in fixes}
    keep_set = {(x["keep"], x["value"]) for x in fixes}
    rows = []
    for v in violations:
        real = v["is_real_violation"] == "TRUE"
        key = (v["qid"], v[value_field])
        value = v[value_field]
        reason = reasons.get((prop, value), "") if real else ""
        if not real or reason == "decision_leave":
            role, keep = "valid", ""
        elif reason == "defer":
            role, keep = "deferred", ""
        elif key in remove_map:
            role, keep = "remove", remove_map[key]
        elif key in keep_set:
            role, keep = "keep", v["qid"]
        else:
            role, keep = "unresolved", ""
        src_qids = crosscheck.get((prop, value), {}).get("source_qids", [])
        weak = role in ("remove", "keep") and (
            reason in WEAK_REASONS or (v["category"] in REVIEW_CATEGORIES and reason not in ("source", "decision")))
        rows.append({
            "q": v["qid"],
            "lab": v["wikidata_label"],
            "desc": v["wikidata_description"],
            "sid": v["synset_id"],
            "ili": v["ili"] if value_field == "ili" else v["synset_ili"],
            "sdef": v["synset_definition"],
            "mem": v["synset_members"].replace("|", ", "),
            "src": v["synset_source"],
            "cat": v["category"],
            "role": role,
            "keep": keep,
            "conf": v["confidence"],
            "notes": v.get("categorization_notes", ""),
            "rev": 1 if role == "deferred" else int(weak),
            "src": src_qids,
            "se": "none" if not src_qids else ("yes" if v["qid"] in src_qids else "other"),
            "reason": reason,
            "dnote": dnotes.get((prop, value), ""),
        })
    return rows


def main(run_dir=None):
    global OUTPUT_DIR, DASHBOARD_PATH
    if run_dir:
        OUTPUT_DIR = Path(run_dir)
    else:
        runs = sorted(p for p in (BASE_DIR / "data" / "output").glob("*")
                      if p.is_dir() and (p / "p8814_violations_final.csv").exists())
        if not runs:
            sys.exit("No data/output/*/ run with p8814_violations_final.csv found.")
        OUTPUT_DIR = runs[-1]
    DASHBOARD_PATH = OUTPUT_DIR / "violations_dashboard.html"

    p8814_raw = load_csv(OUTPUT_DIR / "p8814_violations_final.csv")
    p5063_raw = load_csv(OUTPUT_DIR / "p5063_violations_final.csv")

    # The SPARQL join returns every (QID, ILI) pair several times (once per synset/constraint row).
    seen, p5063_unique = set(), []
    types = defaultdict(set)
    for v in p5063_raw:
        types[(v["qid"], v["ili"])].add(v["violation_type"])
        if (v["qid"], v["ili"]) not in seen:
            seen.add((v["qid"], v["ili"]))
            p5063_unique.append(v)

    fix8814 = load_fixes(OUTPUT_DIR / "quickstatements" / "p8814_fixes_quickstatements.txt")
    fix5063 = load_fixes(OUTPUT_DIR / "quickstatements" / "p5063_fixes_quickstatements.txt")

    crosscheck = {}
    cc_path = OUTPUT_DIR / "source_crosscheck.csv"
    if cc_path.exists():
        for r in load_csv(cc_path):
            crosscheck[(r["prop"], r["value"])] = {"source_qids": [q for q in r["source_qids"].split("|") if q],
                                                  "status": r["status"]}
    reasons = {}
    dnotes = {}
    kd_path = OUTPUT_DIR / "keep_decisions.csv"
    if kd_path.exists():
        for r in load_csv(kd_path):
            reasons[(r["prop"], r["value"])] = r["reason"]
            dnotes[(r["prop"], r["value"])] = r.get("note", "")
    if not crosscheck or not reasons:
        print("WARNING: run crosscheck_sources.py and generate_proposals_v2.py first for source evidence.")

    rows8814 = build_rows(p8814_raw, fix8814, "synset_id", "P8814", crosscheck, reasons, dnotes)
    rows5063 = build_rows(p5063_unique, fix5063, "ili", "P5063", crosscheck, reasons, dnotes)
    for r, v in zip(rows5063, p5063_unique):
        r["vt"] = "+".join(sorted(types[(v["qid"], v["ili"])]))

    # ---- Reconciliation -------------------------------------------------------------------
    def tally(rows):
        c = Counter(r["role"] for r in rows)
        return {"total": len(rows), "valid": c["valid"], "keep": c["keep"], "remove": c["remove"],
                "unresolved": c["unresolved"], "deferred": c["deferred"]}

    s8814, s5063 = tally(rows8814), tally(rows5063)
    assert s8814["remove"] == len(fix8814) and s5063["remove"] == len(fix5063), "QuickStatements / row mismatch"
    review_rows = sum(r["rev"] for r in rows8814 + rows5063)

    manual_file = OUTPUT_DIR / "manual_review" / "p8814_manual_review.csv"
    manual_extra = None  # queue rows that the older manual_review file does not list
    if manual_file.exists():
        manual_qids = {(r["qid"], r["synset_id"]) for r in load_csv(manual_file)}
        queue = {(r["q"], r["sid"]) for r in rows8814 if r["rev"]}
        manual_extra = len(queue - manual_qids)

    missing = load_csv(OUTPUT_DIR / "missing_ilis_verified.csv")
    missing_rows = [{
        "sid": m["wn_synset"], "sdef": m["wn_definition"], "ili": m["wn_ili"], "mem": m["wn_members"].replace("|", ", "),
        "q": m["wn_wd_qid"], "oewn": m["in_oewn"], "oenn": m["in_oenn"], "has": m["has_p5063"],
        "ex": m["existing_ilis"], "status": m["status"], "qs": m["qid_statuses"],
    } for m in missing]

    batches = Counter()
    for p in sorted(glob.glob(str(IMPORT_DIR / "batch-*-report.csv"))):
        name = Path(p).name.replace("-report.csv", "")
        for r in load_csv(p):
            batches[(name, r["status"])] += 1
    batch_rows = sorted({k[0] for k in batches})
    batch_table = [{"batch": b, "done": batches[(b, "Done")], "error": batches[(b, "Error")]} for b in batch_rows]

    mapping_data = load_mappings()

    # Files (relative to the dashboard) with row counts for the Files tab.
    file_specs = [
        ("p8814_violations_final.csv", "P8814 final categorisation (source of this dashboard)"),
        ("p5063_violations_final.csv", "P5063 final categorisation (784 raw rows = 377 unique QID/ILI pairs)"),
        ("p8814_violations_from_wd.csv", "P8814 raw SPARQL violations + synset data"),
        ("p5063_violations_from_wd.csv", "P5063 raw SPARQL violations + synset data"),
        ("quickstatements/p8814_fixes_quickstatements.txt", "P8814 removals (original format, see Fixes tab)"),
        ("quickstatements/p5063_fixes_quickstatements.txt", "P5063 removals (original format, see Fixes tab)"),
        ("source_crosscheck.csv", "What english-wordnet / english-namenet say for every duplicate group"),
        ("keep_decisions.csv", "Which QID is kept per group, and why (source / members / similarity / tie / fallback)"),
        ("manual_review/decisions.csv", "Human decisions per duplicate group (keep / leave / defer); generate_proposals_v2.py consumes them"),
        ("manual_review/p8814_manual_review.csv", "P8814 review queue (weak keep-decision categories)"),
        ("manual_review/p5063_manual_review.csv", "P5063 review queue (empty)"),
        ("missing_ilis_verified.csv", "Synsets with a QID but no ILI, verified"),
        ("missing_ilis.csv", "Synsets with a QID but no ILI, first pass"),
        ("proposal_summary_v2.txt", "Proposal generation summary"),
    ]
    files = []
    for rel, desc in file_specs:
        p = OUTPUT_DIR / rel
        if p.exists():
            files.append({"path": rel, "desc": desc, "lines": count_lines(p), "kb": round(p.stat().st_size / 1024)})

    data_date = run_date(OUTPUT_DIR, datetime.fromtimestamp((OUTPUT_DIR / "p8814_violations_from_wd.csv").stat().st_mtime))

    reason_counts = Counter((k[0], v) for k, v in reasons.items())
    payload = {
        "reasons": [{"prop": k[0], "reason": k[1], "n": n} for k, n in sorted(reason_counts.items())],
        "p8814": rows8814, "p5063": rows5063,
        "fixes": [dict(f, cat="") for f in fix8814 + fix5063],
        "missing": missing_rows, "files": files, "batches": batch_table,
        "mappings": mapping_data["rows"] if mapping_data else [],
        "mstats": mapping_data["meta"] if mapping_data else {},
        "labels": CATEGORY_LABELS,
        "stats": {"p8814": s8814, "p5063": s5063, "p5063_raw": len(p5063_raw), "review_rows": review_rows,
                  "manual_extra": manual_extra, "data_date": data_date,
                  "generated": datetime.now().strftime("%Y-%m-%d %H:%M")},
    }
    # Fixes inherit the category / review flag from their row.
    lookup = {("P8814", r["q"], r["sid"]): r for r in rows8814}
    lookup.update({("P5063", r["q"], r["ili"]): r for r in rows5063})
    for f in payload["fixes"]:
        src = lookup.get((f["prop"], f["remove"], f["value"]))
        f["cat"] = src["cat"] if src else ""
        f["rev"] = src["rev"] if src else 0
        f["lab"] = src["lab"] if src else ""
        f["reason"] = src["reason"] if src else ""
        f["se"] = src["se"] if src else ""
        f["mem"] = src["mem"] if src else ""
        f["sdef"] = src["sdef"] if src else ""
        f["klab"] = (lookup.get((f["prop"], f["keep"], f["value"])) or {}).get("lab", "")

    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.replace("/*__DATA__*/null", blob)
    DASHBOARD_PATH.write_text(html, encoding="utf-8")

    print(f"P8814: {s8814}")
    print(f"P5063: {s5063}  (from {len(p5063_raw)} raw rows)")
    print(f"Review queue rows: {review_rows}; not in manual_review file: {manual_extra}")
    if mapping_data:
        m = mapping_data["meta"]
        print(f"Mappings tab: {m['total']} pairs from {m['path']} ({m['found']} linked, {m['strong']} strong)")
    print(f"Wrote {DASHBOARD_PATH} ({DASHBOARD_PATH.stat().st_size // 1024} KB)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WordNet2Wikidata</title>
<style>
:root {
  --bg:#f4f5f7; --card:#fff; --text:#1f2933; --muted:#667085; --border:#e1e4e8; --head:#eef1f5;
  --primary:#0b66c3; --primary-soft:#e5f0fb; --remove:#c62828; --remove-soft:#fdecec;
  --keep:#0b66c3; --keep-soft:#e5f0fb; --valid:#2e7d32; --valid-soft:#e8f5e9;
  --warn:#b45309; --warn-soft:#fff4e0; --shadow:0 1px 3px rgba(0,0,0,.08);
  --wd-soft:#f1f7fd; --wn-soft:#f7f2fb;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#12161b; --card:#1b2027; --text:#e6e9ee; --muted:#98a2b3; --border:#2d343d; --head:#232a33;
  --primary:#5aa9f0; --primary-soft:#16293c; --remove:#f0716f; --remove-soft:#3a1d1f;
  --keep:#5aa9f0; --keep-soft:#16293c; --valid:#6fcf76; --valid-soft:#18301b;
  --warn:#f0a95a; --warn-soft:#38290f; --shadow:none;
  --wd-soft:#16212d; --wn-soft:#221a2c; } }
:root[data-theme="dark"] {
  --bg:#12161b; --card:#1b2027; --text:#e6e9ee; --muted:#98a2b3; --border:#2d343d; --head:#232a33;
  --primary:#5aa9f0; --primary-soft:#16293c; --remove:#f0716f; --remove-soft:#3a1d1f;
  --keep:#5aa9f0; --keep-soft:#16293c; --valid:#6fcf76; --valid-soft:#18301b;
  --warn:#f0a95a; --warn-soft:#38290f; --shadow:none;
  --wd-soft:#16212d; --wn-soft:#221a2c; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:var(--bg); color:var(--text); }
a { color:var(--primary); text-decoration:none; } a:hover { text-decoration:underline; }
code { font:12px ui-monospace,Menlo,Consolas,monospace; background:var(--head); padding:1px 5px; border-radius:4px; }
.wrap { max-width:1500px; margin:0 auto; padding:0 16px 24px; }
header { padding:14px 0 10px; display:flex; flex-wrap:wrap; align-items:baseline; gap:2px 14px; }
header h1 { font-size:18px; font-weight:650; }
header .sub { color:var(--muted); font-size:13px; }
header .stamp { margin-left:auto; color:var(--muted); font-size:12px; }
.tabbar { position:sticky; top:0; z-index:50; background:var(--bg); padding:8px 0; border-bottom:1px solid var(--border);
  display:flex; gap:4px; flex-wrap:wrap; align-items:center; }
.tab { padding:6px 12px; border:1px solid var(--border); background:var(--card); color:var(--text); border-radius:6px;
  cursor:pointer; font:inherit; font-size:13px; }
.tab:hover { border-color:var(--primary); }
.tab.active { background:var(--primary); border-color:var(--primary); color:#fff; }
.tab .n { opacity:.7; font-size:11px; margin-left:4px; }
.theme { margin-left:auto; }
.panel { display:none; padding-top:12px; } .panel.active { display:block; }
.card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:14px 16px; margin-bottom:12px; box-shadow:var(--shadow); }
.card h2 { font-size:14px; font-weight:650; margin-bottom:8px; }
.card h3 { font-size:13px; font-weight:650; margin:12px 0 4px; }
.card p, .card li { margin-bottom:6px; } .card ul, .card ol { padding-left:20px; }
.muted { color:var(--muted); }
.grid { display:grid; gap:8px; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); }
.stat { border:1px solid var(--border); border-left:3px solid var(--primary); border-radius:6px; padding:8px 10px; background:var(--card); }
.stat .v { font-size:22px; font-weight:700; line-height:1.2; font-variant-numeric:tabular-nums; }
.stat .l { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.4px; }
.stat.remove { border-left-color:var(--remove); } .stat.remove .v { color:var(--remove); }
.stat.keep { border-left-color:var(--keep); } .stat.keep .v { color:var(--keep); }
.stat.valid { border-left-color:var(--valid); } .stat.valid .v { color:var(--valid); }
.alert { border-left:3px solid var(--primary); background:var(--primary-soft); padding:8px 12px; border-radius:4px; margin:8px 0; font-size:13px; }
.alert.warn { border-color:var(--warn); background:var(--warn-soft); }
.alert.remove { border-color:var(--remove); background:var(--remove-soft); }
.tip { position:relative; display:inline-block; border-bottom:1px dotted var(--primary); color:var(--primary); cursor:help; font-weight:600; }
.tip .box { display:none; position:absolute; left:0; top:calc(100% + 6px); z-index:60; background:var(--card); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:10px 12px; width:min(360px,90vw); text-align:left; font-size:12.5px; font-weight:400; line-height:1.55; box-shadow:var(--shadow); }
.tip:hover .box, .tip:focus .box, .tip:focus-within .box { display:block; }
.tip.end .box { left:auto; right:0; }
.bar { display:flex; height:22px; border-radius:5px; overflow:hidden; margin:8px 0 4px; }
.bar div { display:flex; align-items:center; justify-content:center; font-size:11px; color:#fff; min-width:2px; }
.legend { display:flex; gap:14px; flex-wrap:wrap; font-size:12px; color:var(--muted); }
.legend i { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; vertical-align:-1px; }
.cats { width:100%; border-collapse:collapse; }
.cats td { padding:3px 8px 3px 0; font-size:13px; vertical-align:middle; }
.cats tr.click { cursor:pointer; } .cats tr.click:hover td { background:var(--head); }
.cats .track { width:38%; } .cats .fill { height:10px; border-radius:3px; }
.cats .num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; width:1%; }
.toolbar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:8px; }
.toolbar input, .toolbar select { padding:5px 8px; border:1px solid var(--border); border-radius:5px; background:var(--card); color:var(--text); font:inherit; font-size:13px; }
.toolbar input { min-width:220px; }
.toolbar .count { margin-left:auto; color:var(--muted); font-size:12px; }
.btn { padding:5px 10px; border:1px solid var(--border); border-radius:5px; background:var(--card); color:var(--text); cursor:pointer; font:inherit; font-size:13px; }
.btn:hover { border-color:var(--primary); } .btn.primary { background:var(--primary); border-color:var(--primary); color:#fff; }
.scroll { overflow:auto; max-height:68vh; border:1px solid var(--border); border-radius:6px; background:var(--card); }
table.data { border-collapse:separate; border-spacing:0; width:100%; font-size:12.5px; }
table.data th { position:sticky; top:0; background:var(--head); text-align:left; padding:6px 10px; border-bottom:1px solid var(--border);
  white-space:nowrap; cursor:pointer; user-select:none; z-index:2; font-weight:600; }
table.data tr.grp th { top:0; z-index:3; text-align:center; font-size:11px; letter-spacing:.8px; padding:4px 10px; cursor:default; color:#fff; border-bottom:0; }
table.data.has-grp tr.hdr th { top:25px; }
table.data th.g-wd, table.data th.g-wn { color:#fff; } table.data th.g-wd { background:#0b66c3; } table.data th.g-wn { background:#7b3fb3; } table.data th.g-an { background:var(--head); color:var(--text); }
table.data tr.grp th.g-an { color:var(--muted); } table.data tr.grp th.g-'' { background:var(--head); }
table.data td.g-wd { background:var(--wd-soft); } table.data td.g-wn { background:var(--wn-soft); }
table.data th.sorted::after { content:' ▲'; font-size:9px; } table.data th.sorted.desc::after { content:' ▼'; }
table.data td { padding:5px 10px; border-bottom:1px solid var(--border); vertical-align:top; }
table.data tr:hover td { background:var(--head); }
td .id { color:var(--muted); font:11px ui-monospace,Menlo,Consolas,monospace; } .sib { margin-bottom:3px; } .pill.s { font-size:10.5px; padding:0 6px; }
td.nw { white-space:nowrap; } td.cat { min-width:170px; } td.wide { min-width:240px; max-width:380px; } td .sub { color:var(--muted); font-size:11.5px; }
.pill { display:inline-block; padding:1px 8px; border-radius:10px; font-size:11.5px; font-weight:600; white-space:nowrap; }
.pill.remove { background:var(--remove-soft); color:var(--remove); } .pill.keep { background:var(--keep-soft); color:var(--keep); }
.pill.valid { background:var(--valid-soft); color:var(--valid); } .pill.unresolved { background:var(--warn-soft); color:var(--warn); }
.pill.deferred { background:var(--warn-soft); color:var(--warn); }
.pill.rev { background:var(--warn-soft); color:var(--warn); }
pre.box { max-height:60vh; overflow:auto; background:var(--head); border:1px solid var(--border); border-radius:6px; padding:10px; font:12px/1.5 ui-monospace,Menlo,Consolas,monospace; white-space:pre; }
table.plain { border-collapse:collapse; width:100%; } table.plain th, table.plain td { text-align:left; padding:5px 10px; border-bottom:1px solid var(--border); font-size:13px; }
table.plain th { background:var(--head); }
@media (max-width:700px) { .toolbar input { min-width:0; width:100%; } }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1><a href="https://www.wikidata.org/wiki/Wikidata:WikiProject_WordNet" target="_blank" rel="noopener" title="The project on Wikidata">WordNet2Wikidata</a></h1>
  <span class="sub">P8814 (WordNet synset ID) &amp; P5063 (Interlingual Index) · <a href="https://github.com/yapy28/Wordnet2Wikidata-Mappings" target="_blank" rel="noopener" title="This project on GitHub">GitHub repo</a></span>
  <span class="stamp" id="stamp"></span>
</header>
<nav class="tabbar" id="tabbar"></nav>
<main id="panels"></main>
</div>

<script>
const D = /*__DATA__*/null;
const S = D.stats;
const $ = (s, el=document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = n => n.toLocaleString('en-US');
const pct = (a,b) => b ? (100*a/b).toFixed(1)+'%' : '–';
const qlink = q => q ? `<a href="https://www.wikidata.org/wiki/${esc(q)}" target="_blank" rel="noopener">${esc(q)}</a>` : '';
const ilink = i => i ? `<a href="https://globalwordnet.github.io/cili/${esc(i)}" target="_blank" rel="noopener" title="CILI entry">${esc(i)}</a>` : '';
const slink = s => s ? `<a href="https://en-word.net/id/oewn-${esc(s)}" target="_blank" rel="noopener" title="Open English WordNet entry">${esc(s)}</a>` : '';
const wdl = (q, text) => `<a href="https://www.wikidata.org/wiki/${esc(q)}" target="_blank" rel="noopener">${text}</a>`;
const PROP = {P8814:{n:'WordNet synset ID',u:'https://www.wikidata.org/wiki/Property:P8814'},
  P5063:{n:'Interlingual Index',u:'https://www.wikidata.org/wiki/Property:P5063'}};
const propLink = p => `<a href="${PROP[p].u}" target="_blank" rel="noopener" title="${esc(PROP[p].n)}">${p}</a>`;
const propCell = p => `${propLink(p)} <span class="sub">${esc(PROP[p].n)}</span>`;
D.p8814.forEach(r => r.prop = 'P8814'); D.p5063.forEach(r => r.prop = 'P5063');
const LAB = {}; [...D.p8814, ...D.p5063].forEach(r => { if (r.lab) LAB[r.q] = r.lab; });
const named = q => LAB[q] ? `${esc(LAB[q])} <span class="id">${esc(q)}</span>` : esc(q);
const namedLink = q => wdl(q, LAB[q] ? `<b>${esc(LAB[q])}</b>` : esc(q)) + (LAB[q] ? ` <span class="id">${esc(q)}</span>` : '');
const GROUPS = {}; [...D.p8814, ...D.p5063].forEach(r => (GROUPS[r.prop === 'P5063' ? '5:'+r.ili : '8:'+r.sid] ||= []).push(r));
const sibs = r => (GROUPS[r.prop === 'P5063' ? '5:'+r.ili : '8:'+r.sid] || []).filter(x => x.q !== r.q);
const nameNotes = t => esc(t).replace(/\bQ\d+\b/g, q => LAB[q] ? `${LAB[q]} (${q})` : q);
const catLabel = c => D.labels[c] || c;
const ROLE = {remove:'Remove', keep:'Keep', valid:'Valid', unresolved:'Unresolved', deferred:'Deferred'};
const rolePill = r => `<span class="pill ${r.role}">${ROLE[r.role]}</span>`;
const revPill = r => r.rev ? '<span class="pill rev" title="Weak keep-decision: check before removing">review</span>' : '';

/* ---------- reusable table: search + filters + sort over ALL rows, scroll box ---------- */
const GRP = {wd:'WIKIDATA', wn:'WORDNET', an:'ANALYSIS'};
function grpRow(cols) {
  if (!cols.some(c => c.grp)) return '';
  const g = []; cols.forEach(c => { const l = g[g.length-1], k = c.grp || ''; if (l && l.k === k) l.n++; else g.push({k, n:1}); });
  return `<tr class="grp">${g.map(x => `<th colspan="${x.n}" class="g-${x.k}">${GRP[x.k] || ''}</th>`).join('')}</tr>`;
}
function makeTable(host, cfg) {
  const st = {q:'', f:{}, sort:cfg.sort || null, dir:1};
  cfg.rows.forEach(r => r._s = cfg.cols.map(c => c.text ? c.text(r) : r[c.k]).join(' ').toLowerCase());
  host.innerHTML = `<div class="toolbar">
      <input type="search" placeholder="Search all columns…" data-q>
      ${(cfg.filters||[]).map(f => `<select data-f="${f.k}"><option value="">${esc(f.label)}</option>${f.opts().map(o => `<option value="${esc(o[0])}">${esc(o[1])}</option>`).join('')}</select>`).join('')}
      <button class="btn" data-reset>Reset</button>
      ${cfg.extra || ''}
      <span class="count"></span></div>
    <div class="scroll"><table class="data${cfg.cols.some(c => c.grp) ? ' has-grp' : ''}"><thead>${grpRow(cfg.cols)}<tr class="hdr">${cfg.cols.map((c,i) => `<th data-i="${i}" class="${c.grp ? 'g-'+c.grp : ''}">${esc(c.label)}</th>`).join('')}</tr></thead><tbody></tbody></table></div>`;
  const tb = $('tbody', host), count = $('.count', host);
  function view() {
    const q = st.q.toLowerCase().trim();
    let rows = cfg.rows.filter(r => (!q || r._s.includes(q)) && Object.entries(st.f).every(([k,v]) => !v || String(cfg.filters.find(f => f.k===k).get(r)) === v));
    if (st.sort !== null) {
      const c = cfg.cols[st.sort], key = c.sortKey || (r => (c.text ? c.text(r) : r[c.k]));
      rows = rows.slice().sort((a,b) => { const x=key(a), y=key(b); return (x>y?1:x<y?-1:0)*st.dir; });
    }
    const shown = cfg.limit && rows.length > cfg.limit ? rows.slice(0, cfg.limit) : rows;
    count.textContent = shown.length < rows.length
      ? `Showing first ${fmt(shown.length)} of ${fmt(rows.length)} matching rows — search or filter to narrow`
      : `${fmt(rows.length)} of ${fmt(cfg.rows.length)} rows`;
    tb.innerHTML = shown.map(r => `<tr>${cfg.cols.map(c => { const k = [c.cls, c.grp ? 'g-'+c.grp : ''].filter(Boolean).join(' '); return `<td${k ? ` class="${k}"` : ''}>${c.render ? c.render(r) : esc(r[c.k])}</td>`; }).join('')}</tr>`).join('');
    host.querySelectorAll('tr.hdr th').forEach((th,i) => { th.classList.toggle('sorted', i===st.sort); th.classList.toggle('desc', i===st.sort && st.dir<0); });
  }
  host.addEventListener('input', e => { if (e.target.matches('[data-q]')) { st.q = e.target.value; view(); } });
  host.addEventListener('change', e => { if (e.target.matches('[data-f]')) { st.f[e.target.dataset.f] = e.target.value; view(); } });
  host.addEventListener('click', e => {
    const th = e.target.closest('th'); if (th && th.dataset.i !== undefined) { const i = +th.dataset.i; st.dir = st.sort===i ? -st.dir : 1; st.sort = i; view(); }
    if (e.target.matches('[data-reset]')) { st.q=''; st.f={}; st.sort=cfg.sort||null; st.dir=1; $('[data-q]',host).value=''; host.querySelectorAll('[data-f]').forEach(s => s.value=''); view(); }
  });
  view();
  return { setFilter(k, v) { st.f[k]=v; const s = host.querySelector(`[data-f="${k}"]`); if (s) s.value=v; view(); } };
}

const catOpts = rows => () => [...new Set(rows.map(r => r.cat))].sort().map(c => [c, catLabel(c)]);
const srcFilters = [{k:'se',label:'Source: any',opts:() => Object.entries(SE),get:r=>r.se},
  {k:'reason',label:'Reason: any',opts:() => Object.entries(REASON),get:r=>r.reason}];
const roleOpts = () => [['remove','Remove'],['keep','Keep (canonical)'],['valid','Valid (no fix)']];
const REASON = {source:'Source repos name it', decision:'Human decision (decisions.csv)', decision_leave:'Human decision: keep both (decisions.csv)',
  defer:'Deferred — awaiting a decision', members_note:'Label is in synset members', similarity_note:'Best similarity score',
  label_in_members:'Label is in synset members', label_in_definition:'Label appears in definition', score:'Best label/definition score',
  score_tie:'Tie — no clear winner', fallback:'No evidence (first listed)'};
const WEAK = new Set(['score_tie','fallback']);
const SE = {yes:'In source', other:'Not the source QID', none:'No source QID'};
const srcCell = r => r.se === 'none' ? '<span class="muted">source has no QID for this</span>'
  : `<span class="pill s ${r.se==='yes'?'valid':'unresolved'}">${r.se==='yes' ? '✓ named by source' : '✗ source names another'}</span>`
    + (r.se==='other' ? `<div class="sub">${r.src.map(named).join(', ')}</div>` : '')
    + (r.role==='remove' && r.se==='yes' ? ' <span class="pill s remove" title="The source repos name the item we propose to remove">conflict</span>' : '');
const reasonCell = r => r.reason ? `<span class="${WEAK.has(r.reason) ? 'pill s unresolved' : ''}">${esc(REASON[r.reason] || r.reason)}</span>${r.dnote ? `<div class="sub">${esc(r.dnote)}</div>` : ''}` : '';
const wnCell = r => `<b>${esc(r.mem)}</b><div>${esc(r.sdef)}</div><div class="sub">${slink(r.sid)}${r.ili ? ' · ' + ilink(r.ili) : ''}</div>`;
const sibCell = r => sibs(r).map(x => `<div class="sib">${wdl(x.q, `<b>${esc(x.lab)}</b>`)} <span class="id">${esc(x.q)}</span> <span class="pill s ${x.role}">${ROLE[x.role]}</span></div>`).join('');
const decisionCell = r => {
  if (r.role === 'remove') return `Proposed fix: delete this statement (the value stays on ${namedLink(r.keep)})`;
  if (r.role === 'keep') { const rm = sibs(r).filter(x => x.role === 'remove'); return rm.length ? `Proposed fix: keep this statement (delete the duplicate from ${rm.map(x => namedLink(x.q)).join(', ')})` : ''; }
  return '';
};
const violationCols = (extra = []) => [
  {grp:'wd', k:'lab', label:'Item (label · description)', cls:'wide', render:r => `${wdl(r.q, `<b>${esc(r.lab)}</b>`)} <span class="id">${esc(r.q)}</span><div class="sub">${esc(r.desc)}</div>`, text:r => r.lab+' '+r.desc+' '+r.q},
  {grp:'wd', k:'sib', label:'Other items with the same value', cls:'wide', render:sibCell, text:r => sibs(r).map(x => x.lab+' '+x.q).join(' '), sortKey:r => sibs(r).length},
  {grp:'wn', k:'sdef', label:'Synset (lemmas · definition)', cls:'wide', render:wnCell, text:r => r.mem+' '+r.sdef+' '+r.sid+' '+r.ili, sortKey:r => r.sid+r.ili},
  {grp:'wn', k:'se', label:'Source repos say', cls:'wide', render:srcCell, text:r => SE[r.se]+' '+r.src.map(q => (LAB[q]||'')+' '+q).join(' ')},
  {grp:'an', k:'cat', label:'Category', cls:'cat', render:r => esc(catLabel(r.cat)), text:r => catLabel(r.cat)},
  {grp:'an', k:'role', label:'Verdict', render:rolePill, text:r => ROLE[r.role]},
  {grp:'an', k:'rev', label:'Review?', render:revPill, text:r => r.rev ? 'review' : '', sortKey:r => -r.rev},
  {grp:'an', k:'reason', label:'Why this keep', cls:'wide', render:reasonCell, text:r => REASON[r.reason] || ''},
  {grp:'an', k:'keep', label:'Proposed fix', cls:'wide', render:decisionCell, text:r => decisionCell(r).replace(/<[^>]+>/g, ''), sortKey:r => r.keep},
  {grp:'an', k:'conf', label:'Conf.', sortKey:r => +r.conf},
  {grp:'an', k:'notes', label:'Notes', cls:'wide', render:r => nameNotes(r.notes)},
  ...extra,
];
const reviewRows = [...D.p8814, ...D.p5063].filter(r => r.rev);


/* ---------- all-mappings table (import-pipeline comparison) ---------- */
const chk = v => v ? '<span class="pill valid">✓</span>' : '<span class="muted">–</span>';
const mapCols = () => [
  {grp:'wn', k:'sid', label:'Synset (lemmas · definition)', cls:'wide',
   render:r => `<b>${esc(r.mem)}</b><div>${esc(r.def)}</div><div class="sub">${slink(r.sid)}${r.ili ? ' · ' + ilink(r.ili) : ''}</div>`,
   text:r => r.mem+' '+r.def+' '+r.sid+' '+r.ili, sortKey:r => r.sid},
  {grp:'wd', k:'q', label:'Candidate QID (label · description)', cls:'wide',
   render:r => r.j ? `${qlink(r.q)} <span class="id">${esc(r.q)}</span><div class="sub"><b>${esc(r.lab)}</b>${r.desc ? ' — '+esc(r.desc) : ''}</div>`
     : `${qlink(r.q)} <span class="id">${esc(r.q)}</span><div class="sub">not linked in Wikidata (backlog)</div>`,
   text:r => r.q+' '+r.lab+' '+r.desc},
  {grp:'an', k:'j', label:'In Wikidata', render:r => r.j ? '<span class="pill valid">linked</span>' : '<span class="pill remove">backlog</span>', sortKey:r => -r.j},
  {grp:'an', k:'src', label:'Source', render:r => esc(r.src)},
  {grp:'an', k:'s', label:'Synset ID exact', render:r => chk(r.s), sortKey:r => -r.s},
  {grp:'an', k:'i', label:'ILI exact', render:r => chk(r.i), sortKey:r => -r.i},
  {grp:'an', k:'m', label:'Label in members', render:r => chk(r.m), sortKey:r => -r.m},
  {grp:'an', k:'d', label:'Def. overlap', render:r => r.n ? `${fmt(r.n)} <span class="muted">tokens</span>` : '<span class="muted">–</span>', sortKey:r => -r.n},
];

/* ---------- tab definitions ---------- */
const tabs = [
  {id:'overview', label:'Overview'},
  {id:'map', label:'All mappings', n:D.mappings.length, title:'Every OEWN/OENN synset with a candidate Wikidata QID (the import-pipeline comparison table)'},
  {id:'p8814', label:'P8814', n:D.p8814.length, title:'P8814 — WordNet synset ID'},
  {id:'p5063', label:'P5063', n:D.p5063.length, title:'P5063 — Interlingual Index'},
  {id:'review', label:'Review queue', n:reviewRows.length},
  {id:'fixes', label:'Fixes', n:D.fixes.length},
  {id:'missing', label:'Missing ILIs', n:D.missing.length},
  {id:'all', label:'All violations', n:D.p8814.length + D.p5063.length},
  {id:'method', label:'Pipeline & methods'},
  {id:'files', label:'Files'},
].filter(t => t.id !== 'map' || D.mappings.length);
const HELP = {
  overview: 'The big picture: how many duplicate mappings Wikidata has, how many are fine, and how many we propose to fix.',
  map: 'Every WordNet synset that has a matching Wikidata item. Search it to look up any single mapping.',
  p8814: 'Wikidata items that share the same WordNet synset ID. One row per item. Remove = we propose deleting the ID from this item; Keep = this item keeps it; Valid = the duplicate is fine.',
  p5063: 'Wikidata items that share the same Interlingual Index (ILI) ID. One row per item, same colours as the P8814 tab.',
  review: 'Duplicates where the evidence is thin, so a person should decide. Collaborators record their decisions in the shared Google Sheet.',
  fixes: 'The statements we propose to remove from Wikidata, ready to paste into QuickStatements.',
  missing: 'WordNet synsets that have a Wikidata item but no ILI on it yet.',
  all: 'Every row from the P8814 and P5063 tabs in one searchable table.',
  method: 'How the numbers were produced, step by step.',
  files: 'The data files behind this dashboard.',
};
const intro = id => `<p class="muted">${HELP[id]}</p>`;
$('#stamp').innerHTML = `Violations fetched ${S.data_date} · dashboard built ${S.generated} · <span class="tip end" tabindex="0">auto-generated<span class="box">Built automatically from the data files in this folder. Don't edit it by hand: run <code>python scripts/run_pipeline.py</code> to rebuild.</span></span>`;
$('#tabbar').innerHTML = tabs.map(t => `<button class="tab" data-tab="${t.id}"${t.title ? ` title="${esc(t.title)}"` : ''}>${t.label}${t.n!==undefined ? `<span class="n">${fmt(t.n)}</span>` : ''}</button>`).join('') + `<button class="tab theme" id="theme" title="Toggle dark mode">◐ Theme</button>`;
$('#panels').innerHTML = tabs.map(t => `<section class="panel" id="p-${t.id}"></section>`).join('');

const T = {};   // table handles, for cross-links from Overview
const built = {};
function build(id) {
  if (built[id]) return; built[id] = true;
  const el = $('#p-'+id);
  if (id === 'overview') overview(el);
  if (id === 'map' && D.mappings.length) { const M = D.mstats;
    el.innerHTML = `<div class="card">${intro('map')}<p class="muted">${fmt(M.total)} synsets as of ${esc(M.date)}; ${fmt(M.found)} (${pct(M.found, M.total)}) were already linked on Wikidata. Shows the first 500 rows: search or filter to narrow.</p><div id="t-map"></div></div>`;
    makeTable($('#t-map'), {rows:D.mappings, cols:mapCols(), sort:0, limit:500, filters:[
      {k:'j', label:'In Wikidata: any', opts:()=>[['1','Linked'],['0','Backlog (not linked)']], get:r=>r.j},
      {k:'src', label:'Source: any', opts:()=>[['OEWN','OEWN only'],['OENN','OENN only'],['both','Both repos']], get:r=>r.src.includes('+') ? 'both' : r.src},
      {k:'sig', label:'Evidence: any', opts:()=>[['strong','Strong (exact ID / ILI / label)'],['def','Definition overlap only'],['none','No signal']], get:r=>(r.s||r.i||r.m)?'strong':(r.d?'def':'none')}]}); }
  if (id === 'p8814') { el.innerHTML = `<div class="card">${intro('p8814')}<div id="t-p8814"></div></div>`;
    T.p8814 = makeTable($('#t-p8814'), {rows:D.p8814, cols:violationCols(), filters:[{k:'cat',label:'All categories',opts:catOpts(D.p8814),get:r=>r.cat},{k:'role',label:'All verdicts',opts:roleOpts,get:r=>r.role},...srcFilters]}); }
  if (id === 'p5063') { el.innerHTML = `<div class="card">${intro('p5063')}<div id="t-p5063"></div></div>`;
    T.p5063 = makeTable($('#t-p5063'), {rows:D.p5063, cols:violationCols([{grp:'an', k:'vt', label:'Constraint'}]), filters:[{k:'cat',label:'All categories',opts:catOpts(D.p5063),get:r=>r.cat},{k:'role',label:'All verdicts',opts:roleOpts,get:r=>r.role},...srcFilters]}); }
  if (id === 'review') { el.innerHTML = `<div class="card">${intro('review')}<div class="alert warn"><b>${fmt(new Set(reviewRows.map(r=>r.prop+(r.prop==='P5063'?r.ili:r.sid))).size)} groups need a decision</b> before any removal runs. Decisions are collected in the shared Google Sheet. <span class="tip" tabindex="0">Why these?<span class="box">The source repos don't say which item should keep the ID, and the items don't clearly match the synset (or look equally good), so the proposed keep is only a guess.</span></span></div><div id="t-review"></div></div>`;
    T.review = makeTable($('#t-review'), {rows:reviewRows, cols:[{k:'prop', label:'Property', render:r => propCell(r.prop), text:r => r.prop+' '+PROP[r.prop].n}, ...violationCols()], sort:3, filters:[{k:'prop',label:'Both properties',opts:()=>[['P8814','P8814'],['P5063','P5063']],get:r=>r.prop},{k:'cat',label:'All categories',opts:catOpts(reviewRows),get:r=>r.cat},{k:'role',label:'All verdicts',opts:roleOpts,get:r=>r.role},...srcFilters]}); }
  if (id === 'fixes') fixes(el);
  if (id === 'missing') { el.innerHTML = `<div class="card">${intro('missing')}<p class="muted"><b>NEEDS_NEW_ILI</b> = the ILI has to be created first. <b>USE_EXISTING_ILI</b> = the item already has one.</p><div id="t-missing"></div></div>`;
    makeTable($('#t-missing'), {rows:D.missing, cols:[
      {k:'sid', label:'Synset', render:r=>slink(r.sid)}, {k:'sdef', label:'Definition', cls:'wide'}, {k:'mem', label:'Members', cls:'wide'},
      {k:'q', label:'QID', render:r=>r.q.split('|').map(qlink).join(' ')}, {k:'oewn', label:'OEWN'}, {k:'oenn', label:'OENN'},
      {k:'ex', label:'Existing ILIs'}, {k:'status', label:'Status'}, {k:'qs', label:'QID status'}],
      filters:[{k:'status',label:'All statuses',opts:()=>[...new Set(D.missing.map(r=>r.status))].map(s=>[s,s]),get:r=>r.status}]}); }
  if (id === 'all') { const rows = [...D.p8814.map(r=>({...r, prop:'P8814', val:r.sid})), ...D.p5063.map(r=>({...r, prop:'P5063', val:r.ili}))];
    el.innerHTML = `<div class="card">${intro('all')}<div id="t-all"></div></div>`;
    makeTable($('#t-all'), {rows, cols:[{k:'prop', label:'Property', render:r => propCell(r.prop), text:r => r.prop+' '+PROP[r.prop].n}, ...violationCols()],
      filters:[{k:'prop',label:'Both properties',opts:()=>[['P8814','P8814'],['P5063','P5063']],get:r=>r.prop},{k:'cat',label:'All categories',opts:catOpts(rows),get:r=>r.cat},{k:'role',label:'All verdicts',opts:roleOpts,get:r=>r.role},...srcFilters]}); }
  if (id === 'method') method(el);
  if (id === 'files') files(el);
}

function overview(el) {
  const a = S.p8814, b = S.p5063, tot = a.total+b.total, valid = a.valid+b.valid, keep = a.keep+b.keep, rem = a.remove+b.remove;
  const M = D.mappings.length ? D.mstats : null;
  const catRows = (rows, key, color) => { const c = {}; rows.forEach(r => { (c[r.cat] = c[r.cat] || {n:0, role:r.role}).n++; }); const m = Object.entries(c).sort((x,y)=>y[1].n-x[1].n);
    return `<table class="cats">${m.map(([k,v]) => `<tr class="click" data-go="${key}" data-cat="${esc(k)}"><td>${esc(catLabel(k))}</td><td class="track"><div class="fill" style="width:${100*v.n/rows.length}%;background:var(--${v.role==='valid'?'valid':'remove'})"></div></td><td class="num">${fmt(v.n)} <span class="muted">${pct(v.n,rows.length)}</span></td></tr>`).join('')}</table>`; };
  el.innerHTML = `
  <div class="card"><h2>What this dashboard shows</h2>
    <p class="muted">Wikidata links its items to WordNet with two IDs: ${propLink('P8814')} (synset ID) and ${propLink('P5063')} (Interlingual Index, ILI). Each ID should sit on one item only. Where several items share it, we check whether that is a real mistake or fine, and propose fixes. Click a tab to explore:</p>
    <table class="plain">${tabs.filter(t => t.id !== 'overview').map(t => `<tr><td><a href="#${t.id}" data-show="${t.id}"><b>${esc(t.label)}</b></a></td><td>${HELP[t.id]}</td></tr>`).join('')}</table></div>
  <div class="card"><h2>The numbers</h2>
    ${M ? `<p class="muted">${fmt(tot)} statements have a duplicate ID, out of ${fmt(M.total)} WordNet–Wikidata pairs in total (${pct(tot, M.total)}).</p>` : ''}
    <div class="grid">
      <div class="stat"><div class="v">${fmt(tot)}</div><div class="l">Violating statements</div></div>
      <div class="stat valid"><div class="v">${fmt(valid)}</div><div class="l">Valid · no fix</div></div>
      <div class="stat keep"><div class="v">${fmt(keep)}</div><div class="l">Keep · canonical</div></div>
      <div class="stat remove"><div class="v">${fmt(rem)}</div><div class="l">Remove · to delete</div></div>
      <div class="stat"><div class="v">${fmt(S.review_rows)}</div><div class="l">Rows to review first</div></div>
    </div>
    <div class="bar"><div style="width:${100*valid/tot}%;background:var(--valid)">${pct(valid,tot)}</div><div style="width:${100*keep/tot}%;background:var(--keep)"></div><div style="width:${100*rem/tot}%;background:var(--remove)">${pct(rem,tot)}</div></div>
    <div class="legend"><span><i style="background:var(--valid)"></i>Valid duplicates (${fmt(valid)})</span><span><i style="background:var(--keep)"></i>Keep (${fmt(keep)})</span><span><i style="background:var(--remove)"></i>Remove (${fmt(rem)})</span></div>
    <table class="plain" style="margin-top:10px"><tr><th></th><th>Statements</th><th>Valid</th><th>Keep</th><th>Remove</th><th>Real violations</th></tr>
      <tr><td><b>${propLink('P8814')} · WordNet synset ID</b></td><td>${fmt(a.total)}</td><td>${fmt(a.valid)}</td><td>${fmt(a.keep)}</td><td>${fmt(a.remove)}</td><td>${fmt(a.keep+a.remove)} in ${fmt(a.keep)} synsets</td></tr>
      <tr><td><b>${propLink('P5063')} · Interlingual Index</b></td><td>${fmt(b.total)}</td><td>${fmt(b.valid)}</td><td>${fmt(b.keep)}</td><td>${fmt(b.remove)}</td><td>${fmt(b.keep+b.remove)} on ${fmt(b.keep)} ILIs</td></tr>
      <tr><th>Total</th><th>${fmt(tot)}</th><th>${fmt(valid)}</th><th>${fmt(keep)}</th><th>${fmt(rem)}</th><th>${fmt(keep+rem)}</th></tr></table>
    <p class="muted" style="margin-top:8px">In each real duplicate group one item keeps the ID and the others lose it: <b>${fmt(keep+rem)} flagged statements → ${fmt(rem)} removals</b>.</p>
    ${a.unresolved+b.unresolved ? `<div class="alert remove">${a.unresolved+b.unresolved} real-violation rows have no matching fix line.</div>` : ''}
    ${a.deferred+b.deferred ? `<div class="alert warn">${a.deferred+b.deferred} rows are on hold until someone decides.</div>` : ''}
  </div>
  <div class="card"><h2>Why we keep each item <span class="muted">(duplicate groups)</span></h2>
    <table class="plain"><tr><th>Reason</th><th>P8814</th><th>P5063</th></tr>
    ${Object.keys(REASON).filter((k,i,a) => a.indexOf(k)===i).map(k => { const g = p => (D.reasons.find(x => x.prop===p && x.reason===k)||{n:0}).n; return (g('P8814')||g('P5063')) ? `<tr><td>${WEAK.has(k) ? '<span class="pill s unresolved">weak</span> ' : ''}${esc(REASON[k])}</td><td>${fmt(g('P8814'))}</td><td>${fmt(g('P5063'))}</td></tr>` : ''; }).join('')}</table>
    <p class="muted" style="margin-top:6px">“Source repos name it” is the strongest evidence: the original WordNet data itself points to that item. “Weak” ones go to the Review queue.</p></div>
  <div class="card"><div class="alert"><b>All ${fmt(rem)} proposed fixes are removals on the Wikidata side</b> — deleting duplicate P8814/P5063 statements from one item of each group. <span class="tip" tabindex="0">What about the source repos?<span class="box">The source repos were cross-checked (<code>source_crosscheck.csv</code>): <b>${fmt([...D.p8814, ...D.p5063].filter(r => r.role==='remove' && r.se==='yes').length)} removals</b> target an item that english-wordnet / english-namenet name themselves — flagged <i>conflict</i> in the tables. Those need a source-side fix or a different keep decision before the removal is safe; every other removal agrees with the sources.</span></span></div></div>
  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(380px,1fr))">
    <div class="card"><h2>P8814 categories <span class="muted">(click to filter)</span></h2>${catRows(D.p8814,'p8814')}</div>
    <div class="card"><h2>P5063 categories <span class="muted">(click to filter)</span></h2>${catRows(D.p5063,'p5063')}</div>
  </div>`;
  el.addEventListener('click', e => { const lk = e.target.closest('[data-show]'); if (lk) { show(lk.dataset.show); return; }
    const tr = e.target.closest('[data-go]'); if (!tr) return; show(tr.dataset.go); T[tr.dataset.go].setFilter('cat', tr.dataset.cat); });
}

function qsText(list) { return list.map(f => `-${f.remove}|${f.prop}|"${f.value}"`).join('\n'); }
function fixes(el) {
  const n8 = D.fixes.filter(f=>f.prop==='P8814').length, n5 = D.fixes.length - n8;
  el.innerHTML = `<div class="card"><h2>${fmt(D.fixes.length)} removals (${fmt(n8)} ${propLink('P8814')} · ${fmt(n5)} ${propLink('P5063')})</h2>
    ${intro('fixes')}<div class="alert warn"><b>Use the commands below, not the files in <code>quickstatements/</code>.</b> Those files use an older format that QuickStatements rejects.</div>
    <div class="toolbar"><button class="btn primary" id="copy">Copy V1 commands</button><button class="btn" id="dl">Download .txt</button><span class="muted" id="qsnote"></span></div>
    <pre class="box" id="qsbox"></pre></div>
  <div class="card"><h2>Removal table</h2><div id="t-fixes"></div></div>`;
  const box = $('#qsbox', el), sel = () => D.fixes;
  box.textContent = qsText(sel());
  $('#copy', el).onclick = async () => { try { await navigator.clipboard.writeText(box.textContent); $('#qsnote', el).textContent = 'Copied.'; } catch { $('#qsnote', el).textContent = 'Copy blocked by browser — select the text manually.'; } };
  $('#dl', el).onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([box.textContent+'\n'], {type:'text/plain'})); a.download = 'violation_removals_quickstatements_v1.txt'; a.click(); };
  makeTable($('#t-fixes', el), {rows:D.fixes, cols:[
    {k:'prop', label:'Property', render:r => propCell(r.prop), text:r => r.prop+' '+PROP[r.prop].n},
    {grp:'wd', k:'lab', label:'Remove from', cls:'wide', render:r => namedLink(r.remove), text:r => (r.lab||'')+' '+r.remove},
    {grp:'wd', k:'klab', label:'Keep on', cls:'wide', render:r => namedLink(r.keep), text:r => (r.klab||'')+' '+r.keep},
    {grp:'wn', k:'sdef', label:'Synset (lemmas · definition)', cls:'wide', render:r => `<b>${esc(r.mem)}</b><div>${esc(r.sdef)}</div><div class="sub">${r.prop==='P8814' ? slink(r.value) : ilink(r.value)}</div>`, text:r => r.mem+' '+r.sdef+' '+r.value},
    {grp:'an', k:'cat', label:'Category', render:r=>esc(catLabel(r.cat)), text:r=>catLabel(r.cat)},
    {grp:'an', k:'reason', label:'Why this keep', render:reasonCell, text:r=>REASON[r.reason]||''},
    {grp:'an', k:'rev', label:'Review?', render:revPill, text:r=>r.rev?'review':'', sortKey:r=>-r.rev}],
    filters:[{k:'prop',label:'Both properties',opts:()=>[['P8814','P8814'],['P5063','P5063']],get:r=>r.prop},
             {k:'rev',label:'Review: any',opts:()=>[['1','Review first only']],get:r=>r.rev},
             {k:'reason',label:'Reason: any',opts:()=>Object.entries(REASON),get:r=>r.reason}]});
}

function method(el) {
  el.innerHTML = `
  <div class="card">${intro('method')}<h2>What this repository does</h2>
    <p>Two connected jobs around Open English WordNet (OEWN) / Open English Namenet (OENN) and Wikidata:</p>
    <ol>
      <li><b>Import pipeline (Jul–Aug 2026):</b> extract OEWN/OENN synsets that carry a Wikidata QID, compare them with what Wikidata already links via P8814 (WordNet synset ID) / P5063 (Interlingual Index), turn the missing ones (the “backlog”) into QuickStatements, import and verify. The <i>All mappings</i> tab shows this comparison table.</li>
      <li><b>Violation clean-up (Sep 2026 →):</b> the imported and pre-existing statements produce duplicate-value constraint violations on Wikidata. We fetch them, classify each as a real error or a legitimate duplicate (polysemy, synonyms), and propose removals. This dashboard covers this part.</li>
    </ol></div>
  <div class="card"><h2>Import pipeline</h2>
    <p><code>extract_yaml.py</code> → <code>fetch_wikidata.py</code> → <code>build_comparison_table.py</code> → backlog (manual work in Google Sheets) → import via QuickStatements (scripts now in <code>archive/</code>) → <code>verify_import.py</code></p>
    <p class="muted">Snapshots in README: 2026-07-01 — 22,670 candidate pairs, 70.95% already in Wikidata; 2026-08-16 — 22,691 pairs, 96.01% in Wikidata, 906 left in the backlog.</p>
    <table class="plain"><tr><th>QuickStatements batch (Aug 2026)</th><th>Done</th><th>Error</th></tr>
    ${D.batches.map(b => `<tr><td>${esc(b.batch)}</td><td>${fmt(b.done)}</td><td>${fmt(b.error)}</td></tr>`).join('')}</table></div>
  <div class="card"><h2>Violation pipeline</h2>
    <table class="plain"><tr><th>Step</th><th>Script</th><th>Output</th></tr>
      <tr><td>1 Fetch</td><td><code>fetch_violations.py</code></td><td><code>p*_violations_from_wd.csv</code></td></tr>
      <tr><td>2 Classify</td><td><code>categorize_all_final.py</code></td><td><code>p*_violations_final.csv</code></td></tr>
      <tr><td>3 Source cross-check</td><td><code>crosscheck_sources.py</code></td><td><code>source_crosscheck.csv</code></td></tr>
      <tr><td>4 Proposals</td><td><code>generate_proposals_v2.py</code></td><td><code>keep_decisions.csv</code>, <code>quickstatements/*.txt</code></td></tr>
      <tr><td>5 Dashboard</td><td><code>generate_dashboard.py</code></td><td><code>violations_dashboard.html</code></td></tr>
      <tr><td>6 Review sheet</td><td><code>export_review_sheet.py</code> / <code>import_decisions.py</code></td><td><code>review_sheet.xlsx</code> / <code>manual_review/decisions.csv</code></td></tr>
      <tr><td colspan="3" class="muted">All of it: <code>python scripts/run_pipeline.py</code>. Superseded scripts live in <code>archive/</code>.</td></tr></table></div>
  <div class="card"><h2>Classification and keep-decision</h2>
    <ul><li><b>P8814:</b> if one QID's label is among the synset members it is kept; if both are, the pair is a valid polysemy. Otherwise fall back to similarity between the QID description and the synset definition (best score is kept).</li>
    <li><b>P5063:</b> label/description similarity to the synset definition; <i>Dissimilar QIDs</i> are the real violations, the keep QID is the best-scoring one.</li>
    <li>Groups where neither QID clearly fits (<i>Different concepts</i>, <i>Multiple QIDs with mismatches</i>) form the <b>Review queue</b>.</li></ul></div>`;
}

function files(el) {
  el.innerHTML = `<div class="card">${intro('files')}<h2>Output files</h2>
    <table class="plain"><tr><th>File</th><th>Description</th><th>Lines</th><th>Size</th></tr>
    ${D.files.map(f => `<tr><td><a href="${esc(f.path)}">${esc(f.path)}</a></td><td>${esc(f.desc)}</td><td>${fmt(f.lines)}</td><td>${fmt(f.kb)} KB</td></tr>`).join('')}</table></div>`;
}

function show(id, push=true) {
  if (!tabs.some(t => t.id === id)) id = 'overview';
  build(id);
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === 'p-'+id));
  document.querySelectorAll('.tab[data-tab]').forEach(t => t.classList.toggle('active', t.dataset.tab === id));
  if (push) { try { history.replaceState(null, '', '#'+id); } catch {} }
  window.scrollTo({top:0});
}
$('#tabbar').addEventListener('click', e => { const t = e.target.closest('[data-tab]'); if (t) show(t.dataset.tab); });
$('#theme').onclick = () => {
  const cur = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('theme', next); } catch {}
};
try { const t = localStorage.getItem('theme'); if (t) document.documentElement.dataset.theme = t; } catch {}
show(location.hash.slice(1) || 'overview', false);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate the violations dashboard HTML.")
    parser.add_argument("run_dir", nargs="?", default=None,
                        help="output run dir (default: latest data/output/*/ with p8814_violations_final.csv)")
    main(parser.parse_args().run_dir)
