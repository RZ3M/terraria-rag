# TODO — Terraria RAG

Updated: 2026-03-31

## ✅ Completed This Session (2026-03-31)

### Evaluation Infrastructure
- [x] `TESTS/eval_queries.py` — 22 golden test cases across 7 categories
- [x] `TESTS/eval_retrieval.py` — automated retrieval scorer (recall@K, MRR, content-hit, compare mode)
- [x] Baseline captured: `DATA/eval_baseline.json`

### Query-Side Bug Fixes
- [x] `SKIP_WORDS` lowercase fix — was Title-case, never matched `w.lower()`
- [x] `WEAPON_CATS` string key fix — was tuple keys, never matched plain string lookup
- [x] Double `expand_query()` call in `retrieve()` — now computed once
- [x] Expansion term cap (max 8) — was appending 30-50 terms and diluting embeddings
- [x] `textwrap.fill()` removed from prompter — was destroying table/recipe structure
- [x] Response truncation: 500 → 1500 chars
- [x] `GameState.to_filter_dict()` now returns clean `{"game_mode": ["Hardmode", ...]}` instead of MongoDB-style operators
- [x] Score threshold: 0.3 → 0.4

### Ingestion-Side Bug Fixes
- [x] HTML fetch mode set as default (`run_ingestion.py`)
- [x] `_split_by_sentence` returns ALL chunks (was `return chunks[0]`, silently lost content)
- [x] Overlap logic fixed (started at full chunk size, now starts at 0)
- [x] `CHUNK_MAX_TOKENS` reduced 512 → 200 (model max_seq_length is 256, not 512)
- [x] Missing spaces in wikitext link stripping fixed
- [x] `_normalize_whitespace` now preserves `\n\n` paragraph boundaries
- [x] Navbox pollution in HTML parser fixed (nav-class patterns, role="navigation", size heuristic)
- [x] `get_text(separator=" ")` — fixed inline element concatenation
- [x] `infer_game_mode()` and `infer_obtain_method()` — new functions, now populate metadata
- [x] `infer_category()` — expanded to check content patterns, not just title keywords
- [x] Metadata inference uses parsed section text (not raw HTML) for accuracy
- [x] Version changelog pages filtered from ingestion (1.0, 1.0.1, etc.)
- [x] Preview double-increment bug fixed

### Reranker
- [x] Cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`) wired into `retrieve()` — was configured but never called

### Re-ingestion
- [x] Full re-ingestion with HTML mode: 3,671 pages, 22,005 chunks

---

## 🔜 Next: Mod Integration (Milestone 4)

- [ ] Wire `QUERY/query_engine.py` into tModLoader mod via HTTP
- [ ] NPC texture/assets placeholder
- [ ] Mod build and load test in Terraria
- [ ] Hook into game events: boss kills, Wall of Flesh, Moon Lord

## 🔜 Tests Needed

- [ ] `TESTS/test_fetcher.py` — fetch caching, rate limiting, error handling
- [ ] `TESTS/test_retriever.py` — verify SKIP_WORDS, WEAPON_CATS, item extraction
- [ ] `TESTS/test_integration.py` — end-to-end chunk → embed → index → retrieve roundtrip
- [ ] Fix `TESTS/test_chunker.py` — `test_empty_text` and `test_long_text` use wrong expected values for `_estimate_tokens` (pre-existing, low priority)

## 🔜 Polish

- [ ] Error handling & retry logic (tenacity) — listed as dependency but not integrated
- [ ] Context window management if game state + chunks exceed LLM token limit
- [ ] `openrouter/auto` → specify a concrete model for deterministic behaviour
- [ ] Remove dead config: `INFOBOX_TAGS`, `TABLE_ROW_SEPARATOR`, `TABLE_CELL_SEPARATOR`
- [ ] License file (MIT)

## 🔮 Future / Nice-to-Have

- [ ] Embedding model upgrade: `all-mpnet-base-v2` (768d, 512-token limit) — better quality, needs full re-ingest
- [ ] Category query support — "best pre-hardmode bows" fails because no single page aggregates a list; would need guide pages or a multi-doc aggregation layer
- [ ] Conversation history in chatbot (sliding window of last 3-5 exchanges)
- [ ] `INGESTION/run_ingestion.py --preview` — also apply version page filter (currently only in `run_full_ingestion`)
