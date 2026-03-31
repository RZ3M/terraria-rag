"""
QUERY/query_engine.py — Full query pipeline: retrieve → format → generate.

Orchestrates retrieval from Qdrant, prompt construction, and LLM generation
via Minimax or OpenRouter. Returns a fully formatted QueryResult.
"""

import logging
import os
import time
from typing import Optional

from openai import OpenAI

from COMMON.config import (
    DEFAULT_LLM_PROVIDER,
    MINIMAX_API_KEY,
    MINIMAX_BASE_URL,
    MINIMAX_MODEL,
    MINIMAX_MAX_TOKENS,
    MINIMAX_TEMPERATURE,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    OPENROUTER_MAX_TOKENS,
    OPENROUTER_TEMPERATURE,
    RETRIEVE_K,
)
from COMMON.embedding_model import embed_single
from COMMON.types import GameState, QueryResult, RetrievalResult
from QUERY.retriever import retrieve
from QUERY.prompter import (
    build_system_prompt,
    build_user_prompt,
    format_hint_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM clients
# ---------------------------------------------------------------------------

def _get_minimax_client() -> OpenAI:
    api_key = MINIMAX_API_KEY or os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        raise ValueError(
            "Minimax API key not set. Set MINIMAX_API_KEY env var "
            "or provide it in COMMON/config.py"
        )
    return OpenAI(api_key=api_key, base_url=MINIMAX_BASE_URL)


def _get_openrouter_client() -> OpenAI:
    api_key = OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenRouter API key not set. Set OPENROUTER_API_KEY env var "
            "or provide it in COMMON/config.py"
        )
    return OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _generate_via_minimax(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = MINIMAX_MAX_TOKENS,
    temperature: float = MINIMAX_TEMPERATURE,
) -> str:
    client = _get_minimax_client()
    response = client.chat.completions.create(
        model=MINIMAX_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


def _generate_via_openrouter(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = OPENROUTER_MAX_TOKENS,
    temperature: float = OPENROUTER_TEMPERATURE,
) -> str:
    client = _get_openrouter_client()
    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Main query pipeline
# ---------------------------------------------------------------------------

def query(
    question: str,
    game_state: Optional[GameState] = None,
    provider: str = DEFAULT_LLM_PROVIDER,
    retrieve_k: int = RETRIEVE_K,
    verbose: bool = False,
) -> QueryResult:
    """
    Full RAG query pipeline.

    1. Embed the question
    2. Retrieve relevant chunks from Qdrant (with game state filtering)
    3. Build prompt
    4. Generate response via Minimax or OpenRouter
    5. Return formatted QueryResult

    Parameters
    ----------
    question : str
        The user's question.
    game_state : GameState, optional
        Current game state for filtering.
    provider : str
        "minimax" or "openrouter".
    retrieve_k : int
        Number of chunks to retrieve and pass to the LLM.
    verbose : bool
        If True, log detailed pipeline info.

    Returns
    -------
    QueryResult
        Complete query result with chunks and LLM response.
    """
    start_time = time.time()

    # Step 1: Retrieve chunks
    if game_state:
        filter_dict = game_state.to_filter_dict()
        cat = filter_dict.get("category", {}).get("$eq")
        game_mode = None
        # Extract game_mode from filter
        gm_filter = filter_dict.get("game_mode", {})
        if isinstance(gm_filter, dict) and "$eq" in gm_filter:
            game_mode = gm_filter["$eq"]
        elif isinstance(gm_filter, dict) and "$or" in gm_filter:
            # Take first option
            options = gm_filter["$or"]
            if options and "$eq" in options[0]:
                game_mode = options[0]["$eq"]
    else:
        cat = None
        game_mode = None

    results = retrieve(
        query_text=question,
        top_k=retrieve_k * 3,  # retrieve more for re-ranking + keyword boost
        category=cat,
        game_mode=game_mode,
    )

    # Top K after keyword boost and section quality re-ranking (both done in retrieve())
    top_results = results[:retrieve_k]

    # Step 2: Build prompts
    game_state_str = game_state.to_prompt_string() if game_state else None
    system_prompt = build_system_prompt(game_state_str)
    user_prompt = build_user_prompt(
        query_text=question,
        results=top_results,
        game_state_str=game_state_str,
    )

    if verbose:
        logger.debug(f"System prompt:\n{system_prompt}")
        logger.debug(f"User prompt:\n{user_prompt[:500]}...")

    # Step 3: Generate
    try:
        if provider == "minimax":
            llm_response = _generate_via_minimax(system_prompt, user_prompt)
        elif provider == "openrouter":
            llm_response = _generate_via_openrouter(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        llm_response = f"(Generation failed: {e})"

    # Step 4: Clean response
    cleaned_response = format_hint_response(llm_response)

    latency_ms = (time.time() - start_time) * 1000

    result = QueryResult(
        query_text=question,
        retrieved_chunks=top_results,
        game_state=game_state_str or "Unknown",
        llm_response=cleaned_response,
        provider=provider,
        latency_ms=latency_ms,
    )

    logger.info(
        f"Query complete in {latency_ms:.0f}ms | "
        f"{len(top_results)} chunks | provider={provider}"
    )

    return result


def quick_query(question: str, verbose: bool = False) -> str:
    """
    Simple one-liner for a quick query with no game state.

    Returns just the LLM response string.
    """
    result = query(question, verbose=verbose)
    return result.llm_response
