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

1. **Ingest** the entire Terraria wiki — with full crafting recipe data ✅
2. **Index** wiki content in Qdrant with rich metadata filtering ✅
3. **Query** at runtime with game-state-aware retrieval ✅
4. **Generate** contextual hints via Minimax M2.7 / OpenRouter LLMs ✅
5. **Integrate** as a tModLoader mod with an NPC companion 🚧

---

## 🚀 Milestones

### ✅ Milestone 1 — Project Foundation *(COMPLETE)*

- [x] Project structure (COMMON, INGESTION, QUERY, CHATBOT, MOD, TESTS)
- [x] SPEC.md — architecture, design decisions, chunking strategy
- [x] README.md — quick start guide
- [x] COMMON module — config, types, Qdrant client, embedding model
- [x] `.gitignore`, requirements.txt
- [x] GitHub repo initialized and pushed

---

### ✅ Milestone 2 — Ingestion Pipeline *(COMPLETE — 2026-03-31)*

**3,671 pages, 22,005 chunks, HTML mode, crafting recipes included.**

#### Components
- [x] `INGESTION/fetcher.py` — MediaWiki API, paginated fetching, caching
- [x] `INGESTION/html_fetcher.py` — Scrapling-based HTML fetcher (backup)
- [x] `INGESTION/parser_html.py` — BeautifulSoup parser for rendered HTML (default)
- [x] `INGESTION/parser.py` — wikitext parser (fallback mode)
- [x] `INGESTION/chunker.py` — semantic chunking, bug fixes applied (2026-03-31)
- [x] `INGESTION/embedder.py` — sentence-transformer batch embedding
- [x] `INGESTION/indexer.py` — Qdrant upsert with resume support
- [x] `INGESTION/run_ingestion.py` — orchestrator with --resume, --limit, --preview, --fetch-mode
- [x] Default fetch mode is now `html` (MediaWiki rendered — templates expanded, recipes included)
- [x] Version changelog pages filtered (1.0, 1.0.1, etc.)
- [x] Metadata inference: `category`, `game_mode`, `obtain_method` now populated

#### Bugs Fixed (2026-03-31)
- [x] `_split_by_sentence` was returning only first chunk (silent content loss)
- [x] Chunk overlap logic was broken (never added any overlap)
- [x] `CHUNK_MAX_TOKENS=512` exceeded model's 256-token limit → reduced to 200
- [x] Missing spaces in wikitext link stripping ("aHardmodebroadsword" → "a Hardmode broadsword")
- [x] `_normalize_whitespace` destroyed paragraph boundaries (now preserves `\n\n`)
- [x] Navbox/navigation template pollution — added nav-class, role, size heuristics to `_remove_noise`
- [x] `get_text(strip=True)` concatenated inline elements — fixed to `get_text(separator=" ")`

---

### ✅ Milestone 3 — Query & Retrieval *(COMPLETE — bugs fixed 2026-03-31)*

**Retrieval quality: recall@5=81.8%, content-recall@5=95.5%, MRR=0.629**

