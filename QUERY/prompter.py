"""
QUERY/prompter.py — Prompt construction for LLM generation.

Builds system and user prompts from retrieved chunks and game state.
"""

from typing import Optional

from COMMON.config import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    DEFAULT_GAME_STATE,
)
from COMMON.types import RetrievalResult


def build_context_string(
    results: list[RetrievalResult],
    include_raw: bool = False,
) -> str:
    """
    Format retrieved chunks into a context string for the LLM.

    Parameters
    ----------
    results : list[RetrievalResult]
        Retrieved chunks from Qdrant.
    include_raw : bool
        If True, also include raw HTML for tables/infoboxes.

    Returns
    -------
    str
        Formatted context string.
    """
    if not results:
        return "(No relevant wiki content found.)"

    parts = []
    for result in results:
        chunk = result.chunk
        header = (
            f"[Source: {chunk.wiki_title} | Section: {chunk.section_path} | "
            f"Relevance: {result.score:.2f}]"
        )

        if include_raw and chunk.raw_html:
            parts.append(f"{header}\n{chunk.raw_html}")
        else:
            # Preserve original formatting — textwrap.fill would destroy tables,
            # recipe lists, and bullet points by collapsing newlines.
            parts.append(f"{header}\n{chunk.content}")

    return "\n\n".join(parts)


def build_system_prompt(game_state_str: Optional[str] = None) -> str:
    """
    Build the system prompt with optional game state context.

    Parameters
    ----------
    game_state_str : str, optional
        Human-readable game state description.

    Returns
    -------
    str
        Complete system prompt.
    """
    if game_state_str and game_state_str.strip():
        return (
            f"{SYSTEM_PROMPT.strip()}\n\n"
            f"Player Game State:\n{game_state_str.strip()}"
        )
    return SYSTEM_PROMPT


def build_user_prompt(
    query_text: str,
    results: list[RetrievalResult],
    game_state_str: Optional[str] = None,
    include_raw: bool = False,
) -> str:
    """
    Build the full user prompt with context and question.

    Parameters
    ----------
    query_text : str
        The user's question.
    results : list[RetrievalResult]
        Retrieved wiki chunks.
    game_state_str : str, optional
        Game state for filtering context.
    include_raw : bool
        Include raw HTML in context.

    Returns
    -------
    str
        Complete formatted user prompt ready to send to LLM.
    """
    context = build_context_string(results, include_raw=include_raw)
    game_state = game_state_str or DEFAULT_GAME_STATE

    return USER_PROMPT_TEMPLATE.format(
        context=context,
        game_state=game_state,
        question=query_text,
    )


def format_hint_response(response: str) -> str:
    """
    Clean up LLM response for display as an in-game hint.

    Parameters
    ----------
    response : str
        Raw LLM output.

    Returns
    -------
    str
        Cleaned response suitable for NPC dialog.
    """
    # Remove any thinking tags or tool callouts
    import re
    response = re.sub(r"<[^>]+>", "", response)
    response = response.strip()

    # Allow up to 1500 chars — crafting chains and boss strategies need room.
    # The LLM max_tokens setting already caps the raw output length.
    MAX_HINT_CHARS = 1500
    if len(response) > MAX_HINT_CHARS:
        cutoff = response[:MAX_HINT_CHARS].rfind(". ")
        if cutoff > 100:
            response = response[:cutoff + 1]
        else:
            response = response[:MAX_HINT_CHARS].rsplit(" ", 1)[0] + "..."

    return response
