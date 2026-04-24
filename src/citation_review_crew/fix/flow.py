from __future__ import annotations

import os
import re
from pathlib import Path

from crewai import Agent, Crew, LLM, Process, Task
from crewai.flow.flow import Flow, and_, listen, start
from pydantic import BaseModel

from citation_review_crew.tools.presearch import (
    batch_presearch,
    format_presearch_results,
    parse_unsupported_claims,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class FixFlowState(BaseModel):
    report_text: str = ""
    reference_list: str = ""
    unsupported_section: str = ""
    partial_section: str = ""
    format_section: str = ""
    suggestions_section: str = ""
    presearch_group1: str = ""
    presearch_group2: str = ""
    presearch_group3: str = ""
    replacement_result_1: str = ""
    replacement_result_2: str = ""
    replacement_result_3: str = ""
    attribution_result: str = ""
    format_result: str = ""


def _llm_strong() -> LLM:
    return LLM(
        model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE"),
        timeout=600,
    )


def _llm_light() -> LLM:
    return LLM(
        model=os.getenv("OPENAI_MODEL_NAME_LIGHT", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE"),
        timeout=300,
    )


def _split_report(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    pattern = re.compile(r"^## (.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        key = m.group(1).strip()
        start_pos = m.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[key] = text[start_pos:end_pos].strip()
    return sections


def _extract_references(docx_path: Path) -> str:
    from citation_review_crew.tools.docx_reader import extract_cited_passages
    full = extract_cited_passages(docx_path)
    marker = "# Reference list"
    idx = full.find(marker)
    if idx >= 0:
        return full[idx:]
    return ""


def _make_verify_crew(group_text: str, group_label: str) -> Crew:
    verifier = Agent(
        role=f"Reference Verifier ({group_label})",
        goal="From the pre-searched candidate papers, select the BEST match for each unsupported claim. Format the replacement in the required citation style.",
        backstory="You are an expert academic editor. You evaluate candidate papers by comparing their title, abstract, and topic against the manuscript claim to find the best replacement reference.",
        llm=_llm_strong(),
        verbose=True,
    )
    task = Task(
        description=(
            f"Below are pre-searched candidate papers for {group_label}.\n"
            "For EACH reference:\n"
            "1. Read the manuscript claim and the problem description\n"
            "2. Examine all candidates (title, journal, abstract, citation count)\n"
            "3. Pick the BEST match. Prefer: high citation count + topic match + recent year\n"
            "4. If NO candidate matches well, mark as MANUAL_NEEDED\n"
            "5. Format the chosen paper in the required citation style\n\n"
            f"PRE-SEARCHED CANDIDATES:\n{group_text}\n\n"
            "Output in Chinese."
        ),
        expected_output=(
            "For each reference, output:\n"
            "| Ref | Claim | Replacement (title, authors, DOI) | Format | Confidence |"
        ),
        agent=verifier,
    )
    return Crew(agents=[verifier], tasks=[task], process=Process.sequential, verbose=True)


class FixFlow(Flow[FixFlowState]):

    @start()
    def parse_and_presearch(self):
        report_path = PROJECT_ROOT / "report.md"
        self.state.report_text = report_path.read_text(encoding="utf-8")
        docx_files = sorted(PROJECT_ROOT.glob("*.docx"))
        if docx_files:
            self.state.reference_list = _extract_references(docx_files[0])
        sections = _split_report(self.state.report_text)
        for key, val in sections.items():
            if "Unsupported" in key:
                self.state.unsupported_section = val
            elif "Partially" in key:
                self.state.partial_section = val
            elif "Format" in key:
                self.state.format_section = val
            elif "Suggested" in key:
                self.state.suggestions_section = val
        print("=== Phase 1: Python pre-search ===")
        issues = parse_unsupported_claims(self.state.report_text)
        print(f"Found {len(issues)} unsupported references to search")
        issues = batch_presearch(issues)
        total_candidates = sum(len(i.candidates) for i in issues)
        print(f"Pre-search complete: {total_candidates} total candidates")
        n = len(issues)
        s1, s2 = n // 3, 2 * n // 3
        g1 = issues[:s1] if s1 > 0 else issues[:1]
        g2 = issues[s1:s2] if s2 > s1 else issues[1:2]
        g3 = issues[s2:] if s2 < n else issues[2:]
        self.state.presearch_group1 = format_presearch_results(g1)
        self.state.presearch_group2 = format_presearch_results(g2)
        self.state.presearch_group3 = format_presearch_results(g3)
        print(f"Split into 3 groups: {len(g1)}, {len(g2)}, {len(g3)} refs")

    @listen(parse_and_presearch)
    def verify_group1(self):
        try:
            result = _make_verify_crew(self.state.presearch_group1, "Group 1").kickoff()
            self.state.replacement_result_1 = result.raw
        except Exception as e:
            self.state.replacement_result_1 = f"Group 1 failed: {e}"

    @listen(parse_and_presearch)
    def verify_group2(self):
        try:
            result = _make_verify_crew(self.state.presearch_group2, "Group 2").kickoff()
            self.state.replacement_result_2 = result.raw
        except Exception as e:
            self.state.replacement_result_2 = f"Group 2 failed: {e}"

    @listen(parse_and_presearch)
    def verify_group3(self):
        try:
            result = _make_verify_crew(self.state.presearch_group3, "Group 3").kickoff()
            self.state.replacement_result_3 = result.raw
        except Exception as e:
            self.state.replacement_result_3 = f"Group 3 failed: {e}"

    @listen(parse_and_presearch)
    def run_crew_b(self):
        try:
            corrector = Agent(
                role="Text Correction Specialist",
                goal="Generate precise text correction instructions for author name misattributions and data source errors.",
                backstory="You are an academic proofreader specializing in author name errors and data attribution mistakes.",
                llm=_llm_light(), verbose=True,
            )
            task = Task(
                description=(
                    "Extract all author attribution errors and data source corrections.\n\n"
                    f"PARTIALLY SUPPORTED CLAIMS:\n{self.state.partial_section}\n\n"
                    f"SUGGESTED FIXES:\n{self.state.suggestions_section}\n\n"
                    "Output: location, current text, corrected text. Output in Chinese."
                ),
                expected_output="| Location | Current | Corrected | Type |",
                agent=corrector,
            )
            result = Crew(agents=[corrector], tasks=[task], process=Process.sequential, verbose=True).kickoff()
            self.state.attribution_result = result.raw
        except Exception as e:
            self.state.attribution_result = f"Crew B failed: {e}"

    @listen(parse_and_presearch)
    def run_crew_c(self):
        try:
            checker = Agent(
                role="Citation Format Checker",
                goal="Check every reference entry against citation format standards and produce corrected versions.",
                backstory="You are an expert in academic thesis formatting standards.",
                llm=_llm_light(), verbose=True,
            )
            task = Task(
                description=(
                    f"FORMAT VIOLATIONS:\n{self.state.format_section}\n\n"
                    f"REFERENCE LIST:\n{self.state.reference_list}\n\n"
                    "Check format violations and scan the full reference list for additional issues. "
                    "Output: original entry, violation type, corrected entry. Output in Chinese."
                ),
                expected_output="| Ref | Original | Violation | Corrected |",
                agent=checker,
            )
            result = Crew(agents=[checker], tasks=[task], process=Process.sequential, verbose=True).kickoff()
            self.state.format_result = result.raw
        except Exception as e:
            self.state.format_result = f"Crew C failed: {e}"

    @listen(and_(verify_group1, verify_group2, verify_group3, run_crew_b, run_crew_c))
    def merge_results(self):
        replacement = f"{self.state.replacement_result_1}\n\n{self.state.replacement_result_2}\n\n{self.state.replacement_result_3}"
        output = (
            "# Reference Corrections Report\n\n---\n\n"
            f"## 1. Reference Replacements\n\n{replacement}\n\n---\n\n"
            f"## 2. Author/Data Corrections\n\n{self.state.attribution_result}\n\n---\n\n"
            f"## 3. Format Corrections\n\n{self.state.format_result}\n\n---\n\n"
            "*Generated by CitationReviewCrew FixFlow*\n"
        )
        (PROJECT_ROOT / "corrections.md").write_text(output, encoding="utf-8")
        print(f"Corrections written ({len(output)} chars)")
        return output
