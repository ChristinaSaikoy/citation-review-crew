# Citation Review Crew

[![CI](https://github.com/ChristinaSaikoy/citation-review-crew/actions/workflows/ci.yml/badge.svg)](https://github.com/ChristinaSaikoy/citation-review-crew/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10--3.13-blue.svg)](pyproject.toml)

**English** | [中文](README_CN.md)

A research-oriented pipeline for auditing manuscript citations, finding candidate replacement literature, and producing structured correction reports.

Instead of asking one LLM to read an entire manuscript and improvise replacements, Citation Review Crew separates deterministic preprocessing and academic search from agent-based verification.

## What / Why / Current Result

**What** — Extract citation-bearing passages from `.docx` manuscripts, compare them with reference metadata, search academic APIs for better sources, and generate an actionable correction report.

**Why** — Citation review is not just a text-generation problem. It requires traceable source retrieval, claim-to-reference matching, attribution checks, formatting checks, and explicit handling of uncertain replacements.

**Current result** — The repository contains an end-to-end review/fix pipeline, Zotero integration, multi-source academic search, parallel verification flows, and offline-tested DOCX citation extraction. CI validates the offline core on Python 3.10–3.13.

## Pipeline

```text
Manuscript (.docx) + Zotero / citation metadata
                    |
                    v
        Citation-bearing passage extraction
                    |
                    v
          Review Crew -> report.md
                    |
                    v
      Parse unsupported / partial claims
                    |
                    v
 Python pre-search across academic APIs
                    |
       +------------+------------+
       |            |            |
       v            v            v
 Verify group 1  Verify group 2  Verify group 3
       |            |            |
       +------------+------------+
                    |
          +---------+---------+
          |                   |
          v                   v
 Attribution correction   Format checking
          |                   |
          +---------+---------+
                    |
                    v
             corrections.md
```

## Design Principles

- **Deterministic preprocessing first** — only citation-bearing manuscript passages are extracted before review.
- **Search before generation** — replacement candidates come from academic search APIs rather than being invented by the model.
- **Human-verifiable outputs** — candidate replacements include bibliographic information and can be marked `MANUAL_NEEDED` when confidence is insufficient.
- **Failure isolation** — verification and correction branches are separated so one failed branch does not have to invalidate every output.
- **Offline-testable core** — document parsing is tested without LLM credentials or network access.

## Main Components

| Component | Responsibility |
|---|---|
| `tools/docx_reader.py` | Extract citation-bearing paragraphs and reference sections from `.docx` manuscripts |
| `tools/zotero_tool.py` | Load citation metadata from Zotero |
| `tools/scholar_search.py` | Search academic literature sources |
| `tools/presearch.py` | Parse unsupported claims and pre-search candidate replacements |
| `crew.py` | Primary citation review crew |
| `fix/flow.py` | Parallel replacement verification, attribution correction, format checking, and result merge |

## Academic Search Sources

The search layer supports multiple sources with different roles:

- **OpenAlex** — broad scholarly metadata retrieval
- **Semantic Scholar** — semantic paper search and metadata
- **PubMed** — biomedical literature
- **Crossref** — DOI and publication metadata lookup

Replacement candidates are searched first and then passed to verification agents for claim-level matching.

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/ChristinaSaikoy/citation-review-crew.git
cd citation-review-crew
uv sync
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Configure the providers you plan to use:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | LLM provider authentication |
| `OPENAI_API_BASE` | Optional OpenAI-compatible API endpoint |
| `OPENAI_MODEL_NAME` | Strong model used for reference verification |
| `OPENAI_MODEL_NAME_LIGHT` | Lighter model used for auxiliary correction tasks |
| `ZOTERO_API_KEY` | Zotero library access |
| `ZOTERO_LIBRARY_ID` | Zotero library identifier |

### 3. Run the review phase

Place a manuscript `.docx` in the repository root, then run:

```bash
uv run crewai run
```

The review phase produces `report.md`.

### 4. Run the correction phase

```bash
uv run fix
```

The fix flow parses the review report, searches candidate literature, runs parallel verification/correction branches, and writes `corrections.md`.

### 5. Optional Zotero import

```bash
uv run python src/citation_review_crew/tools/zotero_import.py
```

## Offline Tests

The CI suite deliberately tests logic that does **not** require paid APIs, LLM credentials, or network access.

```bash
python -m pip install python-docx
PYTHONPATH=src python -m unittest discover -s tests -v
```

Current offline coverage includes:

- DOCX paragraph reading
- citation-bearing paragraph filtering
- chapter preservation
- reference-section extraction

GitHub Actions also compiles the complete `src/` tree and runs the unit tests on Python 3.10, 3.11, 3.12, and 3.13.

## Repository Layout

```text
citation-review-crew/
├── .github/workflows/ci.yml
├── src/citation_review_crew/
│   ├── config/
│   ├── fix/
│   │   └── flow.py
│   ├── tools/
│   │   ├── docx_reader.py
│   │   ├── presearch.py
│   │   ├── scholar_search.py
│   │   ├── zotero_import.py
│   │   └── zotero_tool.py
│   ├── crew.py
│   └── main.py
├── tests/
│   └── test_docx_reader.py
├── .env.example
├── pyproject.toml
├── LICENSE
└── README.md
```

## Limitations

- Full review and correction runs depend on external APIs and LLM behavior; they are not equivalent to deterministic unit tests.
- Candidate search quality is bounded by the coverage and metadata quality of the configured scholarly APIs.
- A high-confidence automated suggestion should still be checked against the original paper before publication.
- Citation-style rules are configurable and may require adaptation to a journal, university, or discipline-specific standard.
- Reproducible end-to-end benchmark data is not yet published in this repository; performance claims should therefore be treated as unverified until a benchmark harness is added.

## Roadmap

- Add deterministic tests for report parsing and candidate pre-search formatting
- Mock external scholarly APIs for integration tests
- Add a reproducible benchmark corpus with precision/recall-style review metrics
- Add structured JSON outputs alongside Markdown reports
- Add versioned releases once the evaluation protocol is stable

## License

MIT License. See [LICENSE](LICENSE).
