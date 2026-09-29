"""
Fetch P5063 and P8814 constraint violations directly from Wikidata SPARQL.

This replaces parsing static markdown files with live queries.
"""
import csv
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

try:
    import requests
    import yaml
except ImportError:
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml requests"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import requests
    import yaml

WDQS_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "violation-fetcher/0.1 (research script)"

BASE_DIR = Path(__file__).resolve().parent.parent  # Go to repo root
OUT_DIR = BASE_DIR / "data" / "output"

# Paths to source repos
OEWN_ROOT = Path("~/git/english-wordnet/src/yaml").expanduser()
OENN_ROOT = Path("~/git/english-namenet/data/curated").expanduser()


def run_wdqs(query: str, max_retries: int = 6) -> List[dict]:
    """Query Wikidata SPARQL endpoint."""
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": USER_AGENT,
    }
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = requests.get(
                WDQS_ENDPOINT,
                params={"query": query, "format": "json"},
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
            return response.json().get("results", {}).get("bindings", [])
        except requests.HTTPError as exc:
            last_error = exc
            status = getattr(exc.response, "status_code", None)
            if status in (403, 429, 500, 502, 503, 504) and attempt < (max_retries - 1):
                retry_after = response.headers.get("Retry-After")
                try:
                    wait = max(1.0, float(retry_after)) if retry_after else 2.0 * (attempt + 1)
                except ValueError:
                    wait = 2.0 * (attempt + 1)
                print(f"  HTTP {status}, retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            raise
        except requests.RequestException as exc:
            last_error = exc
            if attempt < (max_retries - 1):
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
    if last_error:
        raise last_error
    return []


def fetch_p5063_single_value_violations() -> List[Dict[str, str]]:
    """
    Fetch P5063 "single value" violations:
    Wikidata items that have multiple P5063 (ILI) values.
    
    Returns: List of {entity, entityLabel, ili} for each violation
    """
    query = """
    SELECT ?entity ?entityLabel ?ili1 ?ili2 WHERE {
      ?entity wdt:P5063 ?ili1 .
      ?entity wdt:P5063 ?ili2 .
      FILTER(?ili1 != ?ili2)
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    ORDER BY ?entity
    """
    
    print("  Querying P5063 single-value violations...")
    bindings = run_wdqs(query)
    
    results = []
    for row in bindings:
        entity_uri = row.get("entity", {}).get("value", "")
        qid = entity_uri.rsplit("/", 1)[-1] if entity_uri else ""
        label = row.get("entityLabel", {}).get("value", "")
        ili1 = row.get("ili1", {}).get("value", "")
        ili2 = row.get("ili2", {}).get("value", "")
        
        # Return both ILIs
        results.append({
            "type": "single_value",
            "entity": entity_uri,
            "qid": qid,
            "label": label,
            "ili": ili1,
        })
        results.append({
            "type": "single_value",
            "entity": entity_uri,
            "qid": qid,
            "label": label,
            "ili": ili2,
        })
    
    return results


def fetch_p5063_unique_value_violations() -> List[Dict[str, str]]:
    """
    Fetch P5063 "unique value" violations:
    ILI values that are used on multiple Wikidata items.
    
    Returns: List of {ili, entity, entityLabel} for each violation
    """
    query = """
    SELECT ?ili ?entity1 ?entity1Label ?entity2 ?entity2Label WHERE {
      ?entity1 wdt:P5063 ?ili .
      ?entity2 wdt:P5063 ?ili .
      FILTER(?entity1 != ?entity2)
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    ORDER BY ?ili
    """
    
    print("  Querying P5063 unique-value violations...")
    bindings = run_wdqs(query)
    
    results = []
    for row in bindings:
        ili = row.get("ili", {}).get("value", "")
        entity1_uri = row.get("entity1", {}).get("value", "")
        entity2_uri = row.get("entity2", {}).get("value", "")
        label1 = row.get("entity1Label", {}).get("value", "")
        label2 = row.get("entity2Label", {}).get("value", "")
        qid1 = entity1_uri.rsplit("/", 1)[-1] if entity1_uri else ""
        qid2 = entity2_uri.rsplit("/", 1)[-1] if entity2_uri else ""
        
        # Return both entities
        results.append({
            "type": "unique_value",
            "entity": entity1_uri,
            "qid": qid1,
            "label": label1,
            "ili": ili,
        })
        results.append({
            "type": "unique_value",
            "entity": entity2_uri,
            "qid": qid2,
            "label": label2,
            "ili": ili,
        })
    
    return results


def fetch_p8814_violations() -> List[Dict[str, str]]:
    """
    Fetch P8814 violations:
    Synsets that have multiple Wikidata items.
    
    Note: P8814 is on the synset side in Wikidata, but we query from the Wikidata side.
    This finds Wikidata items that share the same synset ID.
    
    Returns: List of {synset_id, entity, entityLabel} for each violation
    """
    query = """
    SELECT ?ssid ?entity1 ?entity2 ?entity1Label ?entity2Label WHERE {
      ?entity1 wdt:P8814 ?ssid .
      ?entity2 wdt:P8814 ?ssid .
      FILTER(?entity1 != ?entity2)
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    ORDER BY ?ssid
    """
    
    print("  Querying P8814 violations...")
    bindings = run_wdqs(query)
    
    # Use a set to avoid duplicates
    seen = set()
    results = []
    for row in bindings:
        ssid = row.get("ssid", {}).get("value", "")
        # Get both entities
        for entity_key in ["entity1", "entity2"]:
            entity_uri = row.get(entity_key, {}).get("value", "")
            qid = entity_uri.rsplit("/", 1)[-1] if entity_uri else ""
            label = row.get(f"{entity_key}Label", {}).get("value", "")
            
            if qid:  # Only add if we have a QID
                # Deduplicate by (ssid, qid)
                key = (ssid, qid)
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "type": "p8814",
                        "synset_id": ssid,
                        "entity": entity_uri,
                        "qid": qid,
                        "label": label,
                    })
    
    return results


