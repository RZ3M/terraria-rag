# Terraria RAG System 🦀

A local-first Retrieval Augmented Generation (RAG) system for the Terraria wiki, designed for real-time in-game hint generation via a tModLoader mod integration.

## What This Does

1. **Ingest** the entire Terraria wiki (`terraria.wiki.gg`) via the MediaWiki API
2. **Chunk & embed** wiki content using local sentence-transformer models
3. **Store** embeddings in Qdrant (local vector database)
4. **Query** at runtime with game-state-aware filtering to retrieve relevant context
5. **Generate** contextual hints using Minimax M2.7 or OpenRouter LLMs

The primary use case is an intelligent NPC companion inside Terraria that detects player game state and offers progression-appropriate hints — without spoilers.

## Project Layout

```
terraria-rag/
├── COMMON/          # Shared: config, types, Qdrant client, embedding model
├── INGESTION/      # Fetch → Parse → Chunk → Embed → Index
├── QUERY/           # Retrieve → Re-rank → Prompt → Generate
├── CHATBOT/         # Standalone CLI query interface
├── MOD/             # tModLoader integration stubs (C#)
├── DATA/            # raw_pages/, chunks/, ingestion_state.json
├── SCRIPTS/         # setup_qdrant.sh, download_embeddings.sh
└── TESTS/           # Unit & integration tests
```

See [SPEC.md](SPEC.md) for full architecture, design decisions, and implementation phases.

## Quick Start

### Prerequisites

- Python 3.10+
- Qdrant binary (see below)
- ~10 GB disk space for full wiki ingestion

### 1. Setup Qdrant

```bash
./SCRIPTS/setup_qdrant.sh
```

This downloads and starts Qdrant on `localhost:6333`.

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Download Embedding Models

```bash
./SCRIPTS/download_embeddings.sh
```

### 4. Run Ingestion

```bash
python INGESTION/run_ingestion.py
```

This fetches all wiki pages, chunks them, embeds them, and stores them in Qdrant.
First run takes ~2-4 hours for full wiki. Resume is supported.

### 5. Query

```bash
python CHATBOT/cli.py
```

Or integrate via `QUERY/query_engine.py` in your mod.

## Configuration

All configuration lives in `COMMON/config.py`. Key settings:

| Variable | Default | Description |
|---|---|---|
| `QDRANT_HOST` | `localhost` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant HTTP port |
| `COLLECTION_NAME` | `terraria_wiki` | Qdrant collection |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformer model |
| `EMBEDDING_DIM` | `384` | Embedding vector size |
| `CHUNK_MAX_TOKENS` | `512` | Max tokens per chunk |
| `CHUNK_OVERLAP_TOKENS` | `50` | Overlap between chunks |
| `TOP_K` | `10` | Vectors to retrieve |
| `RETRIEVE_K` | `5` | Chunks passed to LLM |
| `MINIMAX_API_KEY` | env var | Minimax API key |
| `OPENROUTER_API_KEY` | env var | OpenRouter API key |

## Game State Filtering

When querying, you can filter by:

- `category` — Weapons, Armor, Blocks, NPCs, Biomes, Mechanics, etc.
- `subcategory` — Melee, Ranged, Magic, Summon, etc.
- `game_mode` — Pre-Hardmode, Hardmode, Post-Moon Lord
- `obtain_method` — Crafting, Drop, Purchase, Fishing, etc.

Example:
```python
from QUERY.retriever import RetrievalResult
results = retriever.query(
    query_text="where can I find Iron Ore",
    top_k=10,
    filters={
        "game_mode": {"$eq": "Pre-Hardmode"},
        "category": {"$eq": "Ore"}
    }
)
```

## Testing

```bash
pytest TESTS/ -v
```

## License

MIT — do whatever, credit is nice but not required.
