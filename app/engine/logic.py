from __future__ import annotations

from typing import List, Dict, Tuple

from .models import GameState, Phase, MatchStatus
from .actions import Action, ActionType


def apply_action(
    state: GameState,
    player_index: int,
    action: Action,
) -> Tuple[GameState, List[Dict]]:
    """
    Core rules entry point.
    For now we only support END_TURN so we can drive a basic loop.
    Returns the updated GameState and a list of events for the client.
    """
    events: List[Dict] = []

    if state.status != MatchStatus.IN_PROGRESS:
        events.append({
            "type": "ERROR",
            "reason": "MATCH_NOT_IN_PROGRESS"
        })
        return state, events

    if player_index != state.current_player:
        events.append({
            "type": "ERROR",
            "reason": "NOT_YOUR_TURN"
        })
        return state, events

    if action.type == ActionType.END_TURN:
        _handle_end_turn(state, player_index, events)
    else:
        events.append({
            "type": "ERROR",
            "reason": f"UNSUPPORTED_ACTION_{action.type}"
        })

    return state, events


def _handle_end_turn(
    state: GameState,
    player_index: int,
    events: List[Dict],
) -> None:
    """
    Simple v0 end turn:
    - Advance turn counter
    - Switch current_player
    - Reset phase to START
    """
    events.append({
        "type": "END_TURN",
        "player": player_index,
        "turn": state.turn,
    })

    # Advance to next player
    next_player = 1 if player_index == 2 else 2
    state.turn += 1
    state.current_player = next_player
    state.phase = Phase.START

    events.append({
        "type": "TURN_STARTED",
        "player": next_player,
        "turn": state.turn,
        "phase": state.phase.value,
    })
