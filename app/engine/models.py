from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict
import uuid


class CardType(str, Enum):
    MONSTER = "monster"
    SPELL = "spell"
    TRAP = "trap"
    HERO = "hero"


class Phase(str, Enum):
    START = "start"
    DRAW = "draw"
    MAIN = "main"
    BATTLE = "battle"
    END = "end"


class MatchStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class CardInstance:
    """
    A single copy of a card that exists in a match.
    This is the runtime version of a row from `cards` + current battle state.
    """

    instance_id: str
    card_code: str
    name: str
    card_type: CardType
    stars: int
    atk: int
    hp: int
    max_hp: int
    element_id: Optional[int] = None

    # Board state
    face_down: bool = True
    can_attack: bool = False

    # Statuses like "barrier", "frozen", etc.
    # MUST be JSON serializable → list instead of set
    statuses: List[str] = field(default_factory=list)

    # Effects from DB
    effect_tags: List[str] = field(default_factory=list)
    effect_params: dict = field(default_factory=dict)
    
    # Card description/flavor text
    description: Optional[str] = None
    art_asset_id: Optional[str] = None
    flavor_text: Optional[str] = None
    rules_text: Optional[str] = None

    def is_monster(self) -> bool:
        return self.card_type == CardType.MONSTER

    def is_hero(self) -> bool:
        return self.card_type == CardType.HERO

    @staticmethod
    def new_from_definition(
        card_def: dict,
        *,
        face_down: bool = True,
    ) -> "CardInstance":
        """
        Create a runtime card instance from a DB definition.
        """
        instance_id = str(uuid.uuid4())
        card_type = CardType(card_def["card_type"])
        atk = card_def.get("atk") or 0
        hp = card_def.get("hp") or 0

        return CardInstance(
            instance_id=instance_id,
            card_code=card_def["card_code"],
            name=card_def["name"],
            card_type=card_type,
            stars=card_def["stars"],
            atk=atk,
            hp=hp,
            max_hp=hp,
            element_id=card_def.get("element_id"),
            face_down=face_down,
            can_attack=False,
            effect_tags=card_def.get("effect_tags") or [],
            effect_params=card_def.get("effect_params") or {},
            description=card_def.get("description") or card_def.get("rules_text") or None,
            art_asset_id=card_def.get("art_asset_id") or None,
            flavor_text=card_def.get("flavor_text") or None,
            rules_text=card_def.get("rules_text") or None,
        )


@dataclass
class PlayerState:
    """
    Full runtime state for a player during a match.
    """
    player_index: int  # 1 or 2
    name: str
    hp: int = 1500

    # Zones
    deck: List[CardInstance] = field(default_factory=list)
    hand: List[CardInstance] = field(default_factory=list)
    monster_zones: List[Optional[CardInstance]] = field(
        default_factory=lambda: [None, None, None, None]
    )
    spell_trap_zones: List[Optional[CardInstance]] = field(
        default_factory=lambda: [None, None, None, None]
    )
    hero: Optional[CardInstance] = None
    graveyard: List[CardInstance] = field(default_factory=list)
    exile: List[CardInstance] = field(default_factory=list)

    # Hero-related
    hero_charges: int = 0

    def alive(self) -> bool:
        return self.hp > 0


@dataclass
class GameState:
    """
    Complete match state.
    This gets serialized into matches.serialized_game_state.
    """
    match_id: str
    turn: int = 1
    current_player: int = 1
    phase: Phase = Phase.START
    status: MatchStatus = MatchStatus.IN_PROGRESS
    winner: Optional[int] = None  # 1, 2, or None

    players: Dict[int, PlayerState] = field(default_factory=dict)

    # Action/event log
    log: List[dict] = field(default_factory=list)

    def get_player(self, index: int) -> PlayerState:
        return self.players[index]

    def get_opponent(self, index: int) -> PlayerState:
        return self.players[2 if index == 1 else 1]
