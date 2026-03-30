# Terraria RAG System — Specification

## 1. Concept & Vision

A local-first Retrieval Augmented Generation (RAG) system that makes the entire Terraria wiki queryable by an AI, designed primarily for integration into a tModLoader mod as an intelligent NPC companion that provides contextual hints without spoiling progression.

The system prioritizes **low-latency local inference** for real-time in-game use, with an optional chatbot mode for out-of-game querying.

---

## 2. System Architecture

### High-Level Data Flow

```
[Wiki Ingestion]                          [Runtime / Query]
                                          ┌──────────────────────┐
terraria.wiki.gg (MediaWiki API)          │  tModLoader Mod      │
        ↓                                 │    or                │
  Fetch page source                       │  Chatbot CLI         │
        ↓                                 │         ↓            │
  Parse & chunk                           │  Game state context  │
        ↓                                 │         ↓            │
  Embed (sentence-transformers)            │  Query Qdrant        │
        ↓                                 │    (top-k chunks)    │
  Store in Qdrant (with metadata)         │         ↓            │
                                          │  LLM (Minimax M2.7   │
                                          │    or OpenRouter)     │
                                          │         ↓            │
                                          │  Formatted hint/text│
                                          └──────────────────────┘
```

### Key Design Decisions

- **Qdrant as vector store** — local sidecar HTTP service, not embedded, so the mod can query it cleanly without managing in-process complexity
- **Separate embedding pipeline** — embeddings generated locally via `sentence-transformers` (no API cost)
- **LLM calls go to minimax** — generation only; everything else is local
- **Metadata filtering** — each chunk carries wiki metadata (category, section, sub-section) enabling game-state-aware filtering at query time

---

## 3. Data & Ingestion

### Source
- URL: `https://terraria.wiki.gg/`
- API: MediaWiki Action API (`https://terraria.wiki.gg/w/api.php`)
- No authentication required

### MediaWiki API Calls

**Step 1 — Get all page titles (site map)**
```
action=query&list=allpages&aplimit=max&format=json
```
Paginate through all pages. Filter out:
- Redirects (`ns` redirect flag)
- User pages, talk pages, templates, modules
- Pages with no real content (short pages < 500 chars)
- Language variant subpages (Page/ja, Page/de, etc.)

**Step 2 — Fetch page content**
```
action=query&prop=revisions&rvprop=content&rvslots=main&format=json&titles=<PAGE_TITLE>
```

**⚠️ Important — Crafting Recipes:** The MediaWiki API returns raw wikitext with
UNEXPANDED templates like `{{recipes|result=Terra Blade}}`. Recipe ingredients are NOT
included. Two solutions exist:

- `html_fetcher.py` — Scrapling (stealthy browser) → fully rendered HTML with
  expanded crafting trees and real item names. Best quality but requires browser.
- `parser_html.py` — MediaWiki `action=parse&prop=text` → rendered HTML without JS.
  Lighter weight, same recipe quality for most pages.

Both need to be integrated into `run_ingestion.py` to fill in missing recipe data.

### Chunking Strategy

**Not fixed token sizes.** The wiki has structured content (headings, sections, infoboxes, tables). We chunk by:

1. **Semantic sections** — split on `<h2>`, `<h3>` headings first
2. **Infoboxes** — extract as separate chunks (key/value facts)
3. **Tables** — serialize as structured text rows
4. **Max chunk size** — ~512 tokens hard cap, with overlap of 50 tokens across section boundaries

Each chunk captures:
- `wiki_title` — original page title
- `wiki_url` — canonical URL
- `section_path` — e.g. `Weapons > Melee > Swords`
- `chunk_index` — position in page
- `content` — raw text (HTML-stripped or minimal HTML)
- `raw_content` — original HTML for table/infobox preservation

### Metadata Stored in Qdrant

```json
{
  "wiki_title": "Night's Edge",
  "wiki_url": "https://terraria.wiki.gg/wiki/Night%27s_Edge",
  "category": "Weapons",
  "subcategory": "Melee Swords",
  "game_mode": ["Pre-Hardmode", "Hardmode"],
  "obtain_method": "Crafting",
  "chunks_in_page": 5,
  "chunk_index": 2
}
```

**Filtering dimensions:**
- `category` — Weapons, Armor, Blocks, NPCs, Biomes, Mechanics, etc.
- `subcategory` — Melee, Ranged, Magic, Summon, etc.
- `game_mode` — Pre-Hardmode, Hardmode, Post-Moon Lord
- `obtain_method` — Crafting, Drop, Purchase, Fishing, etc.

### Embedding Model

`sentence-transformers/all-MiniLM-L6-v2` — fast, 384 dimensions, good quality for this domain.
Alternative (slower but better): `sentence-transformers/all-mpnet-base-v2` (768d)

---

## 4. Storage

### Qdrant

- **Collection name:** `terraria_wiki`
- **Vector dimensions:** 384 (MiniLM-L6) or 768 (MPNet)
- **Distance metric:** Cosine
- **Indexing:** HNSW for fast ANN queries
- **Payload:** JSON metadata as described above

### Local File Cache

