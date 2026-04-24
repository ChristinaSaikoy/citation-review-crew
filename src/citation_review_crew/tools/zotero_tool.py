from __future__ import annotations

import os
from typing import Any

import requests

ALLOWED_ITEM_TYPES = {
    "journalArticle",
    "conferencePaper",
    "preprint",
    "report",
    "book",
    "bookSection",
    "thesis",
    "document",
}


class ZoteroConfigError(Exception):
    pass


class ZoteroRequestError(Exception):
    pass


def zotero_is_configured() -> bool:
    return all(
        os.getenv(name)
        for name in ("ZOTERO_API_KEY", "ZOTERO_LIBRARY_TYPE", "ZOTERO_LIBRARY_ID")
    )


def fetch_zotero_citations() -> str:
    api_key = _require_env("ZOTERO_API_KEY")
    library_type = _require_env("ZOTERO_LIBRARY_TYPE")
    library_id = _require_env("ZOTERO_LIBRARY_ID")
    limit = max(1, int(os.getenv("ZOTERO_LIMIT", "20")))
    search = os.getenv("ZOTERO_SEARCH", "").strip()
    item_types = _parse_item_types(os.getenv("ZOTERO_ITEM_TYPES", ""))

    items = _fetch_items(
        api_key=api_key,
        library_type=library_type,
        library_id=library_id,
        limit=limit,
        search=search,
    )
    filtered_items = _filter_items(items, item_types)

    if not filtered_items:
        raise ZoteroRequestError("No Zotero items matched the current filters.")

    return "\n\n".join(_format_item(item) for item in filtered_items)


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ZoteroConfigError(f"Missing required Zotero setting: {name}")
    return value


def _parse_item_types(raw_value: str) -> set[str]:
    if not raw_value.strip():
        return set(ALLOWED_ITEM_TYPES)
    return {item.strip() for item in raw_value.split(",") if item.strip()}


def _fetch_items(
    *,
    api_key: str,
    library_type: str,
    library_id: str,
    limit: int,
    search: str,
) -> list[dict[str, Any]]:
    url = f"https://api.zotero.org/{library_type}s/{library_id}/items"
    headers = {
        "Zotero-API-Key": api_key,
        "Accept": "application/json",
    }
    params = {
        "limit": min(limit, 100),
        "sort": "dateModified",
        "direction": "desc",
        "format": "json",
    }
    if search:
        params["q"] = search

    response = requests.get(url, headers=headers, params=params, timeout=30)
    if response.status_code >= 400:
        raise ZoteroRequestError(
            f"Zotero API request failed with status {response.status_code}: {response.text[:300]}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ZoteroRequestError("Zotero API did not return valid JSON.") from exc

    if not isinstance(payload, list):
        raise ZoteroRequestError("Unexpected Zotero API response shape.")
    return payload


def _filter_items(items: list[dict[str, Any]], item_types: set[str]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in items:
        data = item.get("data", {})
        if data.get("itemType") not in item_types:
            continue
        if data.get("title"):
            filtered.append(item)
    return filtered


def _format_item(item: dict[str, Any]) -> str:
    data = item.get("data", {})
    creators = "; ".join(_format_creator(creator) for creator in data.get("creators", [])) or "N/A"
    tags = ", ".join(tag.get("tag", "") for tag in data.get("tags", []) if tag.get("tag")) or "N/A"
    notes = _extract_notes(data.get("notes", []))

    fields = [
        f"itemKey: {item.get('key', 'N/A')}",
        f"itemType: {data.get('itemType', 'N/A')}",
        f"title: {data.get('title', 'N/A')}",
        f"creators: {creators}",
        f"date: {data.get('date', 'N/A')}",
        f"publicationTitle: {data.get('publicationTitle', 'N/A')}",
        f"abstractNote: {data.get('abstractNote', 'N/A')}",
        f"DOI: {data.get('DOI', 'N/A')}",
        f"url: {data.get('url', 'N/A')}",
        f"tags: {tags}",
        f"notes: {notes}",
    ]
    return "[Zotero Item]\n" + "\n".join(fields)


def _format_creator(creator: dict[str, Any]) -> str:
    first_name = creator.get("firstName", "").strip()
    last_name = creator.get("lastName", "").strip()
    name = creator.get("name", "").strip()
    creator_type = creator.get("creatorType", "").strip()

    if name:
        display_name = name
    else:
        display_name = " ".join(part for part in (first_name, last_name) if part).strip()

    if creator_type and display_name:
        return f"{display_name} ({creator_type})"
    return display_name or "Unknown"


def _extract_notes(notes: Any) -> str:
    if isinstance(notes, list) and notes:
        return " | ".join(str(note) for note in notes)
    return "N/A"
