#!/usr/bin/env python3
"""Check which QIDs in the import file still exist on Wikidata."""

import urllib.request
import urllib.error
import sys
from pathlib import Path

HEADERS = {"User-Agent": "OEWN-OENN-Import-Bot/1.0"}

def check_qids_exist(tsv_file: Path) -> tuple:
    with open(tsv_file, "r", encoding="utf-8") as f:
        statements = [line.strip().split("\t") for line in f if line.strip()]
    
    qids = list(set(stmt[0] for stmt in statements))
    
    existing = []
    deleted = []
    errors = []
    
    print(f"Checking {len(qids)} unique QIDs...")
    
    for i, qid in enumerate(qids, 1):
        try:
            url = f"https://www.wikidata.org/wiki/{qid}"
            req = urllib.request.Request(url, headers=HEADERS, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status == 200:
                    existing.append(qid)
                else:
                    deleted.append(qid)
        except urllib.error.HTTPError as e:
            deleted.append(qid)
        except Exception as e:
            errors.append((qid, str(e)))
        
        if i % 100 == 0:
            print(f"  Checked {i}/{len(qids)}...")
    
    return existing, deleted, errors


if __name__ == "__main__":
    tsv_file = Path("output/wikidata_import_cleaned.tsv")
    if not tsv_file.exists():
        print(f"File not found: {tsv_file}")
        sys.exit(1)
    
    existing, deleted, errors = check_qids_exist(tsv_file)
    
    print(f"\nExisting: {len(existing)}")
    print(f"Deleted/Non-existent: {len(deleted)}")
    print(f"Errors: {len(errors)}")
    
    if deleted:
        print(f"\nDeleted QIDs ({len(deleted)}):")
        for qid in sorted(deleted)[:50]:
            print(f"  {qid}")
        if len(deleted) > 50:
            print(f"  ... and {len(deleted) - 50} more")
    
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for qid, err in errors[:10]:
            print(f"  {qid}: {err}")
