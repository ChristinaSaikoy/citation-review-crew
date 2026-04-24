from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ScholarSearchInput(BaseModel):
    query: str = Field(..., description="Search keywords for academic papers")
    api: str = Field(
        default="openalex",
        description="API to use: openalex, semantic_scholar, pubmed, or crossref",
    )


class ScholarSearchTool(BaseTool):
    name: str = "scholar_search"
    description: str = (
        "Search academic papers across multiple APIs. "
        "Use api='openalex' first (best coverage, no rate limit). "
        "Try api='semantic_scholar' for better semantic matching. "
        "Try api='pubmed' for biomedical/chemistry papers. "
        "Use api='crossref' to look up a paper by exact title or DOI. "
        "Vary your query keywords across calls for better results."
    )
    args_schema: Type[BaseModel] = ScholarSearchInput

    def _run(self, query: str, api: str = "openalex") -> str:
        try:
            if api == "openalex":
                return self._search_openalex(query)
            elif api == "semantic_scholar":
                return self._search_semantic_scholar(query)
            elif api == "pubmed":
                return self._search_pubmed(query)
            elif api == "crossref":
                return self._search_crossref(query)
            else:
                return f"Unknown API: {api}. Use openalex, semantic_scholar, pubmed, or crossref."
        except Exception as e:
            return f"Search error ({api}): {e}"

    def _fetch_json(self, url: str, headers: dict | None = None) -> dict:
        hdrs = {"User-Agent": "CitationReviewCrew/1.0 (mailto:crewai@example.com)"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())

    def _search_openalex(self, query: str) -> str:
        params = urllib.parse.urlencode({
            "search": query,
            "per_page": 5,
            "mailto": "crewai@example.com",
            "select": "title,publication_year,doi,cited_by_count,authorships,primary_location,abstract_inverted_index",
        })
        data = self._fetch_json(f"https://api.openalex.org/works?{params}")
        items = data.get("results", [])
        if not items:
            return "No results found on OpenAlex."
        lines = [f"OpenAlex results for: {query}\n"]
        for i, r in enumerate(items, 1):
            title = r.get("title", "?")
            year = r.get("publication_year", "?")
            doi = r.get("doi", "N/A")
            cited = r.get("cited_by_count", 0)
            source = r.get("primary_location", {})
            venue = source.get("source", {}).get("display_name", "?") if source else "?"
            authors = ", ".join(
                a.get("author", {}).get("display_name", "")
                for a in (r.get("authorships") or [])[:4]
            )
            abstract = self._reconstruct_abstract(r.get("abstract_inverted_index"))
            lines.append(f"[{i}] [{year}] {title}")
            lines.append(f"    Journal: {venue}")
            lines.append(f"    Authors: {authors}")
            lines.append(f"    DOI: {doi} | Cited by: {cited}")
            if abstract:
                lines.append(f"    Abstract: {abstract[:300]}...")
            lines.append("")
        return "\n".join(lines)

    def _reconstruct_abstract(self, inv_idx: dict | None) -> str:
        if not inv_idx:
            return ""
        words: dict[int, str] = {}
        for word, positions in inv_idx.items():
            for pos in positions:
                words[pos] = word
        return " ".join(words[i] for i in sorted(words.keys()))

    def _search_semantic_scholar(self, query: str) -> str:
        params = urllib.parse.urlencode({
            "query": query,
            "limit": 5,
            "fields": "title,authors,year,venue,abstract,externalIds,citationCount",
        })
        try:
            data = self._fetch_json(f"https://api.semanticscholar.org/graph/v1/paper/search?{params}")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                return "Semantic Scholar rate limited. Try again later or use a different API."
            raise
        items = data.get("data", [])
        if not items:
            return "No results found on Semantic Scholar."
        lines = [f"Semantic Scholar results for: {query}\n"]
        for i, r in enumerate(items, 1):
            doi = r.get("externalIds", {}).get("DOI", "N/A")
            authors = ", ".join(a.get("name", "") for a in (r.get("authors") or [])[:4])
            abstract = (r.get("abstract") or "")[:300]
            lines.append(f"[{i}] [{r.get('year', '?')}] {r.get('title', '?')}")
            lines.append(f"    Journal: {r.get('venue', '?')}")
            lines.append(f"    Authors: {authors}")
            lines.append(f"    DOI: {doi} | Cited by: {r.get('citationCount', 0)}")
            if abstract:
                lines.append(f"    Abstract: {abstract}...")
            lines.append("")
        return "\n".join(lines)

    def _search_pubmed(self, query: str) -> str:
        params = urllib.parse.urlencode({
            "db": "pubmed", "term": query, "retmax": 5,
            "retmode": "json", "sort": "relevance",
        })
        data = self._fetch_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}")
        ids = data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return "No results found on PubMed."
        time.sleep(0.4)
        params2 = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
        data2 = self._fetch_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{params2}")
        lines = [f"PubMed results for: {query}\n"]
        for idx, uid in enumerate(ids, 1):
            r = data2.get("result", {}).get(uid, {})
            authors = ", ".join(a.get("name", "") for a in (r.get("authors") or [])[:4])
            doi = next((x.get("value") for x in (r.get("articleids") or []) if x.get("idtype") == "doi"), "N/A")
            lines.append(f"[{idx}] [{r.get('pubdate', '?')[:4]}] {r.get('title', '?')}")
            lines.append(f"    Journal: {r.get('fulljournalname', '?')}")
            lines.append(f"    Authors: {authors}")
            lines.append(f"    DOI: {doi}")
            lines.append("")
        return "\n".join(lines)

    def _search_crossref(self, query: str) -> str:
        if query.startswith("10."):
            url = f"https://api.crossref.org/works/{urllib.parse.quote(query, safe='')}"
            data = self._fetch_json(url)
            item = data.get("message", {})
            return self._format_crossref_item(item)
        params = urllib.parse.urlencode({"query": query, "rows": 5, "sort": "relevance"})
        data = self._fetch_json(f"https://api.crossref.org/works?{params}")
        items = data.get("message", {}).get("items", [])
        if not items:
            return "No results found on CrossRef."
        lines = [f"CrossRef results for: {query}\n"]
        for i, item in enumerate(items, 1):
            lines.append(f"[{i}] {self._format_crossref_item(item)}")
            lines.append("")
        return "\n".join(lines)

    def _format_crossref_item(self, item: dict) -> str:
        title = item.get("title", ["?"])[0] if item.get("title") else "?"
        year_obj = item.get("published-print", item.get("published-online", {}))
        year = str(year_obj.get("date-parts", [[None]])[0][0]) if year_obj else "?"
        doi = item.get("DOI", "N/A")
        cited = item.get("is-referenced-by-count", 0)
        journal = item.get("container-title", ["?"])[0] if item.get("container-title") else "?"
        authors = ", ".join(
            f"{a.get('family', '')} {a.get('given', '')}" for a in (item.get("author") or [])[:4]
        )
        return f"[{year}] {title}\n    Journal: {journal}\n    Authors: {authors}\n    DOI: {doi} | Cited by: {cited}"
