"""Batch pre-search for replacement references using free academic APIs."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field


@dataclass
class CandidatePaper:
    title: str
    authors: str
    year: str
    journal: str
    doi: str
    cited_by: int
    abstract: str = ""
    source_api: str = ""


@dataclass
class RefIssue:
    ref_num: int
    claim: str
    problem: str
    queries: list[str] = field(default_factory=list)
    candidates: list[CandidatePaper] = field(default_factory=list)


def _fetch_json(url: str, timeout: int = 15) -> dict:
    headers = {"User-Agent": "CitationReviewCrew/1.0 (mailto:crewai@example.com)"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _search_openalex(query: str, limit: int = 5) -> list[CandidatePaper]:
    params = urllib.parse.urlencode({
        "search": query, "per_page": limit, "mailto": "crewai@example.com",
        "select": "title,publication_year,doi,cited_by_count,authorships,primary_location,abstract_inverted_index",
    })
    try:
        data = _fetch_json(f"https://api.openalex.org/works?{params}")
    except Exception:
        return []
    results = []
    for r in data.get("results", []):
        authors = ", ".join(
            a.get("author", {}).get("display_name", "")
            for a in (r.get("authorships") or [])[:4]
        )
        source = r.get("primary_location") or {}
        venue_src = source.get("source") or {}
        venue = venue_src.get("display_name", "?")
        inv_idx = r.get("abstract_inverted_index")
        abstract = ""
        if inv_idx:
            words: dict[int, str] = {}
            for word, positions in inv_idx.items():
                for pos in positions:
                    words[pos] = word
            abstract = " ".join(words[i] for i in sorted(words.keys()))
        results.append(CandidatePaper(
            title=r.get("title", "?"),
            authors=authors,
            year=str(r.get("publication_year", "?")),
            journal=venue,
            doi=r.get("doi", "N/A"),
            cited_by=r.get("cited_by_count", 0),
            abstract=abstract[:300],
            source_api="openalex",
        ))
    return results


def _search_semantic_scholar(query: str, limit: int = 5) -> list[CandidatePaper]:
    params = urllib.parse.urlencode({
        "query": query, "limit": limit,
        "fields": "title,authors,year,venue,abstract,externalIds,citationCount",
    })
    try:
        data = _fetch_json(f"https://api.semanticscholar.org/graph/v1/paper/search?{params}")
    except Exception:
        return []
    results = []
    for r in data.get("data", []):
        authors = ", ".join(a.get("name", "") for a in (r.get("authors") or [])[:4])
        doi = r.get("externalIds", {}).get("DOI", "N/A")
        results.append(CandidatePaper(
            title=r.get("title", "?"),
            authors=authors,
            year=str(r.get("year", "?")),
            journal=r.get("venue", "?"),
            doi=doi,
            cited_by=r.get("citationCount", 0),
            abstract=(r.get("abstract") or "")[:300],
            source_api="semantic_scholar",
        ))
    return results


def _build_queries(issue: RefIssue) -> list[str]:
    """Build multiple query variations from the issue context."""
    queries = []
    claim = issue.claim
    problem = issue.problem

    keywords = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", claim + " " + problem)
    unique_kw = list(dict.fromkeys(keywords))[:8]

    if unique_kw:
        queries.append(" ".join(unique_kw[:6]))

    for phrase in [
        "review", "comprehensive review", "toxicity review",
        "electrochemical sensor", "detection method",
    ]:
        if phrase.split()[0].lower() in (claim + problem).lower():
            queries.append(" ".join(unique_kw[:4]) + " " + phrase)
            break

    specific_terms = re.findall(
        r"(?:HPLC|fluorescence|nitrite|glucose|hollow|nanostructure|water splitting|"
        r"methemoglobin|carcinogen|NiO|CuO|Co3O4|CuS|electrochemical|sensor|"
        r"template|synthesis|review|IDF|diabetes)",
        claim + " " + problem, re.IGNORECASE
    )
    if specific_terms:
        queries.append(" ".join(dict.fromkeys(specific_terms)))

    return list(dict.fromkeys(queries))[:5]


def parse_unsupported_claims(report_text: str) -> list[RefIssue]:
    """Extract unsupported claims from report sections."""
    issues: list[RefIssue] = []

    section_pattern = re.compile(
        r"##\s+(?:四|七).*?(?=\n##\s|\Z)", re.DOTALL
    )
    sections = section_pattern.findall(report_text)
    full_text = "\n".join(sections)

    row_pattern = re.compile(
        r"\|\s*\*?\*?(\d+)\*?\*?\s*\|\s*"
        r"(?:\[(\d+(?:,\s*\d+)*)\])?\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|"
    )
    for m in row_pattern.finditer(full_text):
        ref_match = re.findall(r"\[(\d+)\]", m.group(0))
        ref_num = int(ref_match[0]) if ref_match else int(m.group(1))
        claim = m.group(3).strip()
        problem = m.group(5).strip()
        if any(skip in claim.lower() for skip in ["序号", "稿件", "location", "---"]):
            continue
        issues.append(RefIssue(ref_num=ref_num, claim=claim, problem=problem))

    suggestion_pattern = re.compile(
        r"(\d+)\.\s*\*\*替换文献\[(\d+)\]\*\*[：:]\s*(.+?)(?=\n\d+\.\s|\n###|\n---|\Z)",
        re.DOTALL
    )
    for m in suggestion_pattern.finditer(full_text):
        ref_num = int(m.group(2))
        suggestion = m.group(3).strip()
        existing = next((i for i in issues if i.ref_num == ref_num), None)
        if existing:
            existing.problem += " " + suggestion
        else:
            issues.append(RefIssue(ref_num=ref_num, claim=suggestion, problem=suggestion))

    seen = set()
    deduped = []
    for issue in issues:
        if issue.ref_num not in seen:
            seen.add(issue.ref_num)
            deduped.append(issue)
    return deduped


def batch_presearch(issues: list[RefIssue], delay: float = 0.3) -> list[RefIssue]:
    """Run batch searches for all issues across multiple APIs."""
    print(f"Pre-searching {len(issues)} references...")
    for i, issue in enumerate(issues):
        issue.queries = _build_queries(issue)
        print(f"  [{issue.ref_num}] {len(issue.queries)} queries: {issue.queries[:2]}...")

        seen_titles: set[str] = set()
        for q in issue.queries:
            for paper in _search_openalex(q, limit=5):
                key = paper.title.lower()[:60]
                if key not in seen_titles:
                    seen_titles.add(key)
                    issue.candidates.append(paper)
            time.sleep(delay)

        if len(issue.candidates) < 5 and issue.queries:
            for paper in _search_semantic_scholar(issue.queries[0], limit=5):
                key = paper.title.lower()[:60]
                if key not in seen_titles:
                    seen_titles.add(key)
                    issue.candidates.append(paper)
            time.sleep(1.5)

        issue.candidates.sort(key=lambda p: p.cited_by, reverse=True)
        issue.candidates = issue.candidates[:15]
        print(f"  [{issue.ref_num}] Found {len(issue.candidates)} candidates "
              f"(top cited: {issue.candidates[0].cited_by if issue.candidates else 0})")

    return issues


def format_presearch_results(issues: list[RefIssue]) -> str:
    """Format pre-search results as text for the verification Agent."""
    lines: list[str] = []
    for issue in issues:
        lines.append(f"### Reference [{issue.ref_num}]")
        lines.append(f"Claim: {issue.claim}")
        lines.append(f"Problem: {issue.problem}")
        lines.append(f"Candidates ({len(issue.candidates)}):")
        for j, c in enumerate(issue.candidates, 1):
            lines.append(f"  {j}. [{c.year}] {c.title}")
            lines.append(f"     {c.journal} | {c.authors}")
            lines.append(f"     DOI: {c.doi} | Cited: {c.cited_by}")
            if c.abstract:
                lines.append(f"     Abstract: {c.abstract[:200]}...")
        lines.append("")
    return "\n".join(lines)
