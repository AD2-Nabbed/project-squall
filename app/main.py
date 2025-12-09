from __future__ import annotations

from uuid import uuid4
from typing import Any, Dict, Literal, List, Optional, Tuple
import json  # for parsing effect_params if stored as text
import random

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.engine.factory import create_new_game_state
from app.engine.models import GameState, CardInstance
from app.db.supabase_client import supabase
from app.db.decks import load_deck_card_defs
from app.db.npcs import pick_random_npc_with_deck
from app.engine.effects.resolver import resolve_card_effects, EffectContext, EffectResult
from app.engine.game_state_helpers import find_monster_by_instance_id
from app.engine.ai_controller import get_ai_action


app = FastAPI(
    title="Project Squall Battle Server",
    version="0.1.0",
)

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Helpers to serialize GameState -> plain JSON dict (for Supabase)
# -------------------------------------------------------------------


def card_instance_to_dict(ci: CardInstance) -> Dict[str, Any]:
    """
    Convert a CardInstance dataclass into a JSON-serializable dict.
    """
    statuses = ci.statuses
    if isinstance(statuses, set):
        statuses = list(statuses)

    return {
        "instance_id": ci.instance_id,
        "card_code": ci.card_code,
        "name": ci.name,
        "card_type": ci.card_type.value,
        "stars": ci.stars,
        "atk": ci.atk,
        "hp": ci.hp,
        "max_hp": ci.max_hp,
        "element_id": ci.element_id,
        "face_down": ci.face_down,
        "can_attack": ci.can_attack,
        "statuses": statuses,
        "effect_tags": ci.effect_tags,
        "effect_params": ci.effect_params,
        "description": ci.description or "",
        "art_asset_id": ci.art_asset_id or "",
        "flavor_text": ci.flavor_text or "",
        "rules_text": ci.rules_text or "",
    }


def game_state_to_dict(gs: GameState) -> Dict[str, Any]:
    """
    Convert a GameState dataclass into a JSON-serializable dict.
    Handles enums and nested dataclasses explicitly.
    """
    players_dict: Dict[str, Any] = {}
    for idx, p in gs.players.items():
        players_dict[str(idx)] = {
            "player_index": p.player_index,
            "name": p.name,
            "hp": p.hp,
            "deck": [card_instance_to_dict(c) for c in p.deck],
            "hand": [card_instance_to_dict(c) for c in p.hand],
            "monster_zones": [
                card_instance_to_dict(c) if c is not None else None
                for c in p.monster_zones
            ],
            "spell_trap_zones": [
                card_instance_to_dict(c) if c is not None else None
                for c in p.spell_trap_zones
            ],
            "hero": card_instance_to_dict(p.hero) if p.hero is not None else None,
            "graveyard": [card_instance_to_dict(c) for c in p.graveyard],
            "exile": [card_instance_to_dict(c) for c in p.exile],
            "hero_charges": p.hero_charges,
        }

    return {
        "match_id": gs.match_id,
        "turn": gs.turn,
        "current_player": gs.current_player,
        "phase": gs.phase.value,
        "status": gs.status.value,
        "winner": gs.winner,
        "players": players_dict,
        "log": gs.log,
    }


# -------------------------------------------------------------------
# Request models
# -------------------------------------------------------------------


class BattleStartRequest(BaseModel):
    player_id: str        # players.id (uuid)
    deck_id: str          # decks.id chosen by the player
    mode: str = "PVE"     # "PVE" or "PVP"
    npc_id: Optional[str] = None  # optional: force a specific NPC later (PVE only)
    player2_id: Optional[str] = None  # optional: player 2 ID for PVP mode
    player2_deck_id: Optional[str] = None  # optional: player 2 deck ID for PVP mode


class PlayMonsterPayload(BaseModel):
    card_instance_id: str
    zone_index: int  # 0-3 for now
    tribute_instance_ids: List[str] = []


class PlaySpellPayload(BaseModel):
    """
    Simple spell payload:
    - card_instance_id: spell card in your hand
    - target_player_index: optional player target (1 or 2)
    - target_monster_instance_id: optional monster target
    We keep it flexible so spells can choose one or both.
    """
    card_instance_id: str
    target_player_index: Optional[int] = None
    target_monster_instance_id: Optional[str] = None


class PlayTrapPayload(BaseModel):
    """
    Trap payload:
    - card_instance_id: trap card in your hand
    - zone_index: spell/trap zone to place it in (0-3)
    """
    card_instance_id: str
    zone_index: int


class ActivateHeroAbilityPayload(BaseModel):
    """
    Hero ability activation payload.
    Optional targets depending on the hero's active ability definition.
    """
    target_player_index: Optional[int] = None
    target_monster_instance_id: Optional[str] = None


class ActivateTrapPayload(BaseModel):
    """
    Manual trap activation for v0 testing.

    - trap_instance_id: trap currently set in your spell/trap zone
    - target_player_index / target_monster_instance_id: optional targets
      depending on the trap's effects.
    """
    trap_instance_id: str
    target_player_index: Optional[int] = None
    target_monster_instance_id: Optional[str] = None


class AttackMonsterPayload(BaseModel):
    attacker_instance_id: str
    defender_instance_id: str  # must target a monster on the opponent's field


class AttackPlayerPayload(BaseModel):
    attacker_instance_id: str


class BattleActionRequest(BaseModel):
    match_id: str
    player_index: int  # 1 or 2
    action: Literal[
        "END_TURN",
        "PLAY_MONSTER",
        "PLAY_SPELL",
        "PLAY_TRAP",
        "ACTIVATE_TRAP",
        "ACTIVATE_HERO_ABILITY",
        "ATTACK_MONSTER",
        "ATTACK_PLAYER",
    ]
    play_monster: Optional[PlayMonsterPayload] = None
    play_spell: Optional[PlaySpellPayload] = None
    play_trap: Optional[PlayTrapPayload] = None
    activate_trap: Optional[ActivateTrapPayload] = None
    activate_hero_ability: Optional[ActivateHeroAbilityPayload] = None
    attack_monster: Optional[AttackMonsterPayload] = None
    attack_player: Optional[AttackPlayerPayload] = None


# -------------------------------------------------------------------
# Simple health / test endpoints
# -------------------------------------------------------------------


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/test/supabase")
def test_supabase():
    result = supabase.table("players").select("*").limit(1).execute()
    return {"ok": True, "data": result.data}


# -------------------------------------------------------------------
# Helpers for battle_action
# -------------------------------------------------------------------


def _other_player_index(idx: int) -> int:
    return 2 if idx == 1 else 1


def _check_lethal_after_noncombat(
    game_state: Dict[str, Any],
    players: Dict[str, Any],
    log: List[Dict[str, Any]],
    reason: str,
) -> None:
    """
    Shared lethal check for non-combat effects (spells/traps).
    Uses same semantics as ATTACK_* branches: 0 or below = dead.
    """
    p1_hp = players.get("1", {}).get("hp", 0)
    p2_hp = players.get("2", {}).get("hp", 0)

    p1_dead = p1_hp <= 0
    p2_dead = p2_hp <= 0

    if not p1_dead and not p2_dead:
        return

    game_state["status"] = "completed"

    if p1_dead and p2_dead:
        game_state["winner"] = None
        log.append(
            {
                "type": "MATCH_END",
                "winner": None,
                "reason": f"{reason}_double_lethal",
                "player1_hp": p1_hp,
                "player2_hp": p2_hp,
            }
        )
    elif p2_dead:
        game_state["winner"] = 1
        log.append(
            {
                "type": "MATCH_END",
                "winner": 1,
                "reason": reason,
                "player1_hp": p1_hp,
                "player2_hp": p2_hp,
            }
        )
    elif p1_dead:
        game_state["winner"] = 2
        log.append(
            {
                "type": "MATCH_END",
                "winner": 2,
                "reason": reason,
                "player1_hp": p1_hp,
                "player2_hp": p2_hp,
            }
        )


def _handle_destroyed_monsters(
    game_state: Dict[str, Any],
    destroyed_monsters: List[Tuple[int, int]],
) -> None:
    """Move destroyed monsters to graveyard."""
    players = game_state.get("players", {})
    for player_idx, zone_idx in destroyed_monsters:
        pkey_destroyed = str(player_idx)
        destroyed_state = players.get(pkey_destroyed)
        if not destroyed_state:
            continue
        
        monster_zones = destroyed_state.get("monster_zones") or []
        if zone_idx < len(monster_zones) and monster_zones[zone_idx] is not None:
            destroyed_card = monster_zones[zone_idx]
            graveyard = destroyed_state.get("graveyard") or []
            graveyard.append(destroyed_card)
            monster_zones[zone_idx] = None
            destroyed_state["graveyard"] = graveyard
            destroyed_state["monster_zones"] = monster_zones
            players[pkey_destroyed] = destroyed_state

    # Passive: Gain hero charges when any monster dies
    for pkey, p_state in players.items():
        hero = p_state.get("hero")
        if not hero:
            continue
        effect_params = hero.get("effect_params") or {}
        if isinstance(effect_params, str):
            try:
                import json
                effect_params = json.loads(effect_params)
            except Exception:
                effect_params = {}
        passive_charge = effect_params.get("passive_on_monster_death")
        if passive_charge and passive_charge.get("keyword") == "HERO_PASSIVE_GAIN_CHARGE_ON_DEATH":
            amount = int(passive_charge.get("amount", 0))
            if amount > 0 and destroyed_monsters:
                gained = amount * len(destroyed_monsters)
                hero["hero_charges"] = int(hero.get("hero_charges", 0) or 0) + gained
                # Add log entry
                log = game_state.get("log") or []
                log.append(
                    {
                        "type": "HERO_CHARGE_GAINED",
                        "player": int(pkey),
                        "hero_instance_id": hero.get("instance_id"),
                        "amount": gained,
                        "reason": "MONSTER_DEATH",
                    }
                )
                game_state["log"] = log
                p_state["hero"] = hero
                players[pkey] = p_state


