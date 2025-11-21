from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionType(str, Enum):
    END_TURN = "END_TURN"
    # Later: SUMMON_MONSTER, ATTACK, PLAY_SPELL, SET_TRAP, ACTIVATE_HERO, etc.


@dataclass
class Action:
    type: ActionType
    # Later we’ll add fields like:
    # card_instance_id: str | None = None
    # zone_index: int | None = None
    # attacker_id: str | None = None
    # defender_id: str | None = None