- `data/raw_pages/` — raw JSON responses from MediaWiki (cache, re-fetchable)
- `data/chunks/` — intermediate chunked data as JSONL (Line-delimited JSON)
- `data/ingestion_state.json` — tracks what's been ingested vs what's new/changed

---

## 5. Query & Retrieval

### Query Pipeline

1. Receive query string + optional game state filters
2. Embed query with same model used for ingestion
3. Build Qdrant filter from game state (category, game_mode, etc.)
4. `top_k=10` retrieval, with score threshold (>0.5 relevance)
5. Optionally re-rank with a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`)
6. Return top 3-5 chunks as context

### Prompt Construction

```
System: You are a helpful Terraria NPC companion. You give concise, 
spoiler-free hints that help players progress. You have access to 
the Terraria wiki. Answer based ONLY on the provided context.

Context:
{retrieved_chunks}

Player context:
{game_state_description}

Hint:
```

Game state description includes: current boss kills, progression milestones, active biomes, equipment tier. This lets the LLM contextualize hints.

---

## 6. Project Structure

```
terraria-rag/
├── README.md                  # You are here
├── SPEC.md                    # This file
├── TODO.md                    # Task tracker (auto-generated)
│
├── INGESTION/
│   ├── __init__.py
│   ├── fetcher.py             # MediaWiki API fetching
│   ├── parser.py              # HTML/content parsing
│   ├── chunker.py             # Semantic chunking logic
│   ├── embedder.py            # Embedding generation
│   ├── indexer.py             # Qdrant storage
│   └── run_ingestion.py        # Main ingestion entry point
│
├── QUERY/
│   ├── __init__.py
│   ├── retriever.py           # Qdrant retrieval
│   ├── reranker.py            # Optional cross-encoder rerank
│   ├── prompter.py            # Prompt construction
│   └── query_engine.py         # Full query pipeline
│
├── MOD/
│   ├── TerrariaRAG.cs         # tModLoader integration stub
│   ├── NPCCompanion.cs        # NPC dialog system
│   └── GameStateTracker.cs    # Hooks into game state
│
├── CHATBOT/
│   ├── __init__.py
│   └── cli.py                  # Simple CLI chatbot
│
├── COMMON/
│   ├── __init__.py
│   ├── config.py               # All configuration constants
│   ├── qdrant_client.py        # Shared Qdrant client singleton
│   ├── embedding_model.py      # Shared embedding model loader
│   └── types.py                # Shared dataclasses/types
│
├── DATA/
│   ├── raw_pages/              # Cached wiki page JSON
│   ├── chunks/                 # Chunked documents (JSONL)
│   └── ingestion_state.json    # Ingestion tracking
│
├── SCRIPTS/
│   ├── setup_qdrant.sh         # Install/start Qdrant locally
│   ├── download_embeddings.sh  # Download sentence-transformer models
│   └── test_query.sh           # Smoke-test the retrieval
│
└── TESTS/
    ├── test_fetcher.py
    ├── test_chunker.py
    ├── test_retriever.py
    └── test_integration.py
```

---

## 7. Dependencies

### Python (Ingestion + Query)

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
sentence-transformers>=2.2.0
qdrant-client>=1.7.0
openai>=1.12.0
tqdm>=4.66.0
tenacity>=8.2.0
```

### Runtime

```
Qdrant (binary download, see SCRIPTS/setup_qdrant.sh)
Python >= 3.10
```

---

## 8. Implementation Phases

### Phase 1 — Foundation (this session)
- [x] Project scaffold & SPEC
- [ ] `COMMON/config.py` — all constants in one place
- [ ] `COMMON/types.py` — dataclasses for Chunk, Page, QueryResult
- [ ] `COMMON/qdrant_client.py` — shared client
- [ ] `COMMON/embedding_model.py` — shared model loader

### Phase 2 — Ingestion
- [ ] `INGESTION/fetcher.py` — MediaWiki API, paginated fetching with caching
- [ ] `INGESTION/chunker.py` — semantic chunking by heading structure
- [ ] `INGESTION/embedder.py` — embed chunks
- [ ] `INGESTION/indexer.py` — write to Qdrant
- [ ] `INGESTION/run_ingestion.py` — orchestrator
- [ ] SCRIPTS/setup_qdrant.sh

### Phase 3 — Query
- [ ] `QUERY/retriever.py` — Qdrant retrieval with filtering
- [ ] `QUERY/prompter.py` — prompt construction
- [ ] `QUERY/query_engine.py` — full pipeline
- [ ] `CHATBOT/cli.py` — interactive CLI

### Phase 4 — Mod Integration
- [ ] `MOD/` — tModLoader C# integration stubs
- [ ] Game state hooks design

### Phase 5 — Polish
- [ ] Tests
- [ ] Error handling & retry logic
- [ ] README full documentation
- [ ] Ingestion progress/resume

---

## 9. Open Questions / Future

- [ ] Should we use a cross-encoder reranker? Adds latency but improves quality significantly
- [ ] Update frequency — how often to re-ingest? (Wiki changes infrequently)
- [ ] Offline mode for the mod — can the full pipeline run without internet?
- [ ] LLM-side: minimax M2.7 vs OpenRouter models — latency/quality tradeoff
- [ ] Context window management — if game state + chunks exceed context, what gets dropped?
