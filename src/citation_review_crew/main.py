#!/usr/bin/env python
import json
import os
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

from citation_review_crew.crew import CitationReviewCrew
from citation_review_crew.tools.docx_reader import extract_cited_passages
from citation_review_crew.tools.zotero_tool import (
    ZoteroConfigError,
    ZoteroRequestError,
    fetch_zotero_citations,
    zotero_is_configured,
)

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CITATIONS = "[Citation 1] Title: Example reference. Key finding: Replace this with your actual cited reference content."
DEFAULT_INSERTED_CONTENT = "Replace this with the manuscript content you inserted and want to verify against the cited references."


def _read_optional_text(filename: str, fallback: str) -> str:
    path = PROJECT_ROOT / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return fallback


def _find_docx() -> str | None:
    docx_files = sorted(PROJECT_ROOT.glob("*.docx"))
    if not docx_files:
        return None
    chosen = docx_files[0]
    print(f"Reading manuscript from: {chosen.name}")
    result = extract_cited_passages(chosen)
    char_count = len(result)
    print(f"Extracted {char_count} chars (cited passages + references)")
    return result


def _load_citations() -> str:
    if zotero_is_configured():
        try:
            return fetch_zotero_citations()
        except (ZoteroConfigError, ZoteroRequestError) as exc:
            print(f"Zotero load failed, falling back to citations.txt: {exc}")
    return _read_optional_text("citations.txt", DEFAULT_CITATIONS)


def _load_manuscript() -> str:
    env_val = os.getenv("CITATION_REVIEW_INSERTED_CONTENT")
    if env_val:
        return env_val
    docx_content = _find_docx()
    if docx_content:
        return docx_content
    return _read_optional_text("inserted_content.txt", DEFAULT_INSERTED_CONTENT)


def _build_inputs() -> dict[str, str]:
    citations = os.getenv("CITATION_REVIEW_CITATIONS") or _load_citations()
    inserted_content = _load_manuscript()
    return {
        "citations": citations,
        "inserted_content": inserted_content,
    }


def run():
    try:
        return CitationReviewCrew().crew().kickoff(inputs=_build_inputs())
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def fix():
    from citation_review_crew.fix.flow import FixFlow

    report_path = PROJECT_ROOT / "report.md"
    if not report_path.exists():
        raise FileNotFoundError(
            f"report.md not found at {report_path}. Run 'crewai run' first to generate it."
        )
    print(f"Starting FixFlow from {report_path}")
    flow = FixFlow()
    result = flow.kickoff()
    print("FixFlow complete. Output: corrections.md")
    return result


def train():
    try:
        CitationReviewCrew().crew().train(
            n_iterations=int(sys.argv[1]),
            filename=sys.argv[2],
            inputs=_build_inputs(),
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    try:
        CitationReviewCrew().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    try:
        CitationReviewCrew().crew().test(
            n_iterations=int(sys.argv[1]),
            eval_llm=sys.argv[2],
            inputs=_build_inputs(),
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
