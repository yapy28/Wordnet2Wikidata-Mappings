"""
Fetches all Wikidata entities linked to English WordNet via:
  - P5063 (Interlingual Index ID / ILI)
  - P8814 (WordNet 3.1 Synset ID)

Writes: output/wikidata_wordnet_links.csv
"""
import csv
import io
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    print("Installing requests...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import requests

WDQS_ENDPOINT = "https://query.wikidata.org/sparql"
API_ENDPOINT = "https://www.wikidata.org/w/api.php"
USER_AGENT = "oewn-oenn-fetch/0.1 (research script; contact: you@example.com)"
BASE_DIR = Path(__file__).resolve().parent

# Two-stage fetch. WDQS enforces a ~60 s query timeout, and the wikibase:label
# service over a full property (~10k+ solutions) regularly exceeds it — the query
# is then killed, sometimes mid-stream, which looks like a truncated response.
# So: stage 1 pages the plain statement scan (sub-second per page, CSV output),
# stage 2 fetches labels/descriptions in wbgetentities batches of 50.
PAGE_SIZE = 10000
LABEL_BATCH = 50

QUERIES = {
    "P5063": """
SELECT ?entity ?ili WHERE {
  ?entity wdt:P5063 ?ili .
}
ORDER BY ?entity
""",
    "P8814": """
SELECT ?entity ?ssid WHERE {
  ?entity wdt:P8814 ?ssid .
}
ORDER BY ?entity
""",
}

COUNTS = {
    "P5063": "SELECT (COUNT(*) AS ?c) WHERE { ?entity wdt:P5063 ?v }",
    "P8814": "SELECT (COUNT(*) AS ?c) WHERE { ?entity wdt:P8814 ?v }",
}


def run_wdqs(query: str, max_retries: int = 8) -> List[dict]:
    """Run a query, return its rows as dicts (CSV serialisation)."""
    headers = {
        "Accept": "text/csv",
        "User-Agent": USER_AGENT,
    }
    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            response = requests.get(
                WDQS_ENDPOINT,
                params={"query": query},
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(response.text)))
            if rows and any(v is None for v in rows[-1].values()):
                raise ValueError("response looks truncated (row with missing fields)")
            return rows
        except requests.HTTPError as exc:
            last_error = exc
            status = getattr(exc.response, "status_code", None)
            if status in (403, 429, 500, 502, 503, 504) and attempt < (max_retries - 1):
                retry_after = response.headers.get("Retry-After")
                try:
                    wait = max(1.0, float(retry_after)) if retry_after else 2.0 * (attempt + 1)
                except ValueError:
                    wait = 2.0 * (attempt + 1)
                print(f"HTTP {status}, retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            raise
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < (max_retries - 1):
                print(f"Failed attempt ({exc.__class__.__name__}: {exc}), retrying...")
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
    if last_error:
        raise last_error
    return []


def fetch_labels(qids: List[str]) -> Dict[str, Dict[str, str]]:
    """Fetch the en label and description for each QID via the Action API
    (wbgetentities, 50 ids per call, a few parallel workers)."""
    batches = [qids[i:i + LABEL_BATCH] for i in range(0, len(qids), LABEL_BATCH)]
    progress = {"done": 0}
    lock = threading.Lock()

    def get_batch(batch: List[str]) -> dict:
        data = {}
        for attempt in range(8):
            try:
                r = requests.get(
                    API_ENDPOINT,
                    params={
                        "action": "wbgetentities",
                        "format": "json",
                        "ids": "|".join(batch),
                        "props": "labels|descriptions",
                        "languages": "en",
                    },
                    headers={"User-Agent": USER_AGENT},
                    timeout=60,
                )
                r.raise_for_status()
                data = r.json()
                break
            except (requests.RequestException, ValueError) as exc:
                if attempt == 7:
                    raise
                print(f"  label batch failed ({exc.__class__.__name__}: {exc}), retrying...")
                time.sleep(1.0 * (attempt + 1))
        with lock:
            progress["done"] += len(batch)
            if progress["done"] % 2500 < LABEL_BATCH or progress["done"] >= len(qids):
                print(f"  labels: {progress['done']}/{len(qids)}")
        return data

    out: Dict[str, Dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for data in pool.map(get_batch, batches):
            for qid, ent in data.get("entities", {}).items():
                out[qid] = {
                    "label": ent.get("labels", {}).get("en", {}).get("value", ""),
                    "description": ent.get("descriptions", {}).get("en", {}).get("value", ""),
                }
    return out


def fetch() -> List[Dict[str, str]]:
    # Stage 1: statement scan, one property at a time, paged (no label service).
    print("Stage 1: fetching P5063 / P8814 statements from the SPARQL endpoint...")
    rows = []
    for prop in ("P5063", "P8814"):
        print(f"-- {prop}")
        offset = 0
        while True:
            paged = QUERIES[prop] + f"LIMIT {PAGE_SIZE}\nOFFSET {offset}\n"
            page = run_wdqs(paged)
            for row in page:
                entity_uri = row.get("entity", "") or ""
                rows.append({
                    "entity_uri": entity_uri,
                    "qid": entity_uri.rsplit("/", 1)[-1] if entity_uri else "",
                    "entity_label": "",
                    "entity_description": "",
                    "ili": row.get("ili", "") or "",
                    "ssid": row.get("ssid", "") or "",
                })
            print(f"  {prop}: page {offset // PAGE_SIZE + 1} returned {len(page)} rows, total so far {len(rows)}")
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

    seen, unique = set(), []
    for r in rows:
        key = (r["entity_uri"], r["ili"], r["ssid"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    for prop in ("P5063", "P8814"):
        expected = int(run_wdqs(COUNTS[prop])[0]["c"])
        value_key = "ili" if prop == "P5063" else "ssid"
        got = len({(r["entity_uri"], r[value_key]) for r in unique if r[value_key]})
        print(f"{prop}: {got} unique values fetched vs {expected} on Wikidata")
        if got != expected:
            raise RuntimeError(f"{prop} fetch incomplete ({got} != {expected}) — re-run fetch_wikidata.py")

    # Stage 2: labels and descriptions via the Action API.
    print(f"Stage 2: fetching labels/descriptions for {len({r['qid'] for r in unique})} entities...")
    labels = fetch_labels(sorted({r["qid"] for r in unique}))
    for r in unique:
        lab = labels.get(r["qid"], {})
        r["entity_label"] = lab.get("label", "")
        r["entity_description"] = lab.get("description", "")

    print(f"fetched {len(unique)} unique statement rows")
    return unique


def main() -> None:
    out_path = BASE_DIR / "output" / "wikidata_wordnet_links.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = fetch()

    fieldnames = ["entity_uri", "qid", "entity_label", "entity_description", "ili", "ssid"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Rows written: {len(rows)}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