def _fetch_card_variant(card_code: str, element_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """
    Fetch a specific element variant of a card from Supabase.
    Returns the variant row or None if not found.
    """
    if element_id is None:
        return None
    try:
        resp = (
            supabase.table("cards")
            .select(
                "card_code, name, card_type_id, stars, atk, hp, element_id, effect_tags, effect_params, art_asset_id, flavor_text, rules_text"
            )
            .eq("card_code", card_code)
            .eq("element_id", element_id)
            .single()
            .execute()
        )
        return resp.data
    except Exception:
        # No variant found for this card_code + element_id combination
        # Return None to indicate the card should remain in its current form
        return None


def _apply_element_variant(card: Dict[str, Any], element_id: Optional[int]) -> Dict[str, Any]:
    """
    Mutate the card dict in-place to its element-specific variant if available.
    Preserves instance_id and runtime fields like statuses / flags.
    """
    if element_id is None:
        return card
    variant = _fetch_card_variant(card.get("card_code"), element_id)
    if not variant:
        return card

    # Map card_type_id to string if needed
    ctype = variant.get("card_type_id")
    if ctype == 1:
        v_card_type = "monster"
    elif ctype == 2:
        v_card_type = "spell"
    elif ctype == 3:
        v_card_type = "trap"
    elif ctype == 4:
        v_card_type = "hero"
    else:
        v_card_type = card.get("card_type")

    card["name"] = variant.get("name", card.get("name"))
    card["card_type"] = v_card_type
    card["stars"] = variant.get("stars", card.get("stars", 0))
    card["atk"] = variant.get("atk", card.get("atk", 0))
    card["hp"] = variant.get("hp", card.get("hp", 0))
    card["max_hp"] = variant.get("hp", card.get("hp", 0))
    card["element_id"] = variant.get("element_id", element_id)
    card["effect_tags"] = variant.get("effect_tags") or card.get("effect_tags") or []
    card["effect_params"] = variant.get("effect_params") or card.get("effect_params") or {}
    card["art_asset_id"] = variant.get("art_asset_id") or card.get("art_asset_id", "")
    card["flavor_text"] = variant.get("flavor_text") or card.get("flavor_text", "")
    card["rules_text"] = variant.get("rules_text") or card.get("rules_text", "")
    card["description"] = variant.get("rules_text") or card.get("description", "")
    return card


def _apply_element_variant_preserve_runtime(card: Dict[str, Any], element_id: Optional[int]) -> Dict[str, Any]:
    """
    Wraps _apply_element_variant but preserves runtime fields on the card.
    Runtime fields: instance_id, statuses, face_down, can_attack, summoned_turn, hero_charges.
    """
    if element_id is None:
        return card

    runtime = {
        "instance_id": card.get("instance_id"),
        "statuses": card.get("statuses"),
        "face_down": card.get("face_down"),
        "can_attack": card.get("can_attack"),
        "summoned_turn": card.get("summoned_turn"),
        "hero_charges": card.get("hero_charges"),
    }
    _apply_element_variant(card, element_id)
    for k, v in runtime.items():
        if v is not None:
            card[k] = v
    return card


def _retarget_player_cards_to_element(p_state: Dict[str, Any], element_id: Optional[int]) -> None:
    """
    Convert a player's deck/hand/board/spell_trap cards to the given element variant (if available),
    preserving runtime fields. Does not modify the hero itself.
    """
    if element_id is None:
        return

    # Deck
    deck = p_state.get("deck") or []
    for idx, card in enumerate(deck):
        if card.get("card_type") == "hero" or card.get("stars") == 6:
            continue
        deck[idx] = _apply_element_variant_preserve_runtime(card, element_id)
    p_state["deck"] = deck

    # Hand
    hand = p_state.get("hand") or []
    for idx, card in enumerate(hand):
        if card.get("card_type") == "hero" or card.get("stars") == 6:
            continue
        hand[idx] = _apply_element_variant_preserve_runtime(card, element_id)
    p_state["hand"] = hand

    # Monster zones
    monster_zones = p_state.get("monster_zones") or []
    for idx, card in enumerate(monster_zones):
        if card is None:
            continue
        if card.get("card_type") == "hero" or card.get("stars") == 6:
            continue
        monster_zones[idx] = _apply_element_variant_preserve_runtime(card, element_id)
    p_state["monster_zones"] = monster_zones

    # Spell/trap zones (convert spells/traps too)
    st_zones = p_state.get("spell_trap_zones") or []
    for idx, card in enumerate(st_zones):
        if card is None:
            continue
        st_zones[idx] = _apply_element_variant_preserve_runtime(card, element_id)
    p_state["spell_trap_zones"] = st_zones


def _apply_element_variants_to_deck(
    deck_defs: List[Dict[str, Any]],
    element_id: Optional[int],
) -> List[Dict[str, Any]]:
    """
    Return a new deck_def list where each card is swapped to its element-specific
    variant if available for the given element_id. Heroes are left untouched.
    Uses a small cache to avoid repeated DB hits per card_code.
    """
    if element_id is None:
        return deck_defs

    cache: Dict[str, Optional[Dict[str, Any]]] = {}
    transformed: List[Dict[str, Any]] = []

    for card_def in deck_defs:
        # Leave hero as-is
        if card_def.get("card_type") == "hero" or card_def.get("stars") == 6:
            transformed.append(card_def)
            continue

        code = card_def.get("card_code")
        if code in cache:
            variant = cache[code]
        else:
            variant = _fetch_card_variant(code, element_id)
            cache[code] = variant

        if variant:
            new_def = card_def.copy()
            # Map card_type_id to code
            ctype = variant.get("card_type_id")
            if ctype == 1:
                v_card_type = "monster"
            elif ctype == 2:
                v_card_type = "spell"
            elif ctype == 3:
                v_card_type = "trap"
            elif ctype == 4:
                v_card_type = "hero"
            else:
                v_card_type = new_def.get("card_type")

            new_def["name"] = variant.get("name", new_def.get("name"))
            new_def["card_type"] = v_card_type
            new_def["stars"] = variant.get("stars", new_def.get("stars", 0))
            new_def["atk"] = variant.get("atk", new_def.get("atk", 0))
            new_def["hp"] = variant.get("hp", new_def.get("hp", 0))
            new_def["element_id"] = variant.get("element_id", element_id)
            new_def["effect_tags"] = variant.get("effect_tags") or new_def.get("effect_tags") or []
            new_def["effect_params"] = variant.get("effect_params") or new_def.get("effect_params") or {}
            transformed.append(new_def)
        else:
            transformed.append(card_def)

    return transformed


# -------------------------------------------------------------------
# Battle: Start a new match vs NPC
# -------------------------------------------------------------------


@app.post("/battle/start")
def battle_start(payload: BattleStartRequest) -> Dict[str, Any]:
    """
    Start a new battle:
    - Validate player + deck
    - Pick an NPC with a deck (or a specific one if npc_id provided)
    - Load both decks from Supabase
    - Create a fresh GameState via engine.factory
    - Store match in `matches` table
    - Return match_id + initial game_state
    """

    # 1) Validate player exists
    player_resp = (
        supabase.table("players")
        .select("id, gamer_tag")
        .eq("id", payload.player_id)
        .single()
        .execute()
    )
    player_row = player_resp.data
    if not player_row:
        raise HTTPException(status_code=404, detail="Player not found")

    # 2) Validate the chosen deck belongs to this player
    deck_resp = (
        supabase.table("decks")
        .select("id, name, owner_id")
        .eq("id", payload.deck_id)
        .single()
        .execute()
    )

    deck_row = deck_resp.data
    if not deck_row:
        raise HTTPException(status_code=404, detail="Deck not found")

    owner_id = deck_row.get("owner_id")
    if owner_id is not None and owner_id != payload.player_id:
        raise HTTPException(status_code=403, detail="Deck does not belong to this player")

    # 3) Handle PVE vs PVP mode
    match_mode = payload.mode.upper() if payload.mode else "PVE"
    
    if match_mode == "PVE":
        # PVE: Pick NPC (random or forced)
        npc = pick_random_npc_with_deck(payload.npc_id)
        if not npc:
            raise HTTPException(status_code=404, detail="No NPC with a deck found")

        player2_name = npc["display_name"]
        player2_deck_id = npc["deck_id"]
        npc_id = npc["id"]
        player2_id = None
    elif match_mode == "PVP":
        # PVP: Validate player 2
        if not payload.player2_id or not payload.player2_deck_id:
            raise HTTPException(status_code=400, detail="PVP mode requires player2_id and player2_deck_id")
        
        player2_resp = (
            supabase.table("players")
            .select("id, gamer_tag")
            .eq("id", payload.player2_id)
            .single()
            .execute()
        )
        player2_row = player2_resp.data
        if not player2_row:
            raise HTTPException(status_code=404, detail="Player 2 not found")
        
        # Validate player 2's deck
        player2_deck_resp = (
            supabase.table("decks")
            .select("id, name, owner_id")
            .eq("id", payload.player2_deck_id)
            .single()
            .execute()
        )
        player2_deck_row = player2_deck_resp.data
        if not player2_deck_row:
            raise HTTPException(status_code=404, detail="Player 2 deck not found")
        
        player2_deck_owner = player2_deck_row.get("owner_id")
        if player2_deck_owner is not None and player2_deck_owner != payload.player2_id:
            raise HTTPException(status_code=403, detail="Player 2 deck does not belong to player 2")
        
        player2_name = player2_row["gamer_tag"]
        player2_deck_id = payload.player2_deck_id
        npc_id = None
        player2_id = payload.player2_id
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {match_mode}. Must be 'PVE' or 'PVP'")

    # 4) Load deck card definitions for both players
    player_deck_defs = load_deck_card_defs(payload.deck_id)
    player2_deck_defs = load_deck_card_defs(player2_deck_id)

    if not player_deck_defs:
        raise HTTPException(status_code=400, detail="Player deck has no cards")

    if not player2_deck_defs:
        raise HTTPException(status_code=400, detail="Player 2 deck has no cards")

    # 5) Create a new GameState via the engine
    match_id = str(uuid4())

    game_state: GameState = create_new_game_state(
        match_id=match_id,
        player1_name=player_row["gamer_tag"],
        player2_name=player2_name,
        deck1_defs=player_deck_defs,
        deck2_defs=player2_deck_defs,
    )

    game_state_dict = game_state_to_dict(game_state)

    # 6) Persist match in Supabase
    match_record = {
        "id": match_id,
        "player1_id": payload.player_id,
        "mode": match_mode,
        "status": "in_progress",
        "serialized_game_state": game_state_dict,
    }
    if match_mode == "PVE":
        match_record["npc_id"] = npc_id
    elif match_mode == "PVP":
        match_record["player2_id"] = player2_id
    
    supabase.table("matches").insert(match_record).execute()

    # 7) Return initial state
    return {
        "match_id": match_id,
        "game_state": game_state_dict,
    }


# -------------------------------------------------------------------
# Battle: Take an action
# -------------------------------------------------------------------


@app.post("/battle/action")
def battle_action(payload: BattleActionRequest) -> Dict[str, Any]:
    """
    v0 action endpoint:
    - END_TURN
    - PLAY_MONSTER
    - PLAY_SPELL
    - PLAY_TRAP
    - ACTIVATE_TRAP
    - ATTACK_MONSTER
    - ATTACK_PLAYER
    Loads match.game_state from Supabase, mutates, saves back, returns updated state.
    """

    # 1) Load the match + serialized_game_state
    match_resp = (
        supabase.table("matches")
        .select("id, status, serialized_game_state, mode")
        .eq("id", payload.match_id)
        .single()
        .execute()
    )
    match_row = match_resp.data
    if not match_row:
        raise HTTPException(status_code=404, detail="Match not found")

    if match_row.get("status") != "in_progress":
        raise HTTPException(status_code=400, detail="Match is not in progress")

    game_state = match_row.get("serialized_game_state")
    if not game_state:
        raise HTTPException(status_code=500, detail="Match has no game state stored")

    # Also respect the status inside serialized game_state
    if game_state.get("status") != "in_progress":
        raise HTTPException(status_code=400, detail="Match is not in progress")

    # 2) Basic validation: is it this player's turn?
    current_player = game_state.get("current_player")
    if current_player != payload.player_index:
        raise HTTPException(status_code=400, detail="It is not this player's turn")

    players = game_state.get("players") or {}
    pkey = str(payload.player_index)
    if pkey not in players:
        raise HTTPException(status_code=500, detail="Player state missing")

    # Convenience handles
    log: List[Dict[str, Any]] = game_state.get("log") or []
    game_state["log"] = log  # ensure backref

    # ----------------------------------------------------------------
    # END_TURN
    # ----------------------------------------------------------------
    if payload.action == "END_TURN":
        next_player = 2 if current_player == 1 else 1

        # Apply end-of-turn hero passives for the player ending their turn
        _apply_end_turn_passives(game_state, current_player, log)

        # Bump turn counter
        game_state["turn"] = int(game_state.get("turn", 1)) + 1
        game_state["current_player"] = next_player

        # ---- START OF TURN for next_player (Rule 3) ----
        nkey = str(next_player)
        p_state = players.get(nkey)
        if p_state is None:
            raise HTTPException(status_code=500, detail="Next player state missing")

        # Rule 3: Flip face-down monsters from last turn
        # Rule 5: Face-down monsters flip automatically at start of controller's next turn
        monster_zones = p_state.get("monster_zones") or []
        for slot in monster_zones:
            if slot is None:
                continue
            
            # Flip face-down monsters face-up
            if slot.get("face_down", False):
                slot["face_down"] = False
            
            # Rule 3: All face-up monsters refresh (can_attack = True)
            # BUT: Rule 4: 1-3 star monsters summoned this turn cannot attack
            # We track summoned_turn to know if it was just summoned
            summoned_turn = slot.get("summoned_turn")
            if slot.get("hp", 0) > 0:
                # If summoned this turn, cannot attack
                if summoned_turn == game_state["turn"]:
                    slot["can_attack"] = False
                else:
                    slot["can_attack"] = True
        
        p_state["monster_zones"] = monster_zones

        # Rule 3: Resolve duration-based statuses
        _tick_statuses_on_board(p_state)

        # Rule 3: Draw 2 cards (with reshuffle if needed)
        _draw_with_reshuffle(p_state, 2)

        # Reset per-turn action limits
        turn_state = game_state.setdefault("turn_state", {})
        turn_state[nkey] = {
            "summons": 0,
            "spells_traps": 0,
            "hero_ability": 0,
            "turn": game_state["turn"],
        }

        players[nkey] = p_state
        game_state["players"] = players

        # Set phase to MAIN for the new active player
        game_state["phase"] = "main"

        # Log the event
        log.append(
            {
                "type": "END_TURN",
                "from_player": payload.player_index,
                "to_player": next_player,
                "turn": game_state["turn"],
                "phase": game_state["phase"],
            }
        )

    # ----------------------------------------------------------------
    # PLAY_MONSTER
    # ----------------------------------------------------------------
    elif payload.action == "PLAY_MONSTER":
        if payload.play_monster is None:
            raise HTTPException(status_code=400, detail="Missing play_monster payload")

        pm = payload.play_monster
        p_state = players[pkey]

        # Check per-turn summon limit (Rule 13)
        turn_state = game_state.setdefault("turn_state", {})
        p_turn = turn_state.setdefault(pkey, {"summons": 0, "spells_traps": 0, "hero_ability": 0, "turn": game_state["turn"]})
        if p_turn["turn"] != game_state["turn"]:
            p_turn = {"summons": 0, "spells_traps": 0, "hero_ability": 0, "turn": game_state["turn"]}
        
        if p_turn["summons"] >= 1:
            raise HTTPException(status_code=400, detail="Summon limit reached (1 per turn)")

        hand = p_state.get("hand") or []
        # Filter out None or invalid entries that might not have instance_id
        hand = [c for c in hand if c is not None and isinstance(c, dict) and c.get("instance_id")]
        hand_idx = next(
            (i for i, c in enumerate(hand) if c.get("instance_id") == pm.card_instance_id),
            None,
        )
        if hand_idx is None:
            raise HTTPException(status_code=400, detail="Card not in hand")

        card = hand.pop(hand_idx)
        # Update hand in state after filtering
        p_state["hand"] = hand
        card_type = card.get("card_type")
        stars = card.get("stars", 0)

        # If a hero has set an active element, transform this card to that variant
        active_element = p_state.get("active_element")
        card = _apply_element_variant(card, active_element)
        card_type = card.get("card_type")
        stars = card.get("stars", stars)

        # Rule 2: Hero handling (6-star, card_type "hero")
        if card_type == "hero" or stars == 6:
            # Hero requires 2 tributes
            tribute_ids = pm.tribute_instance_ids or []
            if len(tribute_ids) != 2:
                raise HTTPException(status_code=400, detail="Hero requires exactly 2 tributes")

            # Check hero zone is empty
            if p_state.get("hero") is not None:
                raise HTTPException(status_code=400, detail="Hero zone already occupied")

            # Remove tributes from monster_zones
            monster_zones = p_state.get("monster_zones") or []
            graveyard = p_state.get("graveyard") or []
            for tid in tribute_ids:
                found = False
                for mz_index, mz_card in enumerate(monster_zones):
                    if mz_card is not None and mz_card["instance_id"] == tid:
                        graveyard.append(mz_card)
                        monster_zones[mz_index] = None
                        found = True
                        break
                if not found:
                    raise HTTPException(status_code=409, detail="Selected tribute is no longer on the board. Please reselect tributes.")

            # Place hero in hero zone
            card["face_down"] = False
            card["can_attack"] = False  # Rule 2: Heroes cannot attack
            card["summoned_turn"] = game_state["turn"]

            p_state["hero"] = card
            p_state["monster_zones"] = monster_zones
            p_state["graveyard"] = graveyard
            p_state["hand"] = hand
            p_state["active_element"] = card.get("element_id")
            # Convert existing deck/hand/board/spells to the hero element
            _retarget_player_cards_to_element(p_state, p_state["active_element"])
            players[pkey] = p_state
            game_state["players"] = players

            # Apply hero passive aura effects (e.g., +ATK/+HP to all monsters)
            # Pass None for target_monster_zone_index to apply to all existing monsters
            _apply_hero_passive_aura(game_state, payload.player_index, card, log, target_monster_zone_index=None)

            p_turn["summons"] = 1
            turn_state[pkey] = p_turn

            log.append(
                {
                    "type": "PLAY_HERO",
                    "player": payload.player_index,
                    "card_instance_id": pm.card_instance_id,
                    "card_name": card.get("name"),
                    "tributes": tribute_ids,
                }
            )
        
        # Rule 4: Stars 1-3: No tribute, face-down, cannot attack
        elif 1 <= stars <= 3:
            monster_zones = p_state.get("monster_zones") or []
            if pm.zone_index < 0 or pm.zone_index >= len(monster_zones):
                raise HTTPException(status_code=400, detail="Invalid monster zone index")
            
            if monster_zones[pm.zone_index] is not None:
                raise HTTPException(status_code=400, detail="Monster zone is already occupied")
            
            # No tribute required
            tribute_ids = pm.tribute_instance_ids or []
            if tribute_ids:
                raise HTTPException(status_code=400, detail="1-3 star monsters do not require tributes")
            
            # Place face-down, cannot attack
            card["face_down"] = True
            card["can_attack"] = False
            card["summoned_turn"] = game_state["turn"]
            
            monster_zones[pm.zone_index] = card
            
            # Apply hero passive aura if hero is on field
            hero = p_state.get("hero")
            if hero:
                _apply_hero_passive_aura(game_state, payload.player_index, hero, log, target_monster_zone_index=pm.zone_index)
                # Re-fetch the card after aura application
                monster_zones = p_state.get("monster_zones") or []
                card = monster_zones[pm.zone_index]
            
            p_state["monster_zones"] = monster_zones
            p_state["hand"] = hand
            players[pkey] = p_state
            game_state["players"] = players
            
            p_turn["summons"] = 1
            turn_state[pkey] = p_turn
            
            log.append(
                {
                    "type": "PLAY_MONSTER",
                    "player": payload.player_index,
                    "card_instance_id": pm.card_instance_id,
                    "card_name": card.get("name"),
                    "zone": pm.zone_index,
                    "stars": stars,
                    "face_down": True,
                }
            )
        
        # Rule 4: Stars 4-5: 1 tribute required, face-up, can attack
        elif stars == 4 or stars == 5:
            monster_zones = p_state.get("monster_zones") or []
            if pm.zone_index < 0 or pm.zone_index >= len(monster_zones):
                raise HTTPException(status_code=400, detail="Invalid monster zone index")
            
            if monster_zones[pm.zone_index] is not None:
                raise HTTPException(status_code=400, detail="Monster zone is already occupied")
            
            tribute_ids = pm.tribute_instance_ids or []
            if len(tribute_ids) != 1:
                raise HTTPException(status_code=400, detail="4-5 star monsters require exactly 1 tribute")
            
            # Remove tribute
            graveyard = p_state.get("graveyard") or []
            for tid in tribute_ids:
                found = False
                for mz_index, mz_card in enumerate(monster_zones):
                    if mz_card is not None and mz_card["instance_id"] == tid:
                        graveyard.append(mz_card)
                        monster_zones[mz_index] = None
                        found = True
                        break
                if not found:
                    raise HTTPException(status_code=400, detail=f"Tribute monster {tid} not found")
            
            # Place face-up, can attack immediately
            card["face_down"] = False
            card["can_attack"] = True
            card["summoned_turn"] = game_state["turn"]
            
            monster_zones[pm.zone_index] = card
            
            # Apply hero passive aura if hero is on field
            hero = p_state.get("hero")
            if hero:
                _apply_hero_passive_aura(game_state, payload.player_index, hero, log, target_monster_zone_index=pm.zone_index)
                # Re-fetch the card after aura application
                monster_zones = p_state.get("monster_zones") or []
                card = monster_zones[pm.zone_index]
            
            p_state["monster_zones"] = monster_zones
            p_state["graveyard"] = graveyard
            p_state["hand"] = hand
            players[pkey] = p_state
            game_state["players"] = players
            
            p_turn["summons"] = 1
            turn_state[pkey] = p_turn
            
            log.append(
                {
                    "type": "PLAY_MONSTER",
                    "player": payload.player_index,
                    "card_instance_id": pm.card_instance_id,
                    "card_name": card.get("name"),
                    "zone": pm.zone_index,
                    "stars": stars,
                    "tributes": tribute_ids,
                    "face_down": False,
                }
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Invalid star count: {stars}")

        # Phase goes to MAIN once first monster is played
        game_state["phase"] = "main"

    # ----------------------------------------------------------------
    # PLAY_SPELL
    # ----------------------------------------------------------------
    elif payload.action == "PLAY_SPELL":
        if payload.play_spell is None:
            raise HTTPException(status_code=400, detail="Missing play_spell payload")

        # Rule 13: Check spell/trap play limit (1 per turn combined)
        turn_state = game_state.setdefault("turn_state", {})
        p_turn = turn_state.setdefault(pkey, {"summons": 0, "spells_traps": 0, "hero_ability": 0, "turn": game_state["turn"]})
        if p_turn["turn"] != game_state["turn"]:
            p_turn = {"summons": 0, "spells_traps": 0, "hero_ability": 0, "turn": game_state["turn"]}
        
        if p_turn["spells_traps"] >= 1:
            raise HTTPException(status_code=400, detail="Spell/Trap play limit reached (1 per turn)")

        ps = payload.play_spell
        p_state = players[pkey]

        hand = p_state.get("hand") or []
        # Filter out None or invalid entries that might not have instance_id
        hand = [c for c in hand if c is not None and isinstance(c, dict) and c.get("instance_id")]
        hand_idx = next(
            (i for i, c in enumerate(hand) if c.get("instance_id") == ps.card_instance_id),
            None,
        )
        if hand_idx is None:
            raise HTTPException(status_code=400, detail="Spell card not in hand")

        card = hand[hand_idx]

        card_type = card.get("card_type")
        if card_type not in ("spell", 2, "2"):
            raise HTTPException(status_code=400, detail="Selected card is not a spell")

        # Remove from hand (spells go to graveyard after resolution)
        hand.pop(hand_idx)
        # Update hand in state after filtering and removal
        p_state["hand"] = hand

        # Check for available trap triggers (counter-spell) before resolving
        def_player_idx = _other_player_index(payload.player_index)
        available_traps = _get_available_trap_triggers(
            game_state=game_state,
            defending_player_index=def_player_idx,
            trigger_type="ON_SPELL_CAST",
            trigger_event={"type": "SPELL_CAST", "card_name": card.get("name")},
        )
        if available_traps:
            # Check if this is PVE and the trap belongs to AI - auto-trigger it
            match_mode = match_row.get("mode", "PVE")
            ai_player_index = 2  # NPC is always player 2 in PVE
            if match_mode == "PVE" and def_player_idx == ai_player_index:
                # Auto-trigger AI trap (always say yes)
                trap_to_trigger = available_traps[0]  # Trigger first available trap
                print(f"AI auto-triggering trap: {trap_to_trigger.get('card_name')}")
                
                # Activate the trap directly
                from app.engine.action_handlers import handle_activate_trap
                trap_effect_result = handle_activate_trap(
                    game_state=game_state,
                    player_index=def_player_idx,
                    trap_instance_id=trap_to_trigger["trap_instance_id"],
                    target_player_index=payload.player_index,
                    target_monster_instance_id=ps.target_monster_instance_id,
                    trigger_event={"type": "SPELL_CAST", "card_name": card.get("name"), "spell_card": card, "spell_target": ps.target_monster_instance_id, "spell_caster": payload.player_index},
                )
                
                # Add trap trigger log
                log.append({
                    "type": "TRAP_TRIGGERED",
                    "player": def_player_idx,
                    "trap_instance_id": trap_to_trigger["trap_instance_id"],
                    "card_name": trap_to_trigger.get("card_name"),
                    "trigger_type": "ON_SPELL_CAST",
                    "effects": trap_effect_result.log_events,
                    "cancelled_action": trap_effect_result.cancelled,
                })
                
                # Check if trap cancelled the spell
                if trap_effect_result.cancelled:
                    # Spell was countered - log it and check for reflection
                    log.append({
                        "type": "ACTION_CANCELLED",
                        "reason": "trap_counter",
                        "original_action": "PLAY_SPELL",
                        "spell_name": card.get("name"),
                    })
                    
                    # Check if trap should reflect the spell back
                    reflect_spell = False
                    for eff in trap_effect_result.log_events:
                        if eff.get("type") == "EFFECT_COUNTER_AND_REFLECT_SPELL" or eff.get("reflect_spell"):
                            reflect_spell = True
                            break
                    
                    if reflect_spell:
                        # Reflect spell back to caster's side
                        # Find a target on the caster's side (one of their monsters)
                        caster_state = players.get(pkey)
                        caster_monsters = caster_state.get("monster_zones") or []
                        valid_targets = [m for m in caster_monsters if m is not None and m.get("hp", 0) > 0]
                        
                        if valid_targets:
                            # Auto-select first valid target for reflection
                            reflected_target = valid_targets[0]
                            reflected_target_instance_id = reflected_target.get("instance_id")
                            
                            # Apply the spell effect to the reflected target
                            found = find_monster_by_instance_id(game_state, reflected_target_instance_id)
                            if found:
                                reflected_targets = {
                                    "monster": {
                                        "player_index": found["player_index"],
                                        "zone_index": found["zone_index"],
                                    }
                                }
                                
                                # Create effect context for reflected spell
                                reflected_ctx = EffectContext(
                                    game_state=game_state,
                                    source_player=def_player_idx,  # Trap controller casts the reflected spell
                                    source_card=card,  # Use the original spell card
                                    targets=reflected_targets,
                                )
                                
                                reflected_effect_result = resolve_card_effects(reflected_ctx)
                                _handle_destroyed_monsters(game_state, reflected_effect_result.destroyed_monsters)
                                
                                # Log the reflection
                                log.append({
                                    "type": "SPELL_REFLECTED",
                                    "original_caster": payload.player_index,
                                    "reflected_by": def_player_idx,
                                    "spell_name": card.get("name"),
                                    "target_monster": reflected_target.get("name"),
                                    "effects": reflected_effect_result.log_events,
                                })
                                
                                # Ensure monster zones are updated
                                monster_zones = caster_state.get("monster_zones") or []
                                caster_state["monster_zones"] = monster_zones
                                players[pkey] = caster_state
                                game_state["players"] = players
                                
                                # Check lethal after reflected spell
                                _check_lethal_after_noncombat(
                                    game_state=game_state,
                                    players=players,
                                    log=log,
                                    reason="reflected_spell_effects",
                                )
                    
                    # Move spell to graveyard (it was countered, not resolved)
                    graveyard = p_state.get("graveyard") or []
                    graveyard.append(card)
                    p_state["graveyard"] = graveyard
                    players[pkey] = p_state
                    game_state["players"] = players
                    
                    # Increment spell/trap counter (spell was played, even if countered)
                    p_turn["spells_traps"] = 1
                    turn_state[pkey] = p_turn
                    
                    # Don't resolve the original spell - it was countered
                    # Save and return
                    supabase.table("matches").update({
                        "serialized_game_state": game_state,
                        "status": game_state.get("status", match_row.get("status")),
                    }).eq("id", payload.match_id).execute()
                    
                    return {
                        "match_id": payload.match_id,
                        "game_state": game_state,
                    }
                
                # Check lethal after trap effects
                _check_lethal_after_noncombat(
                    game_state=game_state,
                    players=players,
                    log=log,
                    reason="trap_effects",
                )
                
                # Continue with spell resolution (trap didn't cancel it)
            else:
                # Player trap - return for player decision
                return {
                    "match_id": payload.match_id,
                    "game_state": game_state,
                    "trap_triggers_available": available_traps,
                    "trigger_player_index": def_player_idx,  # Player whose trap is triggering
                    "pending_action": {
                        "action": "PLAY_SPELL",
                        "play_spell": ps.model_dump() if hasattr(ps, "model_dump") else ps.dict(),
                        "player_index": payload.player_index,
                    },
                    "trigger_type": "ON_SPELL_CAST",
                    "trigger_event": {
                        "type": "SPELL_CAST",
                        "card_name": card.get("name"),
                        "spell_card": card,
                        "spell_target": ps.target_monster_instance_id,
                        "spell_caster": payload.player_index,
                    },
                }

        # Capture target monster info BEFORE spell effect (for logging)
        target_monster_info = None
        if ps.target_monster_instance_id:
            found = find_monster_by_instance_id(game_state, ps.target_monster_instance_id)
            if found:
                target_card = found.get("card")
                if target_card:
                    target_monster_info = {
                        "name": target_card.get("name", "Unknown"),
                        "atk": target_card.get("atk", 0),
                        "hp": target_card.get("hp", 0),
                        "max_hp": target_card.get("max_hp", 0),
                        "hp_before": target_card.get("hp", 0),
                    }

        # Build target context for resolver
        targets: Dict[str, Any] = {}
        if ps.target_player_index is not None:
            targets["player"] = ps.target_player_index
        
        if ps.target_monster_instance_id:
            found = find_monster_by_instance_id(game_state, ps.target_monster_instance_id)
            if found:
                targets["monster"] = {
                    "player_index": found["player_index"],
                    "zone_index": found["zone_index"],
                }

        # Create effect context and resolve
        ctx = EffectContext(
            game_state=game_state,
            source_player=payload.player_index,
            source_card=card,
            targets=targets,
        )

        effect_result = resolve_card_effects(ctx)

        # Handle destroyed monsters (move to graveyard)
        _handle_destroyed_monsters(game_state, effect_result.destroyed_monsters)

        # Ensure monster zones are updated after spell effects (buffs, etc.)
        # The resolver modifies cards directly, but we need to ensure the state is updated
        monster_zones = p_state.get("monster_zones") or []
        p_state["monster_zones"] = monster_zones
        players[pkey] = p_state
        game_state["players"] = players

        # Move spell to graveyard after resolution
        graveyard = p_state.get("graveyard") or []
        graveyard.append(card)
        p_state["graveyard"] = graveyard
        players[pkey] = p_state
        game_state["players"] = players

        # Build spell log entry with target info
        spell_log_entry: Dict[str, Any] = {
            "type": "PLAY_SPELL",
            "player": payload.player_index,
            "card_instance_id": ps.card_instance_id,
            "card_name": card.get("name"),
            "effects": effect_result.log_events,
        }
        
        # Add target monster info if available
        if target_monster_info:
            # Update hp_before from effect_result if available
            for eff in effect_result.log_events:
                if eff.get("type") == "EFFECT_DAMAGE_MONSTER" and eff.get("hp_before") is not None:
                    target_monster_info["hp_before"] = eff.get("hp_before")
                    break
            spell_log_entry["target_monster"] = target_monster_info

        log.append(spell_log_entry)

        # Increment spell/trap counter
        p_turn["spells_traps"] = 1
        turn_state[pkey] = p_turn

        # Check lethal from non-combat effects
        _check_lethal_after_noncombat(
            game_state=game_state,
            players=players,
            log=log,
            reason="spell_effects",
        )

    # ----------------------------------------------------------------
    # PLAY_TRAP (set a trap, no trigger logic yet)
    # ----------------------------------------------------------------
    elif payload.action == "PLAY_TRAP":
        if payload.play_trap is None:
            raise HTTPException(status_code=400, detail="Missing play_trap payload")

        # Rule 13: Check spell/trap play limit (1 per turn combined)
        turn_state = game_state.setdefault("turn_state", {})
        p_turn = turn_state.setdefault(pkey, {"summons": 0, "spells_traps": 0, "hero_ability": 0, "turn": game_state["turn"]})
        if p_turn["turn"] != game_state["turn"]:
            p_turn = {"summons": 0, "spells_traps": 0, "hero_ability": 0, "turn": game_state["turn"]}
        if p_turn["spells_traps"] >= 1:
            raise HTTPException(status_code=400, detail="Spell/Trap play limit reached")

        pt = payload.play_trap
        p_state = players[pkey]

        st_zones = p_state.get("spell_trap_zones") or []
        if pt.zone_index < 0 or pt.zone_index >= len(st_zones):
            raise HTTPException(status_code=400, detail="Invalid spell/trap zone index")

        if st_zones[pt.zone_index] is not None:
            raise HTTPException(status_code=400, detail="Spell/Trap zone is already occupied")

        hand = p_state.get("hand") or []
        # Filter out None or invalid entries that might not have instance_id
        hand = [c for c in hand if c is not None and isinstance(c, dict) and c.get("instance_id")]
        hand_idx = next(
            (i for i, c in enumerate(hand) if c.get("instance_id") == pt.card_instance_id),
            None,
        )
        if hand_idx is None:
            raise HTTPException(status_code=400, detail="Trap card not in hand")

        card = hand[hand_idx]
        card_type = card.get("card_type")
        if card_type not in ("trap", 3, "3"):
            raise HTTPException(status_code=400, detail="Selected card is not a trap")

        # Remove from hand, set face-down on board
        hand.pop(hand_idx)
        card["face_down"] = True
        # traps never attack
        card["can_attack"] = False

        st_zones[pt.zone_index] = card

        # Update hand in state after filtering and removal
        p_state["hand"] = hand
        p_state["spell_trap_zones"] = st_zones
        players[pkey] = p_state
        game_state["players"] = players

        # Increment spell/trap counter
        p_turn["spells_traps"] = 1
        turn_state[pkey] = p_turn

        log.append(
            {
                "type": "PLAY_TRAP",
                "player": payload.player_index,
                "card_instance_id": pt.card_instance_id,
                "card_name": card.get("name"),
                "zone": pt.zone_index,
            }
        )

    # ----------------------------------------------------------------
    # ACTIVATE_TRAP (manual activation for testing)
    # ----------------------------------------------------------------
    elif payload.action == "ACTIVATE_TRAP":
        if payload.activate_trap is None:
            raise HTTPException(status_code=400, detail="Missing activate_trap payload")

        atp = payload.activate_trap
        p_state = players[pkey]

        st_zones = p_state.get("spell_trap_zones") or []
        trap_card = None
        trap_zone_index = None
        for idx, slot in enumerate(st_zones):
            if slot is not None and slot.get("instance_id") == atp.trap_instance_id:
                trap_card = slot
                trap_zone_index = idx
                break

        if trap_card is None or trap_zone_index is None:
            raise HTTPException(status_code=400, detail="Trap card not found on battlefield")

        card_type = trap_card.get("card_type")
        if card_type not in ("trap", 3, "3"):
            raise HTTPException(status_code=400, detail="Selected card is not a trap")

        # Build target context for resolver
        targets: Dict[str, Any] = {}
        if atp.target_player_index is not None:
            targets["player"] = atp.target_player_index
        
        if atp.target_monster_instance_id:
            found = find_monster_by_instance_id(game_state, atp.target_monster_instance_id)
            if found:
                targets["monster"] = {
                    "player_index": found["player_index"],
                    "zone_index": found["zone_index"],
                }

        # Create effect context and resolve
        ctx = EffectContext(
            game_state=game_state,
            source_player=payload.player_index,
            source_card=trap_card,
            targets=targets,
        )

        effect_result = resolve_card_effects(ctx)

        # Handle destroyed monsters (move to graveyard)
        _handle_destroyed_monsters(game_state, effect_result.destroyed_monsters)

        # Remove trap from zone and put into graveyard
        st_zones[trap_zone_index] = None
        p_state["spell_trap_zones"] = st_zones

        graveyard = p_state.get("graveyard") or []
        graveyard.append(trap_card)
        p_state["graveyard"] = graveyard

        players[pkey] = p_state
        game_state["players"] = players

        # Build trap log entry
        trap_log_entry: Dict[str, Any] = {
            "type": "ACTIVATE_TRAP",
            "player": payload.player_index,
            "trap_instance_id": atp.trap_instance_id,
            "card_name": trap_card.get("name"),
            "effects": effect_result.log_events,
        }
        log.append(trap_log_entry)

        _check_lethal_after_noncombat(
            game_state=game_state,
            players=players,
            log=log,
            reason="trap_effects",
        )

    # ----------------------------------------------------------------
    # ACTIVATE_HERO_ABILITY
    # ----------------------------------------------------------------
    elif payload.action == "ACTIVATE_HERO_ABILITY":
        turn_state = game_state.setdefault("turn_state", {})
        p_turn = turn_state.setdefault(pkey, {"summons": 0, "spells_traps": 0, "hero_ability": 0, "turn": game_state["turn"]})
        if p_turn["turn"] != game_state["turn"]:
            p_turn = {"summons": 0, "spells_traps": 0, "hero_ability": 0, "turn": game_state["turn"]}
        if p_turn["hero_ability"] >= 1:
            raise HTTPException(status_code=400, detail="Hero ability already used this turn")

        if payload.activate_hero_ability is None:
            raise HTTPException(status_code=400, detail="Missing activate_hero_ability payload")

        p_state = players[pkey]
        hero = p_state.get("hero")
        if not hero:
            raise HTTPException(status_code=400, detail="No hero on field")

        aha = payload.activate_hero_ability

        # Build targets for hero ability
        targets: Dict[str, Any] = {}
        # Auto-targeting: if no target provided, try to select one.
        target_monster_id = aha.target_monster_instance_id
        target_player_idx = aha.target_player_index
        opponent_idx = 2 if payload.player_index == 1 else 1

        if target_monster_id:
            found = find_monster_by_instance_id(game_state, target_monster_id)
            if not found:
                raise HTTPException(status_code=400, detail="Target monster not found")
            targets["monster"] = {
                "player_index": found["player_index"],
                "zone_index": found["zone_index"],
            }
        else:
            # No target provided: auto-pick enemy monster if exactly one; if none, target enemy player.
            opp_state = players.get(str(opponent_idx)) or {}
            opp_mz = opp_state.get("monster_zones") or []
            alive = [
                (idx, m) for idx, m in enumerate(opp_mz)
                if m is not None and m.get("hp", 0) > 0
            ]
            if len(alive) == 1:
                idx, _ = alive[0]
                targets["monster"] = {"player_index": opponent_idx, "zone_index": idx}
            elif len(alive) == 0:
                # No monsters: allow targeting opposing player
                targets["player"] = opponent_idx
            else:
                raise HTTPException(status_code=400, detail="Hero ability requires selecting a target monster")

        if target_player_idx is not None:
            targets["player"] = target_player_idx
        
        # Get effect_params
        effect_params = hero.get("effect_params") or {}
        if isinstance(effect_params, str):
            try:
                import json
                effect_params = json.loads(effect_params)
            except:
                effect_params = {}
        
        # Check for active_ability in effect_params, or use existing effects array
        active_ability = effect_params.get("active_ability")
        if active_ability:
            # New structure: active_ability object
            ability_keyword = active_ability.get("keyword")
            if not ability_keyword:
                # Fallback: check effect_tags
                effect_tags = hero.get("effect_tags") or []
                for tag in effect_tags:
                    if tag.startswith("HERO_ACTIVE_"):
                        ability_keyword = tag
                        break
            
            if not ability_keyword:
                raise HTTPException(status_code=400, detail="Hero active ability keyword not found")
            
            # Create a temporary card dict with the active ability for the resolver
            hero_ability_card = hero.copy()
            hero_ability_card["effect_params"] = {
                "effects": [{
                    "keyword": ability_keyword,
                    **{k: v for k, v in active_ability.items() if k != "keyword"}  # Merge params except keyword
                }]
            }
        else:
            # Fallback: use existing effects array (for backwards compatibility)
            hero_ability_card = hero
        
        # Create effect context and resolve using the existing resolver
        ctx = EffectContext(
            game_state=game_state,
            source_player=payload.player_index,
            source_card=hero_ability_card,
            targets=targets,
            trigger="HERO_ACTIVE",
            trigger_event={"type": "HERO_ACTIVE"},
        )
        
        effect_result = resolve_card_effects(ctx)
        _handle_destroyed_monsters(game_state, effect_result.destroyed_monsters)
        
        # Ensure monster zones are updated after ability effects
        monster_zones = p_state.get("monster_zones") or []
        p_state["monster_zones"] = monster_zones
        players[pkey] = p_state
        game_state["players"] = players

        log.append(
            {
                "type": "ACTIVATE_HERO_ABILITY",
                "player": payload.player_index,
                "hero_instance_id": hero.get("instance_id"),
                "card_name": hero.get("name"),
                "effects": effect_result.log_events,
            }
        )

        p_turn["hero_ability"] = 1
        turn_state[pkey] = p_turn

    # ----------------------------------------------------------------
    # ATTACK_MONSTER (symmetric spillover combat)
    # ----------------------------------------------------------------
    elif payload.action == "ATTACK_MONSTER":
        if payload.attack_monster is None:
            raise HTTPException(status_code=400, detail="Missing attack_monster payload")

        am = payload.attack_monster

        atk_player_idx = payload.player_index
        def_player_idx = 2 if atk_player_idx == 1 else 1

        atk_pkey = str(atk_player_idx)
        def_pkey = str(def_player_idx)

        atk_state = players.get(atk_pkey)
        def_state = players.get(def_pkey)
        if atk_state is None or def_state is None:
            raise HTTPException(status_code=500, detail="Player state missing")

        # Locate attacker on field
        atk_mz = atk_state.get("monster_zones") or []
        attacker = None
        attacker_zone_index = None
        for idx, slot in enumerate(atk_mz):
            if slot is not None and slot.get("instance_id") == am.attacker_instance_id:
                attacker = slot
                attacker_zone_index = idx
                break

        if attacker is None:
            raise HTTPException(status_code=400, detail="Attacker not found on battlefield")

        if not attacker.get("can_attack", False):
            raise HTTPException(status_code=400, detail="This monster cannot attack right now")

        if attacker.get("hp", 0) <= 0:
            raise HTTPException(status_code=400, detail="This monster has been destroyed")

        # Locate defender on field
        def_mz = def_state.get("monster_zones") or []
        defender = None
        defender_zone_index = None
        for idx, slot in enumerate(def_mz):
            if slot is not None and slot.get("instance_id") == am.defender_instance_id:
                defender = slot
                defender_zone_index = idx
                break

        if defender is None:
            raise HTTPException(status_code=400, detail="Defender not found on battlefield")

        # Trap trigger check before resolving combat
        available_traps = _get_available_trap_triggers(
            game_state=game_state,
            defending_player_index=def_player_idx,
            trigger_type="ON_ATTACK_DECLARED",
            trigger_event={
                "type": "ATTACK_MONSTER",
                "attacker_instance_id": am.attacker_instance_id,
                "defender_instance_id": am.defender_instance_id,
                "attacking_player": atk_player_idx,
                "defending_player": def_player_idx,
            },
        )
        if available_traps:
            # Check if this is PVE and the trap belongs to AI - auto-trigger it
            match_mode = match_row.get("mode", "PVE")
            ai_player_index = 2  # NPC is always player 2 in PVE
            if match_mode == "PVE" and def_player_idx == ai_player_index:
                # Auto-trigger AI trap (always say yes)
                trap_to_trigger = available_traps[0]  # Trigger first available trap
                print(f"AI auto-triggering trap: {trap_to_trigger.get('card_name')}")
                
                # Activate the trap directly
                from app.engine.action_handlers import handle_activate_trap
                trap_effect_result = handle_activate_trap(
                    game_state=game_state,
                    player_index=def_player_idx,
                    trap_instance_id=trap_to_trigger["trap_instance_id"],
                    target_player_index=atk_player_idx,
                    target_monster_instance_id=am.attacker_instance_id,
                    trigger_event={
                        "type": "ATTACK_MONSTER",
                        "attacker_instance_id": am.attacker_instance_id,
                        "attacker_atk": attacker.get("atk", 0),
                        "attacking_player": atk_player_idx,
                        "defending_player": def_player_idx,
                    },
                )
                
                # Handle destroyed by trap
                _handle_destroyed_monsters(game_state, trap_effect_result.destroyed_monsters)

                # Add trap trigger log
                log.append({
                    "type": "TRAP_TRIGGERED",
                    "player": def_player_idx,
                    "trap_instance_id": trap_to_trigger["trap_instance_id"],
                    "card_name": trap_to_trigger.get("card_name"),
                    "trigger_type": "ON_ATTACK_DECLARED",
                    "effects": trap_effect_result.log_events,
                    "cancelled_action": trap_effect_result.cancelled,
                })
                
                # Check lethal after trap effects
                _check_lethal_after_noncombat(
                    game_state=game_state,
                    players=players,
                    log=log,
                    reason="trap_effects",
                )
                
                # If trap cancelled the attack, don't proceed
                if trap_effect_result.cancelled:
                    log.append({
                        "type": "ACTION_CANCELLED",
                        "reason": "trap_negate_attack",
                        "original_action": "ATTACK_MONSTER",
                    })
                    # Mark attacker as having used its attack (even though it was negated)
                    attacker["can_attack"] = False
                    atk_mz[attacker_zone_index] = attacker
                    atk_state["monster_zones"] = atk_mz
                    players[atk_pkey] = atk_state
                    game_state["players"] = players
                    supabase.table("matches").update({
                        "serialized_game_state": game_state,
                    }).eq("id", payload.match_id).execute()
                    return {
                        "match_id": payload.match_id,
                        "game_state": game_state,
                    }
                
                # Continue with attack after trap resolves
                # (trap may have destroyed the attacker, so check again)
                # Re-fetch both attacker and defender to get updated HP values
                attacker_found = find_monster_by_instance_id(game_state, am.attacker_instance_id)
                if not attacker_found:
                    # Attacker was destroyed by trap
                    return {
                        "match_id": payload.match_id,
                        "game_state": game_state,
                    }
                # Update attacker reference to use the updated card from game state
                attacker = attacker_found["card"]
                attacker_zone_index = attacker_found["zone_index"]
                # Also re-fetch defender in case trap affected it
                defender_found = find_monster_by_instance_id(game_state, am.defender_instance_id)
                if defender_found:
                    defender = defender_found["card"]
                    defender_zone_index = defender_found["zone_index"]
                else:
                    # Defender was destroyed by trap - attack cannot proceed
                    return {
                        "match_id": payload.match_id,
                        "game_state": game_state,
                    }
            else:
                # Player trap - return for player decision
                return {
                    "match_id": payload.match_id,
                    "game_state": game_state,
                    "trap_triggers_available": available_traps,
                    "trigger_player_index": def_player_idx,  # Player whose trap is triggering
                    "pending_action": {
                        "action": "ATTACK_MONSTER",
                        "attack_monster": am.model_dump() if hasattr(am, "model_dump") else am.dict(),
                        "player_index": payload.player_index,  # AI's player index
                    },
                    "trigger_type": "ON_ATTACK_DECLARED",
                    "trigger_event": {
                        "type": "ATTACK_MONSTER",
                        "attacker_instance_id": am.attacker_instance_id,
                        "defender_instance_id": am.defender_instance_id,
                        "attacking_player": atk_player_idx,
                        "defending_player": def_player_idx,
                    },
                }

        # Flip defender face-up if needed
        defender["face_down"] = False

        # Snapshot monster HP before combat (use current HP after any trap effects)
        attacker_hp_before = attacker.get("hp", 0)
        defender_hp_before = defender.get("hp", 0)
        atk_value = max(attacker.get("atk", 0), 0)
        def_value = max(defender.get("atk", 0), 0)

        # Simultaneous damage to monsters
        defender_hp_after = max(0, defender_hp_before - atk_value)
        attacker_hp_after = max(0, attacker_hp_before - def_value)
        defender["hp"] = defender_hp_after
        attacker["hp"] = attacker_hp_after

        # Spillover damage to players
        # Rule 6: Overflow damage - only if effect grants it
        # For now, we'll keep overflow as a core mechanic (per user clarification)
        # But we can add a flag later if needed: attacker.get("overflow_enabled", True)
        overflow_to_defender_player = max(0, atk_value - defender_hp_before)
        overflow_to_attacker_player = max(0, def_value - attacker_hp_before)

        atk_player_hp_before = atk_state.get("hp", 0)
        def_player_hp_before = def_state.get("hp", 0)

        atk_player_hp_after = max(0, atk_player_hp_before - overflow_to_attacker_player)
        def_player_hp_after = max(0, def_player_hp_before - overflow_to_defender_player)

        atk_state["hp"] = atk_player_hp_after
        def_state["hp"] = def_player_hp_after

        atk_graveyard = atk_state.get("graveyard") or []
        def_graveyard = def_state.get("graveyard") or []

        defender_died = defender_hp_after <= 0
        attacker_died = attacker_hp_after <= 0

        # Check for traps that trigger when monsters would be destroyed (e.g., Last Stand Ward)
        # Check defender's traps first
        if defender_died:
            available_traps = _get_available_trap_triggers(
                game_state=game_state,
                defending_player_index=def_player_idx,
                trigger_type="ON_ALLY_MONSTER_WOULD_BE_DESTROYED",
                trigger_event={
                    "type": "MONSTER_WOULD_BE_DESTROYED",
                    "monster_instance_id": am.defender_instance_id,
                    "player_index": def_player_idx,
                    "zone_index": defender_zone_index,
                },
            )
            if available_traps:
                # Check if this is PVE and the trap belongs to AI - auto-trigger it
                match_mode = match_row.get("mode", "PVE")
                ai_player_index = 2  # NPC is always player 2 in PVE
                if match_mode == "PVE" and def_player_idx == ai_player_index:
                    # Auto-trigger AI trap (always say yes)
                    trap_to_trigger = available_traps[0]
                    print(f"AI auto-triggering trap: {trap_to_trigger.get('card_name')} preventing destruction")
                    
                    from app.engine.action_handlers import handle_activate_trap
                    # For prevent destruction traps, we need to pass the trigger_event with monster info
                    # The trap handler will use this to find the target monster
                    trigger_event_for_trap = {
                        "type": "MONSTER_WOULD_BE_DESTROYED",
                        "monster_instance_id": am.defender_instance_id,
                        "player_index": def_player_idx,
                        "zone_index": defender_zone_index,
                    }
                    handle_activate_trap(
                        game_state=game_state,
                        player_index=def_player_idx,
                        trap_instance_id=trap_to_trigger["trap_instance_id"],
                        target_player_index=def_player_idx,
                        target_monster_instance_id=am.defender_instance_id,
                        trigger_event=trigger_event_for_trap,
                    )
                    
                    log.append({
                        "type": "TRAP_TRIGGERED",
                        "player": def_player_idx,
                        "trap_instance_id": trap_to_trigger["trap_instance_id"],
                        "card_name": trap_to_trigger.get("card_name"),
                        "trigger_type": "ON_ALLY_MONSTER_WOULD_BE_DESTROYED",
                    })
                    
                    # Re-check HP after trap (trap may have set HP to 1)
                    defender_found = find_monster_by_instance_id(game_state, am.defender_instance_id)
                    if defender_found and defender_found["card"].get("hp", 0) > 0:
                        defender_died = False
                        defender_hp_after = defender_found["card"].get("hp", 0)
                else:
                    # Player trap - return for player decision
                    # After trap resolves, attack will continue normally
                    return {
                        "match_id": payload.match_id,
                        "game_state": game_state,
                        "trap_triggers_available": available_traps,
                        "trigger_player_index": def_player_idx,
                        "pending_action": {
                            "action": "ATTACK_MONSTER",
                            "attack_monster": {
                                "attacker_instance_id": am.attacker_instance_id,
                                "defender_instance_id": am.defender_instance_id,
                            },
                            "player_index": payload.player_index,
                        },
                        "trigger_type": "ON_ALLY_MONSTER_WOULD_BE_DESTROYED",
                        "trigger_event": {
                            "type": "MONSTER_WOULD_BE_DESTROYED",
                            "monster_instance_id": am.defender_instance_id,
                            "player_index": def_player_idx,
                            "zone_index": defender_zone_index,
                            "attacker_instance_id": am.attacker_instance_id,
                            "attacker_atk": atk_value,
                            "defender_atk": def_value,
                            "attacker_hp_before": attacker_hp_before,
                            "defender_hp_before": defender_hp_before,
                            "attacker_hp_after": attacker_hp_after,
                            "defender_hp_after": defender_hp_after,
                            "attacking_player": atk_player_idx,
                            "defending_player": def_player_idx,
                        },
                    }
        
        # Check attacker's traps
        if attacker_died:
            available_traps = _get_available_trap_triggers(
                game_state=game_state,
                defending_player_index=atk_player_idx,
                trigger_type="ON_ALLY_MONSTER_WOULD_BE_DESTROYED",
                trigger_event={
                    "type": "MONSTER_WOULD_BE_DESTROYED",
                    "monster_instance_id": am.attacker_instance_id,
                    "player_index": atk_player_idx,
                    "zone_index": attacker_zone_index,
                },
            )
            if available_traps:
                # Check if this is PVE and the trap belongs to AI - auto-trigger it
                match_mode = match_row.get("mode", "PVE")
                ai_player_index = 2  # NPC is always player 2 in PVE
                if match_mode == "PVE" and atk_player_idx == ai_player_index:
                    # Auto-trigger AI trap (always say yes)
                    trap_to_trigger = available_traps[0]
                    print(f"AI auto-triggering trap: {trap_to_trigger.get('card_name')} preventing destruction")
                    
                    from app.engine.action_handlers import handle_activate_trap
                    # For prevent destruction traps, we need to pass the trigger_event with monster info
                    trigger_event_for_trap = {
                        "type": "MONSTER_WOULD_BE_DESTROYED",
                        "monster_instance_id": am.attacker_instance_id,
                        "player_index": atk_player_idx,
                        "zone_index": attacker_zone_index,
                    }
                    handle_activate_trap(
                        game_state=game_state,
                        player_index=atk_player_idx,
                        trap_instance_id=trap_to_trigger["trap_instance_id"],
                        target_player_index=atk_player_idx,
                        target_monster_instance_id=am.attacker_instance_id,
                        trigger_event=trigger_event_for_trap,
                    )
                    
                    log.append({
                        "type": "TRAP_TRIGGERED",
                        "player": atk_player_idx,
                        "trap_instance_id": trap_to_trigger["trap_instance_id"],
                        "card_name": trap_to_trigger.get("card_name"),
                        "trigger_type": "ON_ALLY_MONSTER_WOULD_BE_DESTROYED",
                    })
                    
                    # Re-check HP after trap (trap may have set HP to 1)
                    attacker_found = find_monster_by_instance_id(game_state, am.attacker_instance_id)
                    if attacker_found and attacker_found["card"].get("hp", 0) > 0:
                        attacker_died = False
                        attacker_hp_after = attacker_found["card"].get("hp", 0)
                else:
                    # Player trap - return for player decision
                    return {
                        "match_id": payload.match_id,
                        "game_state": game_state,
                        "trap_triggers_available": available_traps,
                        "trigger_player_index": atk_player_idx,
                        "pending_action": {
                            "action": "ATTACK_MONSTER",
                            "attack_monster": {
                                "attacker_instance_id": am.attacker_instance_id,
                                "defender_instance_id": am.defender_instance_id,
                            },
                            "player_index": payload.player_index,
                        },
                        "trigger_type": "ON_ALLY_MONSTER_WOULD_BE_DESTROYED",
                        "trigger_event": {
                            "type": "MONSTER_WOULD_BE_DESTROYED",
                            "monster_instance_id": am.attacker_instance_id,
                            "player_index": atk_player_idx,
                            "zone_index": attacker_zone_index,
                        },
                    }

        # Move dead defender to graveyard (only if still dead after trap)
        if defender_died:
            # Re-check HP in case trap prevented destruction
            defender_found = find_monster_by_instance_id(game_state, am.defender_instance_id)
            if defender_found and defender_found["card"].get("hp", 0) > 0:
                # Trap saved it - don't move to graveyard
                defender_died = False
                def_mz[defender_zone_index] = defender_found["card"]
            else:
                # Still dead - move to graveyard
                def_graveyard.append(defender)
                def_mz[defender_zone_index] = None

        # Move dead attacker to graveyard or mark that it used its attack
        if attacker_died:
            # Re-check HP in case trap prevented destruction
            attacker_found = find_monster_by_instance_id(game_state, am.attacker_instance_id)
            if attacker_found and attacker_found["card"].get("hp", 0) > 0:
                # Trap saved it - don't move to graveyard
                attacker_died = False
                attacker = attacker_found["card"]
                attacker["can_attack"] = False
                atk_mz[attacker_zone_index] = attacker
            else:
                # Still dead - move to graveyard
                atk_graveyard.append(attacker)
                atk_mz[attacker_zone_index] = None
        else:
            attacker["can_attack"] = False
            atk_mz[attacker_zone_index] = attacker

        atk_state["monster_zones"] = atk_mz
        atk_state["graveyard"] = atk_graveyard
        def_state["monster_zones"] = def_mz
        def_state["graveyard"] = def_graveyard

        players[atk_pkey] = atk_state
        players[def_pkey] = def_state
        game_state["players"] = players

        log.append(
            {
                "type": "ATTACK_MONSTER",
                "attacking_player": atk_player_idx,
                "defending_player": def_player_idx,
                "attacker_instance_id": am.attacker_instance_id,
                "defender_instance_id": am.defender_instance_id,
                "attacker_atk": atk_value,
                "defender_atk": def_value,
                "attacker_hp_before": attacker_hp_before,
                "defender_hp_before": defender_hp_before,
                "attacker_hp_after": attacker_hp_after,
                "defender_hp_after": defender_hp_after,
                "overflow_to_attacker_player": overflow_to_attacker_player,
                "overflow_to_defender_player": overflow_to_defender_player,
                "attacker_player_hp_before": atk_player_hp_before,
                "attacker_player_hp_after": atk_player_hp_after,
                "defender_player_hp_before": def_player_hp_before,
                "defender_player_hp_after": def_player_hp_after,
            }
        )

        # Lethal check after combat + spillover
        winner: Optional[int] = None
        atk_dead = atk_player_hp_after <= 0
        def_dead = def_player_hp_after <= 0

        if atk_dead and def_dead:
            # Draw
            game_state["status"] = "completed"
            game_state["winner"] = None
            log.append(
                {
                    "type": "MATCH_END",
                    "winner": None,
                    "reason": "double_lethal",
                    "player1_hp": players["1"]["hp"],
                    "player2_hp": players["2"]["hp"],
                }
            )
        elif def_dead:
            winner = atk_player_idx
        elif atk_dead:
            winner = def_player_idx

        if winner is not None:
            game_state["status"] = "completed"
            game_state["winner"] = winner
            log.append(
                {
                    "type": "MATCH_END",
                    "winner": winner,
                    "reason": "combat_lethal",
                    "player1_hp": players["1"]["hp"],
                    "player2_hp": players["2"]["hp"],
                }
            )

    # ----------------------------------------------------------------
    # ATTACK_PLAYER (direct attack when opponent has no monsters)
    # ----------------------------------------------------------------
    elif payload.action == "ATTACK_PLAYER":
        if payload.attack_player is None:
            raise HTTPException(status_code=400, detail="Missing attack_player payload")

        ap = payload.attack_player

        atk_player_idx = payload.player_index
        def_player_idx = 2 if atk_player_idx == 1 else 1

        atk_pkey = str(atk_player_idx)
        def_pkey = str(def_player_idx)

        atk_state = players.get(atk_pkey)
        def_state = players.get(def_pkey)
        if atk_state is None or def_state is None:
            raise HTTPException(status_code=500, detail="Player state missing")

        # Opponent must have NO monsters on the field for direct attack
        def_mz = def_state.get("monster_zones") or []
        if any(slot is not None for slot in def_mz):
            raise HTTPException(
                status_code=400,
                detail="Opponent controls monsters; you must attack their monsters first",
            )

        # Locate attacker on field
        atk_mz = atk_state.get("monster_zones") or []
        attacker = None
        attacker_zone_index = None
        for idx, slot in enumerate(atk_mz):
            if slot is not None and slot.get("instance_id") == ap.attacker_instance_id:
                attacker = slot
                attacker_zone_index = idx
                break

        if attacker is None:
            raise HTTPException(status_code=400, detail="Attacker not found on battlefield")

        if not attacker.get("can_attack", False):
            raise HTTPException(status_code=400, detail="This monster cannot attack right now")

        if attacker.get("hp", 0) <= 0:
            raise HTTPException(status_code=400, detail="This monster has been destroyed")

        # Trap trigger check for direct attack
        available_traps = _get_available_trap_triggers(
            game_state=game_state,
            defending_player_index=def_player_idx,
            trigger_type="ON_ATTACK_DECLARED",
            trigger_event={
                "type": "ATTACK_PLAYER",
                "attacker_instance_id": ap.attacker_instance_id,
                "attacker_atk": attacker.get("atk", 0),
                "attacking_player": atk_player_idx,
                "defending_player": def_player_idx,
            },
        )
        if available_traps:
            # Check if this is PVE and the trap belongs to AI - auto-trigger it
            match_mode = match_row.get("mode", "PVE")
            ai_player_index = 2  # NPC is always player 2 in PVE
            if match_mode == "PVE" and def_player_idx == ai_player_index:
                # Auto-trigger AI trap (always say yes)
                trap_to_trigger = available_traps[0]  # Trigger first available trap
                print(f"AI auto-triggering trap: {trap_to_trigger.get('card_name')}")
                
                # Activate the trap directly
                from app.engine.action_handlers import handle_activate_trap
                handle_activate_trap(
                    game_state=game_state,
                    player_index=def_player_idx,
                    trap_instance_id=trap_to_trigger["trap_instance_id"],
                    target_player_index=atk_player_idx,
                    target_monster_instance_id=ap.attacker_instance_id,
                )
                
                # Add trap trigger log
                log.append({
                    "type": "TRAP_TRIGGERED",
                    "player": def_player_idx,
                    "trap_instance_id": trap_to_trigger["trap_instance_id"],
                    "card_name": trap_to_trigger.get("card_name"),
                    "trigger_type": "ON_ATTACK_DECLARED",
                })
                
                # Check lethal after trap effects
                _check_lethal_after_noncombat(
                    game_state=game_state,
                    players=players,
                    log=log,
                    reason="trap_effects",
                )
                
                # Check if trap cancelled the attack
                # (trap may have destroyed the attacker or negated the attack)
                attacker_found = find_monster_by_instance_id(game_state, ap.attacker_instance_id)
                if not attacker_found:
                    # Attacker was destroyed by trap
                    return {
                        "match_id": payload.match_id,
                        "game_state": game_state,
                    }
                # Update attacker reference
                attacker = attacker_found["card"]
                attacker_zone_index = attacker_found["zone_index"]
            else:
                # Player trap - return for player decision
                return {
                    "match_id": payload.match_id,
                    "game_state": game_state,
                    "trap_triggers_available": available_traps,
                    "trigger_player_index": def_player_idx,  # Player whose trap is triggering
                    "pending_action": {
                        "action": "ATTACK_PLAYER",
                        "attack_player": ap.model_dump() if hasattr(ap, "model_dump") else ap.dict(),
                        "player_index": payload.player_index,
                    },
                    "trigger_type": "ON_ATTACK_DECLARED",
                    "trigger_event": {
                        "type": "ATTACK_PLAYER",
                        "attacker_instance_id": ap.attacker_instance_id,
                        "attacker_atk": attacker.get("atk", 0),
                        "attacking_player": atk_player_idx,
                        "defending_player": def_player_idx,
                    },
                }

        atk_value = max(attacker.get("atk", 0), 0)

        before_hp = def_state.get("hp", 0)
        after_hp = max(before_hp - atk_value, 0)
        def_state["hp"] = after_hp

        # Attacker has used its attack this turn
        attacker["can_attack"] = False
        atk_mz[attacker_zone_index] = attacker

        atk_state["monster_zones"] = atk_mz
        players[atk_pkey] = atk_state
        players[def_pkey] = def_state
        game_state["players"] = players

        log.append(
            {
                "type": "ATTACK_PLAYER",
                "attacking_player": atk_player_idx,
                "defending_player": def_player_idx,
                "attacker_instance_id": ap.attacker_instance_id,
                "attacker_atk": atk_value,
                "damage_to_player": atk_value,
                "defender_hp_before": before_hp,
                "defender_hp_after": after_hp,
            }
        )

        # Check lethal
        if after_hp <= 0:
            game_state["status"] = "completed"
            game_state["winner"] = atk_player_idx
            log.append(
                {
                    "type": "MATCH_END",
                    "winner": atk_player_idx,
                    "loser": def_player_idx,
                    "reason": "direct_attack",
                }
            )

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {payload.action}")

    # 4) Persist updated state back into Supabase
    supabase.table("matches").update(
        {
            "serialized_game_state": game_state,
            "status": game_state.get("status", match_row.get("status")),
        }
    ).eq("id", payload.match_id).execute()

    # 5) Return updated state
    return {
        "match_id": payload.match_id,
        "game_state": game_state,
    }


def _draw_with_reshuffle(p_state: Dict[str, Any], amount: int) -> None:
    """
    Draw cards with automatic deck reshuffle from graveyard.
    Rule 11: When deck is empty, shuffle graveyard into deck.
    """
    deck = p_state.get("deck") or []
    graveyard = p_state.get("graveyard") or []
    hand = p_state.get("hand") or []
    active_element = p_state.get("active_element")
    
    for _ in range(amount):
        if not deck:
            if graveyard:
                # Reshuffle graveyard into deck
                random.shuffle(graveyard)
                deck = graveyard
                graveyard = []
            else:
                # Both empty - cannot draw
                break
        
        drawn = deck.pop(0)
        drawn = _apply_element_variant_preserve_runtime(drawn, active_element)
        hand.append(drawn)
    
    p_state["deck"] = deck
    p_state["graveyard"] = graveyard
    p_state["hand"] = hand


def _tick_statuses_on_board(p_state: Dict[str, Any]) -> None:
    """
    Rule 3: Resolve duration-based statuses at start of turn.
    Decrements FIXED_TURNS durations by 1, removes expired ones.
    """
    for card in (p_state.get("monster_zones") or []):
        if card is None:
            continue
        
        statuses = card.get("statuses") or []
        new_statuses = []
        
        for s in statuses:
            # Support both old format (string) and new format (dict)
            if isinstance(s, str):
                # Convert old format to new format
                new_statuses.append({"code": s, "duration_type": "PERMANENT"})
                continue
            
            # New format: dict with duration_type
            dtype = s.get("duration_type", "PERMANENT")
            
            if dtype == "FIXED_TURNS":
                val = s.get("duration_value")
                if val is not None and val > 0:
                    # Decrement by 1
                    new_s = s.copy()
                    new_s["duration_value"] = val - 1
                    if new_s["duration_value"] > 0:
                        new_statuses.append(new_s)
                    else:
                        # Duration reached 0 - status expires
                        # Check if there's an on_expire effect (e.g., FROZEN -> STATUS_IMMUNE)
                        on_expire = s.get("on_expire")
                        if on_expire:
                            # Apply the on_expire status
                            new_statuses.append({
                                "code": on_expire,
                                "duration_type": "FIXED_TURNS",
                                "duration_value": 2,  # 1 round = 2 turns
                            })
                    # If duration reaches 0 and no on_expire, status expires (don't add it)
            else:
                # PERMANENT or other - keep as-is
                new_statuses.append(s)
        
        card["statuses"] = new_statuses
        
        # Apply status effects (e.g., FROZEN prevents attack)
        if any(s.get("code") == "FROZEN" for s in new_statuses):
            card["can_attack"] = False
    
    # Also tick hero statuses if hero exists
    hero = p_state.get("hero")
    if hero:
        statuses = hero.get("statuses") or []
        new_statuses = []
        for s in statuses:
            if isinstance(s, str):
                new_statuses.append({"code": s, "duration_type": "PERMANENT"})
                continue
            dtype = s.get("duration_type", "PERMANENT")
            if dtype == "FIXED_TURNS":
                val = s.get("duration_value")
                if val is not None and val > 0:
                    new_s = s.copy()
                    new_s["duration_value"] = val - 1
                    if new_s["duration_value"] > 0:
                        new_statuses.append(new_s)
            else:
                new_statuses.append(s)
        hero["statuses"] = new_statuses


def _get_available_trap_triggers(
    game_state: Dict[str, Any],
    defending_player_index: int,
    trigger_type: str,
    trigger_event: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Check for traps that can be triggered by an event.
    
    Returns list of traps that match the trigger condition.
    Each trap dict includes: trap_instance_id, card_name, zone_index
    """
    players = game_state.get("players", {})
    def_pkey = str(defending_player_index)
    def_state = players.get(def_pkey)
    if not def_state:
        return []
    
    spell_trap_zones = def_state.get("spell_trap_zones") or []
    available = []
    
    for idx, trap_slot in enumerate(spell_trap_zones):
        if trap_slot is None or not trap_slot.get("face_down", True):
            continue
        
        # Check if trap has matching trigger keywords
        effect_params = trap_slot.get("effect_params") or {}
        if isinstance(effect_params, str):
            try:
                import json
                effect_params = json.loads(effect_params)
            except:
                effect_params = {}
        
        # Get effect_tags from card (data-driven triggers)
        effect_tags = trap_slot.get("effect_tags") or []
        
        # Get top-level trigger from effect_params
        top_level_trigger = effect_params.get("trigger", "")
        
        effects = effect_params.get("effects") or []
        for eff in effects:
            keyword = eff.get("keyword", "")
            trigger_condition = eff.get("trigger") or eff.get("trigger_condition", "")
            
            # Collect all possible trigger identifiers
            all_triggers = [top_level_trigger] + effect_tags + [keyword, trigger_condition]
            all_triggers = [t for t in all_triggers if t]  # Filter out None/empty strings
            
            matches = False
            
            if trigger_type == "ON_SPELL_CAST":
                spell_trigger_patterns = [
                    "ON_SPELL_CAST", "ON_CAST_SPELL", "ON_ENEMY_SPELL", 
                    "ON_OPPONENT_SPELL", "TRAP_ON_SPELL", "TRAP_TRIGGER_ON_OPPONENT_SPELL",
                    "TRAP_CANCEL_SPELL", "SPELL_COUNTER_SPELL", "TRAP_COUNTER_SPELL"
                ]
                if any(t in spell_trigger_patterns for t in all_triggers):
                    matches = True
            
            elif trigger_type == "ON_ATTACK_DECLARED":
                attack_trigger_patterns = [
                    "ON_ATTACK", "ON_ATTACK_DECLARED", "ON_ATTACK_MONSTER", "ON_ATTACK_PLAYER",
                    "ON_ENEMY_ATTACK", "ON_MONSTER_ATTACK", "ON_DIRECT_ATTACK",
                    "ON_YOUR_MONSTER_ATTACKED", "ON_MONSTER_ATTACKS", "TRAP_ON_ATTACK",
                    "TRAP_ON_ATTACK_MONSTER", "TRAP_ON_ATTACK_PLAYER", "TRAP_TRIGGER_ON_ATTACK",
                    "TRAP_DAMAGE_ON_ATTACK", "TRAP_NEGATE_ATTACK", "TRAP_REFLECT_DAMAGE"
                ]
                if any(t in attack_trigger_patterns for t in all_triggers):
                    matches = True
            
            elif trigger_type == "ON_ALLY_MONSTER_WOULD_BE_DESTROYED":
                destruction_trigger_patterns = [
                    "ON_ALLY_MONSTER_WOULD_BE_DESTROYED", "ON_MONSTER_WOULD_BE_DESTROYED",
                    "ON_DESTRUCTION", "PREVENT_DESTRUCTION", "TRAP_PREVENT_DESTRUCTION",
                    "ON_ALLY_MONSTER_WOULD_BE_DESTROYED_BY_DAMAGE"
                ]
                if any(t in destruction_trigger_patterns for t in all_triggers):
                    matches = True
            
            if matches:
                available.append({
                    "trap_instance_id": trap_slot.get("instance_id"),
                    "card_name": trap_slot.get("name"),
                    "zone_index": idx,
                    "trigger_keyword": keyword,
                    "description": trap_slot.get("description"),
                    "rules_text": trap_slot.get("rules_text"),
                })
                break  # Only add once per trap
    
    return available


def _apply_end_turn_passives(
    game_state: Dict[str, Any],
    player_index: int,
    log: List[Dict[str, Any]],
) -> None:
    """
    Apply hero passive effects that occur at end of controller's turn.
    Currently supports:
    - HERO_PASSIVE_END_TURN_HEAL_FULL: Heal all your monsters to full HP.
    """
    players = game_state.get("players", {})
    p_state = players.get(str(player_index))
    if not p_state:
        return
    hero = p_state.get("hero")
    if not hero:
        return

    effect_params = hero.get("effect_params") or {}
    if isinstance(effect_params, str):
        try:
            import json
            effect_params = json.loads(effect_params)
        except Exception:
            effect_params = {}

    passive_end_turn = effect_params.get("passive_end_turn")
    if not passive_end_turn:
        return

    if passive_end_turn.get("keyword") == "HERO_PASSIVE_END_TURN_HEAL_FULL":
        monster_zones = p_state.get("monster_zones") or []
        for idx, card in enumerate(monster_zones):
            if card is None:
                continue
            before_hp = card.get("hp", 0)
            max_hp = card.get("max_hp", before_hp)
            card["hp"] = max_hp
            monster_zones[idx] = card
            log.append(
                {
                    "type": "HERO_PASSIVE_HEAL_FULL",
                    "player": player_index,
                    "hero_instance_id": hero.get("instance_id"),
                    "zone_index": idx,
                    "card_instance_id": card.get("instance_id"),
                    "hp_before": before_hp,
                    "hp_after": max_hp,
                }
            )
        p_state["monster_zones"] = monster_zones
        players[str(player_index)] = p_state
        game_state["players"] = players


def _apply_hero_passive_aura(
    game_state: Dict[str, Any],
    player_index: int,
    hero: Dict[str, Any],
    log: List[Dict[str, Any]],
    target_monster_zone_index: Optional[int] = None,
) -> None:
    """
    Apply hero passive aura effects to monsters on the board.
    If target_monster_zone_index is provided, only apply to that monster (for newly summoned monsters).
    Otherwise, apply to all monsters on the board.
    
    Reads from hero's effect_params.passive_aura:
    {
      "passive_aura": {
        "atk_increase": 100,
        "hp_increase": 100
      }
    }
    """
    players = game_state.get("players", {})
    pkey = str(player_index)
    p_state = players.get(pkey)
    if not p_state:
        return
    
    # Get passive aura from effect_params
    effect_params = hero.get("effect_params") or {}
    if isinstance(effect_params, str):
        try:
            import json
            effect_params = json.loads(effect_params)
        except:
            effect_params = {}
    
    passive_aura = effect_params.get("passive_aura")
    if not passive_aura:
        # No passive aura defined
        return
    
    atk_inc = int(passive_aura.get("atk_increase", 0))
    hp_inc = int(passive_aura.get("hp_increase", 0))
    
    if atk_inc == 0 and hp_inc == 0:
        return
    
    # Apply to monsters on the board
    monster_zones = p_state.get("monster_zones") or []
    if target_monster_zone_index is not None:
        # Only apply to the newly summoned monster
        if target_monster_zone_index < len(monster_zones) and monster_zones[target_monster_zone_index] is not None:
            card = monster_zones[target_monster_zone_index]
            before_atk = card.get("atk", 0)
            before_hp = card.get("hp", 0)
            before_max_hp = card.get("max_hp") or before_hp
            
            card["atk"] = before_atk + atk_inc
            new_hp = before_hp + hp_inc
            new_max_hp = before_max_hp + hp_inc
            card["hp"] = max(0, min(new_hp, new_max_hp))
            card["max_hp"] = new_max_hp
            
            log.append({
                "type": "HERO_PASSIVE_AURA",
                "player": player_index,
                "hero_name": hero.get("name"),
                "zone_index": target_monster_zone_index,
                "monster_name": card.get("name"),
                "atk_before": before_atk,
                "atk_after": card["atk"],
                "hp_before": before_hp,
                "hp_after": card["hp"],
                "max_hp_before": before_max_hp,
                "max_hp_after": new_max_hp,
            })
    else:
        # Apply to all monsters on the board
        for zone_idx, card in enumerate(monster_zones):
            if card is None:
                continue
            
            before_atk = card.get("atk", 0)
            before_hp = card.get("hp", 0)
            before_max_hp = card.get("max_hp") or before_hp
            
            card["atk"] = before_atk + atk_inc
            new_hp = before_hp + hp_inc
            new_max_hp = before_max_hp + hp_inc
            card["hp"] = max(0, min(new_hp, new_max_hp))
            card["max_hp"] = new_max_hp
            
            log.append({
                "type": "HERO_PASSIVE_AURA",
                "player": player_index,
                "hero_name": hero.get("name"),
                "zone_index": zone_idx,
                "monster_name": card.get("name"),
                "atk_before": before_atk,
                "atk_after": card["atk"],
                "hp_before": before_hp,
                "hp_after": card["hp"],
                "max_hp_before": before_max_hp,
                "max_hp_after": new_max_hp,
            })
    
    p_state["monster_zones"] = monster_zones
    players[pkey] = p_state
    game_state["players"] = players


class TriggerTrapRequest(BaseModel):
    match_id: str
    player_index: int
    trap_instance_id: str
    pending_action: Optional[Dict[str, Any]] = None  # The action that triggered this
    trigger_type: Optional[str] = None
    trigger_event: Optional[Dict[str, Any]] = None


@app.post("/battle/trigger-trap")
def trigger_trap(payload: TriggerTrapRequest) -> Dict[str, Any]:
    """
    Activate a trap in response to a trigger event.
    This is called after the client receives trap_triggers_available.
    """
    # Load match
    match_resp = (
        supabase.table("matches")
        .select("id, status, serialized_game_state")
        .eq("id", payload.match_id)
        .single()
        .execute()
    )
    match_row = match_resp.data
    if not match_row:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if match_row.get("status") != "in_progress":
        raise HTTPException(status_code=400, detail="Match is not in progress")
    
    game_state = match_row.get("serialized_game_state")
    if not game_state:
        raise HTTPException(status_code=500, detail="Match has no game state stored")
    
    players = game_state.get("players") or {}
    pkey = str(payload.player_index)
    p_state = players.get(pkey)
    if not p_state:
        raise HTTPException(status_code=500, detail="Player state missing")
    
    # Find trap
    st_zones = p_state.get("spell_trap_zones") or []
    trap_card = None
    trap_zone_index = None
    for idx, slot in enumerate(st_zones):
        if slot is not None and slot.get("instance_id") == payload.trap_instance_id:
            trap_card = slot
            trap_zone_index = idx
            break
    
    if trap_card is None:
        raise HTTPException(status_code=400, detail="Trap not found")
    
    if not trap_card.get("face_down", True):
        raise HTTPException(status_code=400, detail="Trap is already face-up")
    
    targets: Dict[str, Any] = {}
    
    # Extract target from trigger_event if available
    trigger_event = payload.trigger_event or {}
    if isinstance(trigger_event, dict):
        # For prevent-destruction traps, extract monster_instance_id from trigger_event
        if trigger_event.get("type") == "MONSTER_WOULD_BE_DESTROYED":
            monster_instance_id = trigger_event.get("monster_instance_id")
            if monster_instance_id:
                found = find_monster_by_instance_id(game_state, monster_instance_id)
                if found:
                    targets["monster"] = {
                        "player_index": found["player_index"],
                        "zone_index": found["zone_index"],
                    }
        # For attack triggers, extract attacker_instance_id
        elif trigger_event.get("type") in ("ATTACK_MONSTER", "ATTACK_PLAYER"):
            attacker_instance_id = trigger_event.get("attacker_instance_id")
            if attacker_instance_id:
                found = find_monster_by_instance_id(game_state, attacker_instance_id)
                if found:
                    targets["monster"] = {
                        "player_index": found["player_index"],
                        "zone_index": found["zone_index"],
                    }
                    # Also set target_player_index to the attacking player
                    attacking_player = trigger_event.get("attacking_player")
                    if attacking_player:
                        targets["player"] = attacking_player
    
    # Create effect context
    ctx = EffectContext(
        game_state=game_state,
        source_player=payload.player_index,
        source_card=trap_card,
        targets=targets,
        trigger=payload.trigger_type or "ON_SPELL_CAST",
        trigger_event=trigger_event,
    )
    
    effect_result = resolve_card_effects(ctx)
    
    # Handle destroyed monsters
    _handle_destroyed_monsters(game_state, effect_result.destroyed_monsters)
    
    # Remove trap from zone
    st_zones[trap_zone_index] = None
    p_state["spell_trap_zones"] = st_zones
    
    # Move to graveyard
    graveyard = p_state.get("graveyard") or []
    graveyard.append(trap_card)
    p_state["graveyard"] = graveyard
    
    players[pkey] = p_state
    game_state["players"] = players
    
    log = game_state.get("log") or []
    log.append({
        "type": "TRAP_TRIGGERED",
        "player": payload.player_index,
        "trap_instance_id": payload.trap_instance_id,
        "card_name": trap_card.get("name"),
        "effects": effect_result.log_events,
        "cancelled_action": effect_result.cancelled,
    })
    
    # Initialize attack_completed flag
    attack_completed = False
    
    # If trap cancelled the action, don't process pending_action
    if effect_result.cancelled and payload.pending_action:
        log.append({
            "type": "ACTION_CANCELLED",
            "reason": "trap_counter",
            "original_action": payload.pending_action,
        })
        
        # Check if trap should reflect the spell back
        reflect_spell = False
        for eff in effect_result.log_events:
            if eff.get("type") == "EFFECT_COUNTER_AND_REFLECT_SPELL" or eff.get("reflect_spell"):
                reflect_spell = True
                break
        
        if reflect_spell and payload.pending_action and payload.pending_action.get("action") == "PLAY_SPELL":
            # Reflect spell back to caster's side
            pending_spell = payload.pending_action.get("play_spell", {})
            spell_caster = payload.pending_action.get("player_index")
            spell_target = pending_spell.get("target_monster_instance_id")
            
            # Find the original spell card from the trigger_event or reconstruct it
            # For now, we'll need to get the spell info from trigger_event
            trigger_event = payload.trigger_event or {}
            spell_card = trigger_event.get("spell_card")
            
            if spell_card and spell_caster:
                # Find a target on the caster's side (one of their monsters)
                caster_pkey = str(spell_caster)
                caster_state = players.get(caster_pkey)
                if caster_state:
                    caster_monsters = caster_state.get("monster_zones") or []
                    valid_targets = [m for m in caster_monsters if m is not None and m.get("hp", 0) > 0]
                    
                    if valid_targets:
                        # Auto-select first valid target for reflection
                        reflected_target = valid_targets[0]
                        reflected_target_instance_id = reflected_target.get("instance_id")
                        
                        # Apply the spell effect to the reflected target
                        found = find_monster_by_instance_id(game_state, reflected_target_instance_id)
                        if found:
                            reflected_targets = {
                                "monster": {
                                    "player_index": found["player_index"],
                                    "zone_index": found["zone_index"],
                                }
                            }
                            
                            # Create effect context for reflected spell
                            reflected_ctx = EffectContext(
                                game_state=game_state,
                                source_player=payload.player_index,  # Trap controller casts the reflected spell
                                source_card=spell_card,  # Use the original spell card
                                targets=reflected_targets,
                            )
                            
                            reflected_effect_result = resolve_card_effects(reflected_ctx)
                            _handle_destroyed_monsters(game_state, reflected_effect_result.destroyed_monsters)
                            
                            # Ensure monster zones are updated
                            monster_zones = caster_state.get("monster_zones") or []
                            caster_state["monster_zones"] = monster_zones
                            players[caster_pkey] = caster_state
                            game_state["players"] = players
                            
                            # Log the reflection
                            log.append({
                                "type": "SPELL_REFLECTED",
                                "original_caster": spell_caster,
                                "reflected_by": payload.player_index,
                                "spell_name": spell_card.get("name"),
                                "target_monster": reflected_target.get("name"),
                                "effects": reflected_effect_result.log_events,
                            })
                            
                            # Check lethal after reflected spell
                            _check_lethal_after_noncombat(
                                game_state=game_state,
                                players=players,
                                log=log,
                                reason="reflected_spell_effects",
                            )
    
    # Last Stand Ward: Just set HP to 1, let attack continue normally
    # If this was a prevent-destruction trap, the attack was already resolved; don't re-run it.
    attack_completed = False
    if (
        not effect_result.cancelled
        and payload.pending_action
        and payload.pending_action.get("action") == "ATTACK_MONSTER"
        and payload.trigger_type == "ON_ALLY_MONSTER_WOULD_BE_DESTROYED"
    ):
        # Mark attack as completed so frontend does NOT resend the attack.
        attack_completed = True
    
    # Save state
    supabase.table("matches").update({
        "serialized_game_state": game_state,
    }).eq("id", payload.match_id).execute()
    
    return {
        "match_id": payload.match_id,
        "game_state": game_state,
        "trap_activated": True,
        "cancelled_action": effect_result.cancelled,
        "attack_completed": attack_completed,
    }


class ProcessAITurnRequest(BaseModel):
    match_id: str
    ai_player_index: int


@app.post("/battle/ai-turn")
def process_ai_turn(payload: ProcessAITurnRequest) -> Dict[str, Any]:
    """
    Process AI turn in PVE mode.
    Repeatedly calls get_ai_action and processes actions until AI ends turn.
    """
    # Load match
    match_resp = (
        supabase.table("matches")
        .select("id, status, serialized_game_state, mode")
        .eq("id", payload.match_id)
        .single()
        .execute()
    )
    match_row = match_resp.data
    if not match_row:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if match_row.get("status") != "in_progress":
        raise HTTPException(status_code=400, detail="Match is not in progress")
    
    game_state = match_row.get("serialized_game_state")
    if not game_state:
        raise HTTPException(status_code=500, detail="Match has no game state stored")
    
    # Verify it's AI's turn
    if game_state.get("current_player") != payload.ai_player_index:
        return {
            "match_id": payload.match_id,
            "game_state": game_state,
            "ai_turn": False,
            "ai_actions_taken": [],
        }
    
    ai_actions_taken = []
    max_actions = 20  # Safety limit to prevent infinite loops
    action_count = 0
    
    # Process AI actions until it ends turn
    while action_count < max_actions:
        ai_action = get_ai_action(game_state, payload.ai_player_index)
        
        if ai_action is None or ai_action.get("action") == "END_TURN":
            # AI wants to end turn
            if ai_action and ai_action.get("action") == "END_TURN":
                # Process END_TURN
                end_turn_payload = BattleActionRequest(
                    match_id=payload.match_id,
                    player_index=payload.ai_player_index,
                    action="END_TURN",
                )
                result = battle_action(end_turn_payload)
                game_state = result["game_state"]
                ai_actions_taken.append({"action": "END_TURN"})
            break
        
        # Process the AI action
        try:
            action_type = ai_action.get("action")
            
            # Build BattleActionRequest - AI action has nested payloads like "play_monster", "play_spell", etc.
            battle_req_dict = {
                "match_id": payload.match_id,
                "player_index": payload.ai_player_index,
                "action": action_type,
            }
            
            # Extract the action-specific payload (e.g., "play_monster", "play_spell", "attack_monster")
            if "play_monster" in ai_action:
                battle_req_dict["play_monster"] = ai_action["play_monster"]
            elif "play_spell" in ai_action:
                battle_req_dict["play_spell"] = ai_action["play_spell"]
            elif "play_trap" in ai_action:
                battle_req_dict["play_trap"] = ai_action["play_trap"]
            elif "activate_hero_ability" in ai_action:
                battle_req_dict["activate_hero_ability"] = ai_action["activate_hero_ability"]
            elif "attack_monster" in ai_action:
                battle_req_dict["attack_monster"] = ai_action["attack_monster"]
            elif "attack_player" in ai_action:
                battle_req_dict["attack_player"] = ai_action["attack_player"]
            
            battle_req = BattleActionRequest(**battle_req_dict)
            
            result = battle_action(battle_req)
            game_state = result["game_state"]
            
            # Check if a player trap was triggered (requires player decision)
            if result.get("trap_triggers_available"):
                # AI action is blocked by player trap - return to frontend for player decision
                # Don't increment action_count or add to ai_actions_taken yet
                return {
                    "match_id": payload.match_id,
                    "game_state": game_state,
                    "ai_turn": True,  # Still AI's turn, but waiting for trap resolution
                    "ai_actions_taken": ai_actions_taken,
                    "trap_triggers_available": result["trap_triggers_available"],
                    "pending_action": result.get("pending_action"),
                    "trigger_type": result.get("trigger_type"),
                    "trigger_event": result.get("trigger_event"),
                }
            
            ai_actions_taken.append(ai_action)
            action_count += 1
            
            # Check if match ended
            if game_state.get("status") != "in_progress":
                break
                
        except Exception as e:
            print(f"AI action failed: {e}")
            # Force end turn if action fails
            end_turn_payload = BattleActionRequest(
                match_id=payload.match_id,
                player_index=payload.ai_player_index,
                action="END_TURN",
            )
            result = battle_action(end_turn_payload)
            game_state = result["game_state"]
            break
    
    # Save updated state
    supabase.table("matches").update({
        "serialized_game_state": game_state,
        "status": game_state.get("status", match_row.get("status")),
    }).eq("id", payload.match_id).execute()
    
    # Check if it's still AI's turn (shouldn't be after END_TURN, but check anyway)
    still_ai_turn = game_state.get("current_player") == payload.ai_player_index
    
    return {
        "match_id": payload.match_id,
        "game_state": game_state,
        "ai_turn": still_ai_turn,
        "ai_actions_taken": ai_actions_taken,
    }
