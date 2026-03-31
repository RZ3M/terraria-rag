# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Terraria RAG is a local-first Retrieval Augmented Generation system for the Terraria wiki, designed as an intelligent NPC companion mod for tModLoader. It ingests the Terraria wiki (~3,700 pages), chunks and embeds content into Qdrant (local vector DB), and generates spoiler-aware in-game hints via LLM.

## Commands

### Setup
```bash
./SCRIPTS/setup_qdrant.sh          # Download and start Qdrant on localhost:6333
pip install -r requirements.txt
./SCRIPTS/download_embeddings.sh   # Download all-MiniLM-L6-v2 (~100 MB)
cp .env.example .env               # Then add MINIMAX_API_KEY / OPENROUTER_API_KEY
```

### Ingestion
```bash
python INGESTION/run_ingestion.py                        # Resume from checkpoint
python INGESTION/run_ingestion.py --no-resume            # Full re-ingest from scratch
python INGESTION/run_ingestion.py --preview --limit 10   # Preview without indexing
python INGESTION/run_ingestion.py --fetch-mode html --re-ingest  # Re-ingest with HTML (needed for crafting recipes)
python INGESTION/run_ingestion.py --verbose
```

### Chatbot / Query
```bash
python CHATBOT/cli.py                          # Interactive chatbot
python CHATBOT/cli.py --game-state             # With game state filtering
python CHATBOT/cli.py --provider openrouter    # Use OpenRouter instead of Minimax
python CHATBOT/cli.py --verbose                # Show source chunks and scores
```

### Tests
```bash
pytest TESTS/ -v
pytest TESTS/test_chunker.py -v   # Run a specific test file

# Retrieval quality evaluation (no LLM needed)
python3 TESTS/eval_retrieval.py
python3 TESTS/eval_retrieval.py --compare DATA/eval_baseline.json   # compare to baseline
python3 TESTS/eval_retrieval.py --category crafting                 # run one category
```

## Architecture

```
COMMON/          # Shared infrastructure
INGESTION/       # Wiki fetch → parse → chunk → embed → index pipeline
QUERY/           # Retrieval + prompt construction + LLM generation
CHATBOT/         # Interactive CLI interface
MOD/             # tModLoader C# stubs (incomplete)
DATA/            # Storage: raw_pages/ (cached JSON), chunks/ (JSONL), ingestion_state.json
SCRIPTS/         # Setup and utility shell scripts
TESTS/           # pytest tests
```

### Ingestion Pipeline

```
terraria.wiki.gg (MediaWiki API)
  → fetcher.py (cached in DATA/raw_pages/)
  → parser.py (wikitext) or parser_html.py (rendered HTML)
  → chunker.py (~512 token max, 50-token overlap, heading-aware)
  → embedder.py (sentence-transformers, 384-dim)
  → indexer.py (Qdrant upsert + DATA/ingestion_state.json checkpoint)
```

### Query Pipeline

```
User query
  → embed_single() — same model as ingestion
  → retriever.py — vector search + keyword boosting + section quality re-ranking
  → prompter.py — format chunks + game state into prompt
  → LLM (Minimax M2.7 or OpenRouter)
```

### Key Design Decisions

- **Singleton pattern** for Qdrant client and embedding model — see `get_qdrant_client()` / `get_embedding_model()`
- **All config in one place**: `COMMON/config.py` — API keys, model names, chunk sizes, retrieval thresholds
- **Two fetch modes**: `wikitext` (fast, default) and `html` (slow, needed for crafting recipes — wikitext templates are unexpanded)
- **Retrieval uses multi-signal approach**: direct item-name matching, semantic expansion, section quality re-ranking (Crafting sections boosted; References penalized)
- **Game state filtering** via Qdrant payload metadata: `category`, `game_mode`, `obtain_method`, etc.
- **Resume-safe ingestion**: `DATA/ingestion_state.json` tracks processed pages; `--no-resume` resets

### Key Retrieval Knobs (COMMON/config.py)
- `TOP_K = 10` — vectors fetched from Qdrant
- `RETRIEVE_K = 5` — chunks passed to LLM
- `RETRIEVAL_SCORE_THRESHOLD = 0.3` — minimum cosine similarity

## Current State

- **3,671 pages indexed, 22,005 chunks** in Qdrant collection `terraria_wiki` (HTML mode, includes crafting recipes)
- Eval results (TESTS/eval_retrieval.py): recall@5=81.8%, content-recall@5=95.5%, MRR=0.629
- Retrieval pipeline: bi-encoder (all-MiniLM-L6-v2) → section quality → cross-encoder reranker
- MOD/ (tModLoader C#) is stub-only; Milestone 4 is ~20% complete
- `TESTS/test_chunker.py` has 2 pre-existing failures (wrong expected values for `_estimate_tokens`); 6/8 tests pass

## Known Issues

- `_estimate_tokens` test assertions are wrong (use `len(text)//4`; tests expect 1/4 of actual values) — pre-existing, don't fix
- Category queries ("best pre-hardmode bows", "first boss") fail title recall — need guide/progression pages or multi-document aggregation
- `game_mode` metadata inference only works for items with explicit "is a Hardmode" text in the first 5 sections; boss pages often get `[]`
