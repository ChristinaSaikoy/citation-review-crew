# Citation Review Crew

**English** | [中文](README_CN.md)

A CrewAI-powered tool that automatically reviews academic paper citations for accuracy, identifies mismatched references, searches for correct replacements, and checks citation format compliance.

## What It Does

1. **Review Phase** (`crewai run`): Reads your manuscript (.docx) and reference metadata (Zotero API), then generates a review report identifying:
   - Unsupported claims (reference doesn't match the claim)
   - Author attribution errors
   - Citation format violations
   - Duplicate references

2. **Fix Phase** (`uv run fix`): Takes the review report and automatically:
   - Searches for correct replacement references via OpenAlex, Semantic Scholar, PubMed, and CrossRef APIs
   - Verifies replacements using parallel AI agents
   - Generates author name corrections
   - Produces format compliance fixes
   - Outputs an actionable correction checklist

## Architecture

```
Phase 1: Review (crewai run)
  docx_reader ─── extract cited passages by chapter
  zotero_tool ─── fetch reference metadata
       └──> 2-Agent Crew (review + report) ──> report.md

Phase 2: Fix (uv run fix)
  ┌─────────────────────────────────────────────────┐
  │          parse_and_presearch()                   │
  │  Parse report.md ──> Python batch API search     │
  │  (OpenAlex + Semantic Scholar, ~10 seconds)      │
  └──────────┬──────────┬──────────┬────────────────┘
   ┌─────────▼──┐ ┌─────▼──────┐ ┌▼─────────────┐
   │ Group 1    │ │ Group 2    │ │ Group 3      │  3x parallel
   │ Verify     │ │ Verify     │ │ Verify       │  verification
   └──────┬─────┘ └─────┬──────┘ └──────┬───────┘
   ┌──────▼───────────▼───────────────▼───────┐
   │  + Crew B (author corrections)                │  parallel
   │  + Crew C (format checks)                     │
   └──────────────────┬─────────────────────────┘
                      ▼
              corrections.md
```

## Key Features

- **Smart Input Reduction**: Extracts only paragraphs with citation markers `[N]` from the manuscript, reducing input from ~87K to ~17K chars (5x compression)
- **Multi-API Academic Search**: OpenAlex (primary, no rate limit) + Semantic Scholar (semantic matching) + PubMed (biomedical) + CrossRef (DOI lookup)
- **Python Pre-search + AI Verification**: Batch searches via free APIs (~10 seconds), then AI agents verify matches in parallel (~2 minutes total vs 10+ minutes for pure AI search)
- **Fault Tolerant**: Each crew runs in try/except - if one fails, others still produce output
- **Zotero Integration**: Auto-imports replacement papers into your Zotero library with tags for easy filtering

## Setup

```bash
uv tool install crewai
git clone https://github.com/ChristinaSaikoy/citation-review-crew.git
cd citation-review-crew
cp .env.example .env  # Edit with your API keys
uv sync
```

### Required API Keys

| Key | Source | Purpose |
|-----|--------|---------|
| `OPENAI_API_KEY` | Your LLM provider | AI agents |
| `OPENAI_API_BASE` | Your LLM provider | API endpoint |
| `ZOTERO_API_KEY` | [Zotero Settings](https://www.zotero.org/settings/keys) | Fetch references |
| `ZOTERO_LIBRARY_ID` | Zotero Settings | Your library |

## Usage

### Step 1: Review

Place your `.docx` manuscript in the project root, then:

```bash
uv run crewai run
```

### Step 2: Fix

```bash
uv run fix
```

### Step 3: Import to Zotero (optional)

```bash
uv run python src/citation_review_crew/tools/zotero_import.py
```

## Customization

- **Citation format**: Edit `src/citation_review_crew/config/tasks.yaml`
- **Models**: Set `OPENAI_MODEL_NAME` and `OPENAI_MODEL_NAME_LIGHT` in `.env`
- **Search APIs**: `scholar_search.py` supports openalex, semantic_scholar, pubmed, crossref

## License

MIT
