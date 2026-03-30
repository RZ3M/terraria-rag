"""
CHATBOT/cli.py — Simple interactive CLI chatbot.

Run with:
    python CHATBOT/cli.py [--provider minimax|openrouter] [--game-state]

An interactive CLI for querying the Terraria RAG system. Useful for
testing and out-of-game exploration.
"""

import argparse
import logging
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from COMMON.config import LOG_LEVEL, LOG_FORMAT, DEFAULT_LLM_PROVIDER
from COMMON.types import GameState
from QUERY.query_engine import query

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format=LOG_FORMAT,
)
logger = logging.getLogger("chatbot")


def run_chat(
    provider: str = DEFAULT_LLM_PROVIDER,
    game_state: bool = False,
    verbose: bool = False,
) -> None:
    """
    Run the interactive chat loop.
    """
    print("=" * 60)
    print("  Terraria RAG Chatbot  🦀")
    print("=" * 60)
    print(f"  Provider: {provider}")
    print(f"  Game state filtering: {'ON' if game_state else 'OFF'}")
    print(f"  (type 'quit' or Ctrl+C to exit)")
    print("=" * 60)
    print()

    current_game_state: GameState | None = None

    if game_state:
        print("Setting up game state...")
        current_game_state = _interactive_game_state_setup()
        print()
        print(f"Game state: {current_game_state.to_prompt_string()}")
        print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        if user_input.lower() == "/state" and game_state:
            current_game_state = _interactive_game_state_setup()
            print(f"Updated: {current_game_state.to_prompt_string()}")
            continue

        if user_input.lower() == "/verbose":
            verbose = not verbose
            print(f"Verbose mode: {'ON' if verbose else 'OFF'}")
            continue

        # Run query
        print("Thinking...")
        try:
            result = query(
                question=user_input,
                game_state=current_game_state,
                provider=provider,
                verbose=verbose,
            )
        except Exception as e:
            print(f"Error: {e}")
            continue

        print()
        print(f"🤖 Hint: {result.llm_response}")
        print()
        print(f"  [{result.provider} | {result.latency_ms:.0f}ms | {len(result.retrieved_chunks)} chunks]")
        if verbose and result.retrieved_chunks:
            print("  Sources:")
            for r in result.retrieved_chunks:
                print(f"    - {r.chunk.wiki_title} [{r.chunk.section_path}] (score={r.score:.3f})")
        print()


def _interactive_game_state_setup() -> GameState:
    """Walk through game state setup interactively."""
    gs = GameState()

    # Hardmode
    hm = input("Hardmode? (y/N): ").strip().lower()
    gs.is_hardmode = hm == "y"

    # Moon Lord
    if gs.is_hardmode:
        ml = input("Moon Lord defeated? (y/N): ").strip().lower()
        gs.moon_lord_defeated = ml == "y"

    # Current biomes
    biomes = input("Current biomes (comma-separated): ").strip()
    if biomes:
        gs.current_biomes = [b.strip() for b in biomes.split(",")]

    # Bosses defeated
    bosses = input("Bosses defeated (comma-separated): ").strip()
    if bosses:
        gs.bosses_defeated = [b.strip() for b in bosses.split(",")]

    # Armor tier
    armor = input("Armor tier [Iron/Silver/Gold/Platinum/Hallowed/Shroomite/etc.]: ").strip()
    if armor:
        gs.armor_tier = armor

    # Weapon tier
    weapons = input("Weapons tier [Iron/Gold/Platinum/Hallowed/etc.]: ").strip()
    if weapons:
        gs.weapons_tier = weapons

    return gs


def main() -> None:
    parser = argparse.ArgumentParser(description="Terraria RAG Chatbot CLI")
    parser.add_argument(
        "--provider",
        choices=["minimax", "openrouter"],
        default=DEFAULT_LLM_PROVIDER,
        help="LLM provider to use",
    )
    parser.add_argument(
        "--game-state",
        action="store_true",
        help="Enable game state filtering with interactive setup",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output (show sources)",
    )

    args = parser.parse_args()

    # Check API keys
    if args.provider == "minimax":
        key = os.environ.get("MINIMAX_API_KEY")
        if not key:
            print("WARNING: MINIMAX_API_KEY not set in environment.")
            print("Set it with: export MINIMAX_API_KEY=your_key")
    elif args.provider == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            print("WARNING: OPENROUTER_API_KEY not set in environment.")
            print("Set it with: export OPENROUTER_API_KEY=your_key")

    run_chat(
        provider=args.provider,
        game_state=args.game_state,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
