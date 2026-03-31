"""
COMMON/config.py — All configuration constants for the Terraria RAG system.

Keep all magic numbers and settings here. No hardcoding elsewhere.

API keys are loaded from .env (never committed). See .env.example for keys.
"""

from pathlib import Path
from dotenv import load_dotenv

# Load .env file (ignored by git — contains private API keys)
load_dotenv(Path(__file__).parent.parent / ".env")

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
FETCH_REQUEST_DELAY_SEC = 2.0  # be polite; wiki.gg has rate limits
FETCH_MAX_RETRIES = 3
FETCH_MIN_PAGE_LENGTH = 500     # skip pages shorter than this

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
CHUNK_MAX_TOKENS = 200          # hard cap on tokens per chunk
# NOTE: all-MiniLM-L6-v2 has max_seq_length=256 actual tokens. With the rough
# len(text)//4 estimator, 200 "tokens" ≈ 800 chars ≈ ~200 real tokens, leaving
# headroom for the model's [CLS]/[SEP] tokens and tokenization overhead.
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
RETRIEVAL_SCORE_THRESHOLD = 0.4  # minimum cosine similarity to include

# Reranker (optional — set to None to disable)
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANK_TOP_N = 5               # after reranking, keep top N

# ---------------------------------------------------------------------------
# LLM Generation
# ---------------------------------------------------------------------------
DEFAULT_LLM_PROVIDER = "minimax"  # "minimax" or "openrouter"

# Minimax
MINIMAX_API_KEY = None          # set via environment variable MINIMAX_API_KEY
MINIMAX_BASE_URL = "https://api.minimax.io/v1"
MINIMAX_MODEL = "MiniMax-M2.7"
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
spoiler-free hints that help players progress through the game.

You have been given wiki context about Terraria items, weapons, and strategies.
Answer based ONLY on the provided context.

OUTPUT FORMAT:
- Give the hint in 2-3 sentences MAXIMUM
- Do NOT explain your reasoning
- Do NOT say "Based on the context" or "Looking at the context"
- Do NOT output any thinking, reasoning, or chain-of-thought
- Just give the answer directly as a helpful NPC hint
- If the context doesn't have enough info, say "I don't have enough information to answer that."
- Be encouraging but not hand-holding
- Suggest specific items or strategies when relevant
- NEVER reveal exact crafting recipes unless the player asks directly
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
