"""
COMMON/config.py — All configuration constants for the Terraria RAG system.

Keep all magic numbers and settings here. No hardcoding elsewhere.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "DATA"
RAW_PAGES_DIR = DATA_DIR / "raw_pages"
CHUNKS_DIR = DATA_DIR / "chunks"
INGESTION_STATE_FILE = DATA_DIR / "ingestion_state.json"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
RAW_PAGES_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# MediaWiki API
# ---------------------------------------------------------------------------
WIKI_API_BASE = "https://terraria.wiki.gg/api.php"
WIKI_BASE_URL = "https://terraria.wiki.gg/wiki/"
WIKI_ACTION = "query"
WIKI_FORMAT = "json"

# Fetch settings
FETCH_BATCH_SIZE = 50          # pages per API request (for list=allpages)
FETCH_REQUEST_DELAY_SEC = 0.5  # be polite; wiki.gg has rate limits
FETCH_MAX_RETRIES = 3
FETCH_MIN_PAGE_LENGTH = 500     # skip pages shorter than this

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
CHUNK_MAX_TOKENS = 512          # hard cap on tokens per chunk
CHUNK_OVERLAP_TOKENS = 50       # overlap between consecutive chunks
CHUNK_HTML_STRIP = True        # strip HTML tags from plain-text chunks

# Heading levels to split on (h2=h2, h3=h3 in HTML)
CHUNK_HEADING_TAGS = ["h2", "h3", "h4"]

# Infobox extraction: look for these CSS classes in wiki HTML
INFOBOX_TAGS = ["infobox", " infobox"]

# Table serialization: how to format table rows as text
TABLE_ROW_SEPARATOR = " | "
TABLE_CELL_SEPARATOR = ": "

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384             # output dimension of all-MiniLM-L6-v2
EMBEDDING_BATCH_SIZE = 64       # sentences per embedding batch

# Alternative (slower but higher quality):
# EMBEDDING_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
# EMBEDDING_DIM = 768

# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_GRPC_PORT = 6334
COLLECTION_NAME = "terraria_wiki"

# Qdrant collection settings
HNSW_M = 16                     # HNSW construction parameter
HNSW_EF_CONSTRUCT = 128        # HNSW construction-time search depth
HNSW_EF = 128                   # HNSW runtime search depth

# Payload index fields (enable these for fast filtering)
PAYLOAD_INDEX_FIELDS = [
    "wiki_title",
    "wiki_url",
    "category",
    "subcategory",
    "game_mode",
    "obtain_method",
]

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
TOP_K = 10                      # vectors to retrieve from Qdrant
RETRIEVE_K = 5                  # chunks to pass to LLM (post-rerank if used)
RETRIEVAL_SCORE_THRESHOLD = 0.3  # minimum cosine similarity to include

# Reranker (optional — set to None to disable)
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANK_TOP_N = 5               # after reranking, keep top N

# ---------------------------------------------------------------------------
# LLM Generation
# ---------------------------------------------------------------------------
DEFAULT_LLM_PROVIDER = "minimax"  # "minimax" or "openrouter"

# Minimax
MINIMAX_API_KEY = None          # set via environment variable MINIMAX_API_KEY
MINIMAX_BASE_URL = "https://api.minimax.chat/v1"
MINIMAX_MODEL = "MiniMax-Text-01"
MINIMAX_MAX_TOKENS = 500
MINIMAX_TEMPERATURE = 0.7

# OpenRouter (fallback)
OPENROUTER_API_KEY = None       # set via environment variable OPENROUTER_API_KEY
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openrouter/auto"
OPENROUTER_MAX_TOKENS = 500
OPENROUTER_TEMPERATURE = 0.7

# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a helpful Terraria NPC companion. You give concise,
spoiler-free hints that help players progress through the game. You have access
to the Terraria wiki. Answer based ONLY on the provided context.

- Do NOT reveal exact crafting recipes unless the player is clearly asking
- Suggest next steps based on the player's current game state
- Be encouraging but not hand-holding
- If the context doesn't contain enough info to answer, say so
"""

USER_PROMPT_TEMPLATE = """Context:
{context}

Player game state:
{game_state}

Question: {question}

Hint:"""

# ---------------------------------------------------------------------------
# Game State Defaults (used when no state is provided)
# ---------------------------------------------------------------------------
DEFAULT_GAME_STATE = """Unknown game state. Provide a general hint if possible."""

# Known categories in the wiki (for filtering)
WIKI_CATEGORIES = [
    "Weapons",
    "Armor",
    "Blocks",
    "Ores",
    "Bars",
    "NPCs",
    "Enemies",
    "Bosses",
    "Biomes",
    "Mechanics",
    "Crafting",
    "Objects",
    "Potions",
    "Accessories",
    "Pets",
    "Mounts",
    "Hooks",
    "Dyes",
    "Paintings",
    "Music",
    "Events",
    "Town NPCs",
    "Quests",
    "Achievements",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
