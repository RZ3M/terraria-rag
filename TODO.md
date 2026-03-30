# TODO — Terraria RAG

## 🚨 Priority: Finish Recipe Re-Ingestion
- [ ] Integrate `html_fetcher` or `parser_html` into `run_ingestion.py`
  - Add `--html-fetch` flag to use rendered HTML for recipe-bearing pages
  - Re-fetch already-cached pages that have crafting sections
- [ ] Run recipe re-ingestion on all indexed pages
- [ ] Verify crafting data is now in Qdrant (query for Terra Blade crafting)

## Phase 1 — Foundation
- [x] Project scaffold & SPEC
- [x] README.md
- [x] `COMMON/config.py` — all configuration constants
- [x] `COMMON/types.py` — dataclasses (Chunk, Page, QueryResult, GameState)
- [x] `COMMON/qdrant_client.py` — shared Qdrant client singleton
- [x] `COMMON/embedding_model.py` — shared embedding model loader
- [x] `COMMON/__init__.py`

## Phase 2 — Ingestion
- [x] `INGESTION/fetcher.py` — MediaWiki API, paginated fetching, caching
- [x] `INGESTION/parser.py` — HTML/content parsing, heading extraction
- [x] `INGESTION/chunker.py` — semantic chunking by heading structure
- [x] `INGESTION/embedder.py` — embed chunks using sentence-transformers
- [x] `INGESTION/indexer.py` — Qdrant upsert logic
- [x] `INGESTION/run_ingestion.py` — main ingestion orchestrator
- [x] `SCRIPTS/setup_qdrant.sh` — download & start Qdrant
- [x] `SCRIPTS/download_embeddings.sh` — download sentence-transformer models
- [x] `INGESTION/html_fetcher.py` — Scrapling fetcher for rendered HTML (crafting)
- [x] `INGESTION/parser_html.py` — BeautifulSoup parser for MediaWiki HTML
- [ ] **Integrate html_fetcher into run_ingestion.py** ← TOP PRIORITY
- [ ] Re-ingest recipe-bearing pages (weapons, armor, tools, accessories)

## Phase 3 — Query
- [x] `QUERY/retriever.py` — Qdrant retrieval with metadata filtering
- [x] `QUERY/prompter.py` — prompt construction with game state
- [x] `QUERY/query_engine.py` — full pipeline: retrieve → re-rank → prompt → generate
- [x] `CHATBOT/cli.py` — interactive CLI chatbot
- [ ] Test LLM generation (needs MINIMAX_API_KEY or OPENROUTER_API_KEY)
- [ ] `TESTS/test_retriever.py`

## Phase 4 — Mod Integration
- [x] `MOD/TerrariaRAG.cs` — tModLoader integration entry point (stub)
- [x] `MOD/NPCCompanion.cs` — NPC dialog system (stub)
- [x] `MOD/GameStateTracker.cs` — game state detection hooks (stub)
- [ ] Wire `QUERY/query_engine.py` into mod via HTTP

## Phase 5 — Polish
- [x] `TESTS/test_chunker.py`
- [ ] `TESTS/test_fetcher.py`
- [ ] `TESTS/test_integration.py`
- [ ] `TESTS/test_retriever.py`
- [ ] Error handling & retry logic (tenacity)
- [ ] Ingestion progress bar + ETA
- [ ] README: full documentation with screenshots
- [ ] License file (MIT)

---

Updated: 2026-03-30
