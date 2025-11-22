from __future__ import annotations

import random
from typing import List, Dict, Any

from app.engine.models import (
    CardInstance,
    PlayerState,
    GameState,
    Phase,
    MatchStatus,
)


def build_player_state(
    *,
    player_index: int,
    name: str,
    deck_defs: List[Dict[str, Any]],
) -> PlayerState:
    """
    Build a PlayerState from a list of card definitions.

    `deck_defs` is expected to be a list of dicts coming from `load_deck_card_defs`,
    each with fields like:
      - card_code
      - name
      - card_type      (string: "monster" | "spell" | "trap" | "hero")
      - stars
      - atk
      - hp
      - element_id
      - effect_tags
      - effect_params
    """

    # Turn deck defs into runtime instances
    deck_instances: List[CardInstance] = [
        CardInstance.new_from_definition(card_def, face_down=True)
        for card_def in deck_defs
    ]

    # Shuffle deck
    random.shuffle(deck_instances)

    # Draw starting hand (5 cards)
    starting_hand: List[CardInstance] = []
    draws = min(5, len(deck_instances))
    for _ in range(draws):
        starting_hand.append(deck_instances.pop(0))

    # Create the player state
    player_state = PlayerState(
        player_index=player_index,
        name=name,
        hp=1500,
        deck=deck_instances,
        hand=starting_hand,
        # monster_zones, spell_trap_zones, hero, graveyard, exile,
        # hero_charges are all handled by the dataclass defaults.
    )

    return player_state


def create_new_game_state(
    *,
    match_id: str,
    player1_name: str,
    player2_name: str,
    deck1_defs: List[Dict[str, Any]],
    deck2_defs: List[Dict[str, Any]],
) -> GameState:
    """
    Factory to build a brand new GameState for a 1v1 match.

    - match_id: UUID for this match (stored in `matches` table)
    - player1_name: human player display name (e.g., "Nabbed")
    - player2_name: NPC or other player's display name (e.g., "Ornn")
    - deck1_defs: list of card definitions for player 1's deck
    - deck2_defs: list of card definitions for player 2's deck
    """

    p1_state = build_player_state(
        player_index=1,
        name=player1_name,
        deck_defs=deck1_defs,
    )

    p2_state = build_player_state(
        player_index=2,
        name=player2_name,
        deck_defs=deck2_defs,
    )

    game_state = GameState(
        match_id=match_id,
        turn=1,
        current_player=1,
        phase=Phase.START,
        status=MatchStatus.IN_PROGRESS,
        winner=None,
        players={
            1: p1_state,
            2: p2_state,
        },
        log=[],
    )

    # Initial log entry
    game_state.log.append(
        {
            "type": "GAME_INIT",
            "player1": player1_name,
            "player2": player2_name,
        }
    )

    return game_state