#### Components
- [x] `QUERY/retriever.py` — Qdrant retrieval with section quality re-ranking
- [x] `QUERY/query_expander.py` — query expansion (capped at 8 terms to avoid dilution)
- [x] `QUERY/prompter.py` — prompt construction from chunks + game state
- [x] `QUERY/query_engine.py` — full pipeline: embed → retrieve → generate
- [x] `CHATBOT/cli.py` — interactive CLI chatbot
- [x] Cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`) — enabled and wired in

#### Bugs Fixed (2026-03-31)
- [x] `SKIP_WORDS` case mismatch — Title-case set compared against lowercased words (never matched)
- [x] `WEAPON_CATS` tuple keys — `("ranged",)` never matched string `"ranged"` (dead code)
- [x] `expand_query()` called twice in `retrieve()` — unconditional second call ignored the flag
- [x] Query expansion appended 30-50 terms — diluted embeddings rather than improving them (capped at 8)
- [x] `textwrap.fill()` in prompter destroyed table/recipe/list structure
- [x] `format_hint_response()` capped at 500 chars — too short for crafting/strategy answers (→ 1500)
- [x] `GameState.to_filter_dict()` produced MongoDB-style operators that `query_engine.py` parsed lossily
- [x] Score threshold 0.3 too permissive (→ 0.4)
- [x] Cross-encoder reranker was configured in config but never instantiated or called

#### Evaluation Infrastructure
- [x] `TESTS/eval_queries.py` — 22 golden test cases (item lookup, crafting, boss, stats, progression, biome, NPC)
- [x] `TESTS/eval_retrieval.py` — automated scorer (recall@K, MRR, content-hit, per-category)
- [x] Baseline saved: `DATA/eval_baseline.json` (pre-fix: 77.3%/68.2%/MRR=0.600)
- [x] Final saved: `DATA/eval_final.json` (post-fix: 81.8%/95.5%/MRR=0.629)

---

### 🚧 Milestone 4 — tModLoader Mod Integration *(stubs done, ~20%)*

- [x] `MOD/TerrariaRAG.cs` — tModLoader entry point (stub)
- [x] `MOD/NPCCompanion.cs` — NPC dialog system, hint button (stub)
- [x] `MOD/GameStateTracker.cs` — boss detection, biome detection, armor tier (stub)
- [ ] Integrate `QUERY/query_engine.py` via HTTP call to Qdrant sidecar
- [ ] NPC texture/assets placeholder
- [ ] Mod build and load test in Terraria
- [ ] Hook into game events: boss kills, Wall of Flesh, Moon Lord

---

### 🚧 Milestone 5 — Polish & Release *(~25%)*

- [x] `TESTS/test_chunker.py` — chunker unit tests
- [x] `TESTS/eval_queries.py` + `TESTS/eval_retrieval.py` — retrieval quality evaluation
- [ ] `TESTS/test_fetcher.py`
- [ ] `TESTS/test_integration.py`
- [ ] `TESTS/test_retriever.py`
- [ ] Error handling & retry logic (tenacity) across all HTTP calls
- [ ] Ingestion progress bar + ETA
- [ ] Context window management: if game state + chunks exceed LLM limit
- [ ] README: screenshots and demo
- [ ] PyPI package / mod release workflow
- [ ] License file (MIT)

---

## 🔮 Future Ideas (Backlog)

- [ ] Embedding model upgrade: `all-mpnet-base-v2` (768d, 512-token limit) — would allow larger chunks
- [ ] Multi-language support (other Terraria wikis) — currently EN only
- [ ] Voice TTS for NPC dialog (ElevenLabs)
- [ ] Discord bot interface
- [ ] Web UI for the chatbot
- [ ] Streaming LLM responses
- [ ] Conversation memory / multi-turn dialog with NPC
- [ ] Player-specific hint history (avoid repeating hints)
- [ ] Category query support — "best pre-hardmode bows" type queries need guide pages or aggregation

---

## 📊 Progress Tracking

| Milestone | Status | Completion |
|-----------|--------|-----------|
| 1 — Foundation | ✅ Complete | 100% |
| 2 — Ingestion | ✅ Complete | 100% |
| 3 — Query & Retrieval | ✅ Complete | 100% |
| 4 — Mod Integration | 🚧 Stubs Done | ~20% |
| 5 — Polish & Release | 🚧 Partial | ~25% |

---

## 📁 Data Summary (as of 2026-03-31)

- **Qdrant collection:** `terraria_wiki` — 22,005 chunks, 384-dim vectors (cosine, HNSW)
- **Raw pages cached:** ~3,771 JSON files in `DATA/raw_pages/` (HTML mode cache)
- **Ingestion mode:** HTML (`action=parse&prop=text`) — templates rendered, crafting recipes included
- **Wiki coverage:** All English pages (namespaces=[0]), no redirects, no language variants, no version changelogs
- **Eval results:** `DATA/eval_baseline.json`, `DATA/eval_phase1.json`, `DATA/eval_final.json`

---

*Last updated: 2026-03-31*
