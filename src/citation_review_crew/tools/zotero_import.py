"""
Import replacement papers into Zotero library via API.

Usage:
    1. Populate the `papers` list below with your replacement references.
    2. Set ZOTERO_API_KEY, ZOTERO_LIBRARY_TYPE, ZOTERO_LIBRARY_ID in .env
    3. Run: uv run python src/citation_review_crew/tools/zotero_import.py
"""
from __future__ import annotations

import os
import sys
import io
import requests
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
load_dotenv()

API_KEY = os.getenv("ZOTERO_API_KEY")
LIB_TYPE = os.getenv("ZOTERO_LIBRARY_TYPE", "user")
LIB_ID = os.getenv("ZOTERO_LIBRARY_ID")

if not all([API_KEY, LIB_ID]):
    print("Error: Set ZOTERO_API_KEY and ZOTERO_LIBRARY_ID in .env")
    sys.exit(1)

# --- Replace with your own papers ---
papers = [
    {
        "itemType": "journalArticle",
        "title": "Example Paper Title",
        "creators": [
            {"creatorType": "author", "firstName": "A", "lastName": "Example"},
        ],
        "date": "2024",
        "publicationTitle": "Example Journal",
        "volume": "1",
        "issue": "1",
        "pages": "1-10",
        "DOI": "10.1234/example",
        "tags": [{"tag": "citation-fix"}],
    },
]
# --- End of paper list ---

url = f"https://api.zotero.org/{LIB_TYPE}s/{LIB_ID}/items"
headers = {"Zotero-API-Key": API_KEY, "Content-Type": "application/json"}

resp = requests.post(url, headers=headers, json=papers, timeout=30)
print(f"Status: {resp.status_code}")
if resp.status_code in (200, 201):
    result = resp.json()
    success = result.get("success", {})
    failed = result.get("failed", {})
    print(f"Imported: {len(success)} items")
    for idx, key in success.items():
        print(f"  [{idx}] -> {key}")
    if failed:
        print(f"Failed: {len(failed)} items")
        for k, v in failed.items():
            print(f"  [{k}]: {v}")
else:
    print(f"Error: {resp.text[:500]}")
