"""
Fetches all Wikidata entities linked to English WordNet via:
  - P5063 (Interlingual Index ID / ILI)
  - P8814 (WordNet 3.1 Synset ID)

Writes: output/wikidata_wordnet_links.csv
"""
import csv
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

WDQS_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "oewn-oenn-fetch/0.1 (research script; contact: you@example.com)"
BASE_DIR = Path(__file__).resolve().parent

QUERY = """
SELECT ?entity ?entityLabel ?entityDescription ?ili ?ssid WHERE {
  {
    ?entity wdt:P5063 ?ili
  } UNION {
    ?entity wdt:P8814 ?ssid
  }
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en".
  }
}
"""


def run_wdqs(query: str, max_retries: int = 6) -> List[dict]:
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": USER_AGENT,
    }
    last_error: Optional[Exception] = None
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
                print(f"HTTP {status}, retrying in {wait:.1f}s...")
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


def fetch() -> List[Dict[str, str]]:
    print("Querying Wikidata SPARQL endpoint...")
    bindings = run_wdqs(QUERY)
    rows = []
    for row in bindings:
        entity_uri = row.get("entity", {}).get("value", "")
        qid = entity_uri.rsplit("/", 1)[-1] if entity_uri else ""
        rows.append({
            "entity_uri": entity_uri,
            "qid": qid,
            "entity_label": row.get("entityLabel", {}).get("value", ""),
            "entity_description": row.get("entityDescription", {}).get("value", ""),
            "ili": row.get("ili", {}).get("value", ""),
            "ssid": row.get("ssid", {}).get("value", ""),
        })
    return rows


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
