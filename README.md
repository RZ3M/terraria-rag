# Terraria RAG System

A local-first Retrieval Augmented Generation (RAG) system for the Terraria wiki, designed for real-time in-game hint generation via a tModLoader mod integration.

## What This Does

1. **Ingest** the entire Terraria wiki (`terraria.wiki.gg`) via the MediaWiki HTML API (fully rendered — templates, crafting recipes included)
2. **Chunk & embed** wiki content using local sentence-transformer models
3. **Store** embeddings in Qdrant (local vector database)
4. **Query** at runtime with game-state-aware filtering, section quality re-ranking, and cross-encoder reranking to retrieve relevant context
5. **Generate** contextual hints using Minimax M2.7 or OpenRouter LLMs

The primary use case is an intelligent NPC companion inside Terraria that detects player game state and offers progression-appropriate hints — without spoilers.

## Current State (2026-03-31)

- **3,671 pages indexed, 22,005 chunks** in Qdrant (`terraria_wiki` collection)
- **Retrieval quality:** recall@5=81.8%, content-recall@5=95.5%, MRR=0.629
- Crafting recipes, item stats, boss drops all included via HTML ingestion
- Cross-encoder reranker active for precision ranking

## Project Layout

```
terraria-rag/
├── COMMON/          # Shared: config, types, Qdrant client, embedding model
├── INGESTION/       # Fetch → Parse → Chunk → Embed → Index
├── QUERY/           # Retrieve → Re-rank → Prompt → Generate
├── CHATBOT/         # Standalone CLI query interface
├── MOD/             # tModLoader integration stubs (C#)
├── DATA/            # raw_pages/, chunks/, ingestion_state.json, eval results
├── SCRIPTS/         # setup_qdrant.sh, download_embeddings.sh
└── TESTS/           # Unit tests + retrieval quality evaluation
```

See [SPEC.md](SPEC.md) for full architecture and design decisions.

## Quick Start

### Prerequisites

- Python 3.10+
- Qdrant binary (see below)
- ~10 GB disk space for full wiki ingestion

### 1. Setup Qdrant

```bash
./SCRIPTS/setup_qdrant.sh
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Download Embedding Models

```bash
./SCRIPTS/download_embeddings.sh
```

### 4. Configure API Keys

```bash
cp .env.example .env
# Add MINIMAX_API_KEY and/or OPENROUTER_API_KEY
```

### 5. Run Ingestion

```bash
python INGESTION/run_ingestion.py
```

Default mode is `--fetch-mode html` (fully rendered — includes crafting recipes). First run fetches from the wiki and caches pages locally. Resume is supported — restarting picks up where it left off.

To re-ingest from scratch:
```bash
python INGESTION/run_ingestion.py --no-resume
```

### 6. Query

```bash
python CHATBOT/cli.py
python CHATBOT/cli.py --game-state     # with game state filtering
python CHATBOT/cli.py --verbose        # show source chunks and scores
```

## Configuration

All configuration lives in `COMMON/config.py`. Key settings:

| Variable | Default | Description |
|---|---|---|
| `QDRANT_HOST` | `localhost` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant HTTP port |
| `COLLECTION_NAME` | `terraria_wiki` | Qdrant collection |
| `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | sentence-transformer model (384d, 256-token limit) |
| `CHUNK_MAX_TOKENS` | `200` | Max tokens per chunk (aligned to model capacity) |
| `CHUNK_OVERLAP_TOKENS` | `50` | Overlap between chunks |
| `TOP_K` | `10` | Vectors to retrieve from Qdrant |
| `RETRIEVE_K` | `5` | Chunks passed to LLM (after reranking) |
| `RETRIEVAL_SCORE_THRESHOLD` | `0.4` | Minimum cosine similarity |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder for precision reranking |
| `MINIMAX_API_KEY` | env var | Primary LLM |
| `OPENROUTER_API_KEY` | env var | Fallback LLM |

## Retrieval Pipeline

```
Query
  → bi-encoder embed (all-MiniLM-L6-v2)
  → Qdrant vector search (top 30 candidates)
    + direct item name search (capitalized terms from query)
  → section quality re-ranking (Crafting/Tips boosted, References/History penalized)
  → cross-encoder reranker (ms-marco-MiniLM-L-6-v2) → top 5
  → LLM prompt + generation
```

## Game State Filtering

Chunks are tagged with metadata during ingestion:

- `category` — Weapons, Armor, Ores, Potions, Town NPCs, Bosses, Accessories, Biomes, Blocks
- `subcategory` — Melee, Ranged, Magic, Summon, Throwing (for Weapons)
- `game_mode` — Pre-Hardmode, Hardmode, Post-Moon Lord (inferred from page content)
- `obtain_method` — Crafting, Drop, Purchase, Fishing

```python
from QUERY.query_engine import query
from COMMON.types import GameState

result = query(
    "What's a good weapon for this stage?",
    game_state=GameState(is_hardmode=True, armor_tier="Hallowed"),
)
print(result.llm_response)
```

## Evaluation

```bash
# Run retrieval quality evaluation (no LLM needed)
python TESTS/eval_retrieval.py

# Compare against a saved baseline
python TESTS/eval_retrieval.py --compare DATA/eval_baseline.json

# Run only one category of test cases
python TESTS/eval_retrieval.py --category crafting
```

The golden test set is in `TESTS/eval_queries.py` (22 cases across 7 categories).

## Testing

```bash
pytest TESTS/ -v
```

Note: 2 tests in `test_chunker.py` have pre-existing wrong expected values for `_estimate_tokens` and will always fail — all other tests pass.

## License

MIT — do whatever, credit is nice but not required.
