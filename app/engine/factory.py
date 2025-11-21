from __future__ import annotations

import random
from typing import List, Dict

from .models import (
    CardInstance,
    PlayerState,
    GameState,
    CardType
)


# Temporary constant (we can make this configurable later)
STARTING_HAND_SIZE = 5


def build_deck_instances(deck_cards: List[dict]) -> List[CardInstance]:
    """
    deck_cards is a list of dicts representing card definitions:
    [
        { "card_code": "...", "name": "...", "card_type": "monster", "atk": 100, "hp": 100, ... },
        ...
    ]

    This produces a shuffled list of CardInstance objects.
    """
    instances: List[CardInstance] = []

    for card_def in deck_cards:
        instance = CardInstance.new_from_definition(card_def)
        instances.append(instance)

    random.shuffle(instances)
    return instances


def draw_cards(deck: List[CardInstance], n: int) -> List[CardInstance]:
    """
    Removes top n cards from the deck and returns them.
    """
    drawn = deck[:n]
    del deck[:n]
    return drawn


def initialize_player(
    player_index: int,
    player_name: str,
    deck_def: List[dict]
) -> PlayerState:
    """
    Create PlayerState:
    - Build deck from card definitions
    - Draw a starting hand
    """
    deck_instances = build_deck_instances(deck_def)
    hand = draw_cards(deck_instances, STARTING_HAND_SIZE)

    p = PlayerState(
        player_index=player_index,
        name=player_name,
        deck=deck_instances,
        hand=hand
    )

    return p


def create_new_game_state(
    match_id: str,
    player1_name: str,
    player1_deck: List[dict],
    player2_name: str,
    player2_deck: List[dict]
) -> GameState:
    """
    The master factory function.
    Given deck definitions for P1 + P2,
    returns a fully initialized GameState:
    - Turn = 1
    - Current player = 1
    - Both players have 5-card hands
    - Hero slots empty
    """

    p1_state = initialize_player(
        player_index=1,
        player_name=player1_name,
        deck_def=player1_deck
    )

    p2_state = initialize_player(
        player_index=2,
        player_name=player2_name,
        deck_def=player2_deck
    )

    game_state = GameState(
        match_id=match_id,
        turn=1,
        current_player=1,
        players={
            1: p1_state,
            2: p2_state
        }
    )

    # Log event for clients/UI
    game_state.log.append({
        "type": "GAME_INIT",
        "player1": player1_name,
        "player2": player2_name
    })

    return game_state
