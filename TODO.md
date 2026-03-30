# TODO — Terraria RAG

## Phase 1 — Foundation
- [x] Project scaffold & SPEC
- [x] README.md
- [x] `COMMON/config.py` — all configuration constants
- [x] `COMMON/types.py` — dataclasses (Chunk, Page, QueryResult, etc.)
- [x] `COMMON/qdrant_client.py` — shared Qdrant client singleton
- [x] `COMMON/embedding_model.py` — shared embedding model loader
- [x] `COMMON/__init__.py`

## Phase 2 — Ingestion
- [ ] `INGESTION/__init__.py`
- [ ] `INGESTION/fetcher.py` — MediaWiki API, paginated fetching, caching
- [ ] `INGESTION/parser.py` — HTML/content parsing, heading extraction
- [ ] `INGESTION/chunker.py` — semantic chunking by heading structure
- [ ] `INGESTION/embedder.py` — embed chunks using sentence-transformers
- [ ] `INGESTION/indexer.py` — Qdrant upsert logic
- [ ] `INGESTION/run_ingestion.py` — main ingestion orchestrator
- [ ] `SCRIPTS/setup_qdrant.sh` — download & start Qdrant
- [ ] `SCRIPTS/download_embeddings.sh` — download sentence-transformer models

## Phase 3 — Query
- [ ] `QUERY/__init__.py`
- [ ] `QUERY/retriever.py` — Qdrant retrieval with metadata filtering
- [ ] `QUERY/reranker.py` — optional cross-encoder re-ranking
- [ ] `QUERY/prompter.py` — prompt construction with game state
- [ ] `QUERY/query_engine.py` — full pipeline: retrieve → re-rank → prompt → generate
- [ ] `QUERY/__init__.py`
- [ ] `CHATBOT/__init__.py`
- [ ] `CHATBOT/cli.py` — interactive CLI chatbot

## Phase 4 — Mod Integration
- [ ] `MOD/TerrariaRAG.cs` — tModLoader integration entry point
- [ ] `MOD/NPCCompanion.cs` — NPC dialog system
- [ ] `MOD/GameStateTracker.cs` — game state detection hooks

## Phase 5 — Polish
- [ ] `TESTS/test_fetcher.py`
- [ ] `TESTS/test_chunker.py`
- [ ] `TESTS/test_retriever.py`
- [ ] `TESTS/test_integration.py`
- [ ] Error handling & retry logic (tenacity)
- [ ] Ingestion resume support
- [ ] Progress bar for ingestion
- [ ] Logging setup
- [ ] requirements.txt

---

Updated: 2026-03-30
