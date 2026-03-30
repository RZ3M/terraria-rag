# Terraria RAG — Roadmap

> [!NOTE]
> This document is the canonical source for tracking all project tasks and milestones.
> See also: [SPEC.md](./SPEC.md) for architecture details, [TODO.md](./TODO.md) for granular task checklist.

---

## Overview

Terraria RAG is a local-first Retrieval Augmented Generation system for the Terraria wiki, built for integration into a tModLoader mod as an intelligent NPC companion that provides contextual, spoiler-free hints during gameplay.

**Repository:** https://github.com/RZ3M/terraria-rag

---

## 🎯 Goals

1. **Ingest** the entire Terraria wiki (`terraria.wiki.gg`) via MediaWiki API
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

### 🚧 Milestone 2 — Ingestion Pipeline *(IN PROGRESS)*
**Goal:** Fetch all wiki pages, chunk semantically, embed, and index in Qdrant.

#### Ingestion Components
- [ ] `INGESTION/fetcher.py` — MediaWiki API, paginated fetching, caching
- [ ] `INGESTION/parser.py` — HTML/wikitext → structured sections
- [ ] `INGESTION/chunker.py` — semantic chunking by heading + paragraph
- [ ] `INGESTION/embedder.py` — sentence-transformer batch embedding
- [ ] `INGESTION/indexer.py` — Qdrant upsert with resume support
- [ ] `INGESTION/run_ingestion.py` — orchestrator with `--resume`, `--limit`, `--preview`

#### Setup Scripts
- [ ] `SCRIPTS/setup_qdrant.sh` — download & start Qdrant
- [ ] `SCRIPTS/download_embeddings.sh` — download sentence-transformer models

#### Validation
- [ ] Run `--preview` on 10 pages — verify chunk quality
- [ ] Run full ingestion — verify all wiki pages indexed
- [ ] Write `TESTS/test_fetcher.py`
- [ ] Write `TESTS/test_integration.py`

---

### 📋 Milestone 3 — Query & Retrieval
**Goal:** Full query pipeline with game state filtering.

- [ ] `QUERY/retriever.py` — Qdrant retrieval with metadata filtering
- [ ] `QUERY/prompter.py` — prompt construction from chunks + game state
- [ ] `QUERY/query_engine.py` — full pipeline: embed → retrieve → generate
- [ ] `QUERY/reranker.py` — optional cross-encoder re-ranking *(deferred)*
- [ ] `CHATBOT/cli.py` — interactive CLI chatbot for testing
- [ ] Write `TESTS/test_retriever.py`
- [ ] Smoke test: query with no filters → verify results
- [ ] Smoke test: query with game_mode=Hardmode filter → verify filtering

---

### 🎮 Milestone 4 — tModLoader Mod Integration
**Goal:** Functional NPC companion inside Terraria.

- [ ] `MOD/TerrariaRAG.cs` — tModLoader entry point
- [ ] `MOD/NPCCompanion.cs` — NPC dialog system, hint button
- [ ] `MOD/GameStateTracker.cs` — boss detection, biome detection, armor tier
- [ ] Integrate `QUERY/query_engine.py` via HTTP call to Qdrant sidecar
- [ ] NPC texture/assets placeholder
- [ ] Mod build and load test in Terraria
- [ ] Hook into game events: boss kills, Wall of Flesh, Moon Lord

---

### ✨ Milestone 5 — Polish & Release
**Goal:** Production-ready, documented, releaseable.

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

These are aspirational — not committed for any milestone.

- [ ] Cross-encoder reranker for better relevance
- [ ] Embedding model comparison: MiniLM vs MPNet vs domain-specific
- [ ] Multi-language support (other Terraria wikis)
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
| 2 — Ingestion | 🚧 In Progress | ~30% |
| 3 — Query & Retrieval | 📋 Planned | 0% |
| 4 — Mod Integration | 📋 Planned | 0% |
| 5 — Polish & Release | 📋 Planned | 0% |

---

## 🗺️ Project Board

Track progress on GitHub: https://github.com/users/RZ3M/projects/1

---

*Last updated: 2026-03-30*