def build_ili_synset_lookup() -> Dict[str, List[dict]]:
    """Build ILI -> synset lookup from OEWN/OENN."""
    ili_map = {}
    
    def scan(root: Path, source: str):
        yaml_files = list(root.rglob("*.yaml")) + list(root.rglob("*.yml"))
        for fp in yaml_files:
            try:
                data = yaml.safe_load(fp.read_text(encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for synset_id, payload in data.items():
                if not isinstance(payload, dict):
                    continue
                ili = payload.get("ili")
                if ili and isinstance(ili, str):
                    ili = ili.strip()
                    if ili not in ili_map:
                        ili_map[ili] = []
                    
                    wikidata = payload.get("wikidata")
                    definition = payload.get("definition", "")
                    members = payload.get("members", [])
                    
                    if isinstance(definition, list):
                        definition = " ".join(str(d).strip() for d in definition)
                    else:
                        definition = str(definition).strip() if definition else ""
                    
                    if isinstance(members, list):
                        members = "|".join(str(m).strip() for m in members)
                    else:
                        members = str(members).strip() if members else ""
                    
                    # Normalize wikidata
                    if wikidata is None:
                        wd_list = []
                    elif isinstance(wikidata, list):
                        wd_list = [str(q).strip() for q in wikidata]
                    elif isinstance(wikidata, str):
                        wd_list = [wikidata.strip()] if wikidata.strip() else []
                    else:
                        wd_list = []
                    
                    ili_map[ili].append({
                        "synset_id": synset_id,
                        "ili": ili,
                        "definition": definition,
                        "members": members,
                        "wikidata_qids": wd_list,
                        "source": source,
                    })
    
    scan(OEWN_ROOT, "OEWN")
    scan(OENN_ROOT, "OENN")
    
    return ili_map


def build_qid_synset_lookup() -> Dict[str, List[dict]]:
    """Build QID -> synset lookup from OEWN/OENN."""
    qid_map = {}
    
    def scan(root: Path, source: str):
        yaml_files = list(root.rglob("*.yaml")) + list(root.rglob("*.yml"))
        for fp in yaml_files:
            try:
                data = yaml.safe_load(fp.read_text(encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for synset_id, payload in data.items():
                if not isinstance(payload, dict):
                    continue
                wikidata = payload.get("wikidata")
                ili = payload.get("ili", "")
                definition = payload.get("definition", "")
                members = payload.get("members", [])
                
                # Normalize
                if isinstance(ili, str):
                    ili = ili.strip()
                if isinstance(definition, list):
                    definition = " ".join(str(d).strip() for d in definition)
                else:
                    definition = str(definition).strip() if definition else ""
                if isinstance(members, list):
                    members = "|".join(str(m).strip() for m in members)
                else:
                    members = str(members).strip() if members else ""
                
                if wikidata is None:
                    wd_list = []
                elif isinstance(wikidata, list):
                    wd_list = [str(q).strip() for q in wikidata]
                elif isinstance(wikidata, str):
                    wd_list = [wikidata.strip()] if wikidata.strip() else []
                else:
                    wd_list = []
                
                for wd_qid in wd_list:
                    if wd_qid not in qid_map:
                        qid_map[wd_qid] = []
                    qid_map[wd_qid].append({
                        "synset_id": synset_id,
                        "ili": ili,
                        "definition": definition,
                        "members": members,
                        "wikidata_qids": [wd_qid],
                        "source": source,
                    })
    
    scan(OEWN_ROOT, "OEWN")
    scan(OENN_ROOT, "OENN")
    
    return qid_map


def build_synset_lookup() -> Dict[str, dict]:
    """Build synset_id -> synset lookup."""
    s2s = {}
    
    def scan(root: Path, source: str):
        yaml_files = list(root.rglob("*.yaml")) + list(root.rglob("*.yml"))
        for fp in yaml_files:
            try:
                data = yaml.safe_load(fp.read_text(encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for synset_id, payload in data.items():
                if isinstance(payload, dict):
                    ili = payload.get("ili", "")
                    wikidata = payload.get("wikidata")
                    definition = payload.get("definition", "")
                    members = payload.get("members", [])
                    
                    if isinstance(ili, str):
                        ili = ili.strip()
                    if isinstance(definition, list):
                        definition = " ".join(str(d).strip() for d in definition)
                    else:
                        definition = str(definition).strip() if definition else ""
                    if isinstance(members, list):
                        members = "|".join(str(m).strip() for m in members)
                    else:
                        members = str(members).strip() if members else ""
                    
                    if wikidata is None:
                        wd_list = []
                    elif isinstance(wikidata, list):
                        wd_list = [str(q).strip() for q in wikidata]
                    elif isinstance(wikidata, str):
                        if "|" in wikidata:
                            wd_list = [q.strip() for q in wikidata.split("|")]
                        else:
                            wd_list = [wikidata.strip()]
                    else:
                        wd_list = []
                    
                    s2s[synset_id] = {
                        "synset_id": synset_id,
                        "ili": ili,
                        "definition": definition,
                        "members": members,
                        "wikidata_qids": wd_list,
                        "source": source,
                    }
    
    scan(OEWN_ROOT, "OEWN")
    scan(OENN_ROOT, "OENN")
    
    return s2s


def build_violation_table(violations: List[Dict[str, str]], ili_map: Dict[str, List[dict]], qid_map: Dict[str, List[dict]]) -> List[dict]:
    """Build enriched violation table."""
    rows = []
    
    for v in violations:
        vtype = v.get("type", "")
        qid = v.get("qid", "")
        ili = v.get("ili", "")
        label = v.get("label", "")
        synset_id = v.get("synset_id", "")
        
        if vtype == "p8814":
            # P8814 violation: synset with multiple QIDs
            if synset_id in s2s:
                synset = s2s[synset_id]
                row = {
                    "violation_type": "p8814",
                    "synset_id": synset_id,
                    "qid": qid,
                    "wikidata_label": label,
                    "synset_definition": synset.get("definition", ""),
                    "synset_members": synset.get("members", ""),
                    "synset_ili": synset.get("ili", ""),
                    "synset_source": synset.get("source", ""),
                    "synset_wikidata_qids": "|".join(synset.get("wikidata_qids", [])),
                }
                # Add other synsets with this QID
                if qid in qid_map:
                    other_synsets = [s["synset_id"] for s in qid_map[qid] if s["synset_id"] != synset_id]
                    if other_synsets:
                        row["other_synsets_with_qid"] = "|".join(other_synsets)
                rows.append(row)
        else:
            # P5063 violation
            row = {
                "violation_type": vtype,
                "qid": qid,
                "ili": ili,
                "wikidata_label": label,
            }
            
            # Add synset info for this ILI
            if ili in ili_map:
                for synset in ili_map[ili]:
                    row_copy = row.copy()
                    row_copy.update({
                        "synset_id": synset["synset_id"],
                        "synset_definition": synset["definition"],
                        "synset_members": synset["members"],
                        "synset_ili": synset["ili"],
                        "synset_source": synset["source"],
                        "synset_wikidata_qids": "|".join(synset["wikidata_qids"]),
                    })
                    rows.append(row_copy)
            else:
                rows.append(row)
    
    return rows


# Main
print("="*70)
print("Fetching violations from Wikidata SPARQL")
print("="*70)

# Build lookups
print("\nBuilding lookup tables from OEWN/OENN...")
i2s = build_ili_synset_lookup()
qid_map = build_qid_synset_lookup()
s2s = build_synset_lookup()
print(f"Loaded {len(i2s)} ILIs, {len(qid_map)} QIDs, {len(s2s)} synsets")

# Fetch violations
print("\nFetching P5063 single-value violations...")
p5063_single = fetch_p5063_single_value_violations()
print(f"  Found {len(p5063_single)} rows")

print("\nFetching P5063 unique-value violations...")
p5063_unique = fetch_p5063_unique_value_violations()
print(f"  Found {len(p5063_unique)} rows")

print("\nFetching P8814 violations...")
p8814 = fetch_p8814_violations()
print(f"  Found {len(p8814)} rows")

# Combine all P5063 violations
all_p5063 = p5063_single + p5063_unique

# Build tables
print("\nBuilding enriched tables...")
p5063_rows = build_violation_table(all_p5063, i2s, qid_map)
p8814_rows = build_violation_table(p8814, i2s, qid_map)

# Write output
OUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"\nWriting P5063 violations ({len(p5063_rows)} rows)...")
fieldnames_p5063 = set()
for row in p5063_rows:
    fieldnames_p5063.update(row.keys())
with (OUT_DIR / "p5063_violations_from_wd.csv").open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=sorted(fieldnames_p5063))
    writer.writeheader()
    writer.writerows(p5063_rows)

print(f"Writing P8814 violations ({len(p8814_rows)} rows)...")
fieldnames_p8814 = set()
for row in p8814_rows:
    fieldnames_p8814.update(row.keys())
with (OUT_DIR / "p8814_violations_from_wd.csv").open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=sorted(fieldnames_p8814))
    writer.writeheader()
    writer.writerows(p8814_rows)

print("\nDone!")
print(f"P5063: {len(p5063_rows)} rows -> {OUT_DIR / 'p5063_violations_from_wd.csv'}")
print(f"P8814: {len(p8814_rows)} rows -> {OUT_DIR / 'p8814_violations_from_wd.csv'}")
