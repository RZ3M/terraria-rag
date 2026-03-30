# Terraria RAG — Roadmap

> [!NOTE]
> This document is the canonical source for tracking all project tasks and milestones.
> See also: [SPEC.md](./SPEC.md) for architecture details, [TODO.md](./TODO.md) for granular task checklist.

---

## Overview

Terraria RAG is a local-first Retrieval Augmented Generation system for the Terraria wiki, built for integration into a tModLoader mod as an intelligent NPC companion that provides contextual, spoiler-free hints during gameplay.

**Repository:** https://github.com/RZ3M/terraria-rag

---

## 🚨 Key Issue: Missing Crafting Recipes

**Problem:** The MediaWiki API returns raw wikitext with UNEXPANDED templates like
`{{recipes|result=Terra Blade}}` — no actual crafting ingredients are included.
The 3,694 pages already indexed have full text/stats but NO recipe data.

**Two solutions built:**

1. **`html_fetcher.py`** — Scrapling (stealthy browser, bypasses anti-bot) → rendered HTML
   with full crafting trees and ingredients. Tested on Terra Blade ✅
2. **`parser_html.py`** — MediaWiki `action=parse&prop=text` endpoint → also renders
   recipes in HTML (227KB HTML for Terra Blade, includes True Night's Edge etc.)
   Tested ✅

**Neither is integrated into run_ingestion.py yet.** This is the main TODO to finish
Milestone 2 and fill in the missing recipe content.

---

## 🎯 Goals

1. **Ingest** the entire Terraria wiki — with full crafting recipe data
2. **Index** wiki content in Qdrant with rich metadata filtering
3. **Query** at runtime with game-state-aware retrieval
4. **Generate** contextual hints via Minimax M2.7 / OpenRouter LLMs
5. **Integrate** as a tModLoader mod with an NPC companion

---

## 🚀 Milestones

### ✅ Milestone 1 — Project Foundation *(COMPLETE)*
**Goal:** Scaffold the project with full architecture documented.

- [x] Project structure (COMMON, INGESTION, QUERY, CHATBOT, MOD, TESTS)
- [x] SPEC.md — architecture, design decisions, chunking strategy
- [x] README.md — quick start guide
- [x] COMMON module — config, types, Qdrant client, embedding model
- [x] `.gitignore`, requirements.txt
- [x] GitHub repo initialized and pushed

---

### 🚧 Milestone 2 — Ingestion Pipeline *(~75% — needs recipe re-ingest)*
**Goal:** Fetch all wiki pages with full crafting data, chunk semantically, embed, index in Qdrant.

**Progress:** 3,694 pages indexed (10,761 chunks) but MISSING crafting recipe content.

#### Ingestion Components
- [x] `INGESTION/fetcher.py` — MediaWiki API, paginated fetching, caching
- [x] `INGESTION/html_fetcher.py` — Scrapling-based HTML fetcher for rendered pages
  (crafting recipes, infobox stats) ✅ tested
- [x] `INGESTION/parser_html.py` — BeautifulSoup parser for MediaWiki rendered HTML ✅
- [x] `INGESTION/parser.py` — wikitext → structured sections
- [x] `INGESTION/chunker.py` — semantic chunking by heading + paragraph
- [x] `INGESTION/embedder.py` — sentence-transformer batch embedding
- [x] `INGESTION/indexer.py` — Qdrant upsert with resume support
- [x] `INGESTION/run_ingestion.py` — orchestrator with --resume, --limit, --preview

#### Setup Scripts
- [x] `SCRIPTS/setup_qdrant.sh` — download + start Qdrant v1.17
- [x] `SCRIPTS/download_embeddings.sh` — download sentence-transformer models
- [x] `SCRIPTS/run_full_ingestion.sh` — background ingestion wrapper

#### Validation
- [ ] **Integrate html_fetcher/parser_html into run_ingestion.py** ← PRIMARY TODO
- [ ] Re-ingest recipe-bearing pages (weapons, armor, tools, accessories, etc.)
- [ ] Write `TESTS/test_fetcher.py`
- [ ] Write `TESTS/test_integration.py`

---

### ✅ Milestone 3 — Query & Retrieval *(COMPLETE)*
**Goal:** Full query pipeline with game state filtering.

- [x] `QUERY/retriever.py` — Qdrant retrieval with metadata filtering ✅
- [x] `QUERY/prompter.py` — prompt construction from chunks + game state ✅
- [x] `QUERY/query_engine.py` — full pipeline: embed → retrieve → generate ✅
- [x] `QUERY/reranker.py` — optional cross-encoder re-ranking *(deferred)*
- [x] `CHATBOT/cli.py` — interactive CLI chatbot for testing ✅
- [ ] Write `TESTS/test_retriever.py`
- [ ] Smoke test: query with no filters → verify results ✅ (verified 2026-03-30)
- [ ] Smoke test: query with game_mode=Hardmode filter → verify filtering

---

### 🚧 Milestone 4 — tModLoader Mod Integration *(stubs done)*
**Goal:** Functional NPC companion inside Terraria.

- [x] `MOD/TerrariaRAG.cs` — tModLoader entry point (stub)
- [x] `MOD/NPCCompanion.cs` — NPC dialog system, hint button (stub)
- [x] `MOD/GameStateTracker.cs` — boss detection, biome detection, armor tier (stub)
- [ ] Integrate `QUERY/query_engine.py` via HTTP call to Qdrant sidecar
- [ ] NPC texture/assets placeholder
- [ ] Mod build and load test in Terraria
- [ ] Hook into game events: boss kills, Wall of Flesh, Moon Lord

---

### 🚧 Milestone 5 — Polish & Release *(partial)*
**Goal:** Production-ready, documented, releaseable.

- [x] `TESTS/test_chunker.py` — chunker unit tests
- [ ] Error handling & retry logic (tenacity) across all HTTP calls
- [ ] Ingestion progress bar + ETA
- [ ] Logging setup (`structlog` or standard logging)
- [ ] Update frequency strategy (wiki changes infrequently)
- [ ] Offline mode: can the full pipeline run without internet?
- [ ] Context window management: if game state + chunks exceed limit
- [ ] README: full documentation with screenshots
- [ ] PyPI package / mod release workflow
- [ ] License file (MIT)

---

## 🔮 Future Ideas (Backlog)

- [ ] Cross-encoder reranker for better relevance
- [ ] Embedding model comparison: MiniLM vs MPNet vs domain-specific
- [ ] Multi-language support (other Terraria wikis) — currently EN only
- [ ] Voice TTS for NPC dialog (ElevenLabs)
- [ ] Discord bot interface
- [ ] Web UI for the chatbot
- [ ] Streaming LLM responses for longer hints
- [ ] Conversation memory / multi-turn dialog with NPC
- [ ] Player-specific hint history (avoid repeating hints)

---

## 📊 Progress Tracking

| Milestone | Status | Completion |
|-----------|--------|-----------|
| 1 — Foundation | ✅ Complete | 100% |
| 2 — Ingestion | 🚧 In Progress | ~75% (needs recipe re-ingest) |
| 3 — Query & Retrieval | ✅ Complete | 100% |
| 4 — Mod Integration | 🚧 Stubs Done | ~20% |
| 5 — Polish & Release | 🚧 Partial | ~15% |

---

## 🗺️ Project Board

Track progress on GitHub: https://github.com/users/RZ3M/projects/1

---

## 📁 Data Summary (as of 2026-03-30)

- **Qdrant collection:** `terraria_wiki` — GREEN, 10,761 chunks, 384-dim vectors
- **Raw pages cached:** ~3,694 in `DATA/raw_pages/`
- **Chunks on disk:** 3,694 JSONL files in `DATA/chunks/`
- **Ingestion state:** `DATA/ingestion_state.json` (checkpoint for --resume)
- **Wiki coverage:** All English pages (namespaces=[0]), no redirects, no language variants

---

*Last updated: 2026-03-30*
