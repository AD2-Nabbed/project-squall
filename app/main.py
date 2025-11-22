from __future__ import annotations

from uuid import uuid4
from typing import Any, Dict, Literal, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.engine.factory import create_new_game_state
from app.engine.models import GameState, CardInstance
from app.db.supabase_client import supabase
from app.db.decks import load_deck_card_defs
from app.db.npcs import pick_random_npc_with_deck


app = FastAPI(
    title="Project Squall Battle Server",
    version="0.1.0",
)


# -------------------------------------------------------------------
# Helpers to serialize GameState -> plain JSON dict (for Supabase)
# -------------------------------------------------------------------

def card_instance_to_dict(ci: CardInstance) -> Dict[str, Any]:
    """
    Convert a CardInstance dataclass into a JSON-serializable dict.
    """
    # statuses was originally a set; you’ve now made it a list,
    # but this keeps us safe either way.
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
    npc_id: Optional[str] = None  # optional: force a specific NPC later


class BattleActionRequest(BaseModel):
    match_id: str
    player_index: int  # 1 or 2
    action: Literal["END_TURN"]


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

    # Optional: enforce that this deck is owned by the requesting player
    owner_id = deck_row.get("owner_id")
    if owner_id is not None and owner_id != payload.player_id:
        raise HTTPException(status_code=403, detail="Deck does not belong to this player")

    # 3) Pick NPC (random or forced)
    npc = pick_random_npc_with_deck(payload.npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="No NPC with a deck found")

    # npc table uses "display_name"
    npc_name = npc["display_name"]
    npc_deck_id = npc["deck_id"]

    # 4) Load deck card definitions for both players
    player_deck_defs = load_deck_card_defs(payload.deck_id)
    npc_deck_defs = load_deck_card_defs(npc_deck_id)

    if not player_deck_defs:
        raise HTTPException(status_code=400, detail="Player deck has no cards")

    if not npc_deck_defs:
        raise HTTPException(status_code=400, detail="NPC deck has no cards")

    # 5) Create a new GameState via the engine
    match_id = str(uuid4())

    game_state: GameState = create_new_game_state(
        match_id=match_id,
        player1_name=player_row["gamer_tag"],
        player2_name=npc_name,
        deck1_defs=player_deck_defs,
        deck2_defs=npc_deck_defs,
    )

    game_state_dict = game_state_to_dict(game_state)

    # 6) Persist match in Supabase
    match_record = {
        "id": match_id,
        "player1_id": payload.player_id,
        "npc_id": npc["id"],  # <-- NEW
        "mode": "PVE",  # <-- NEW
        "status": "in_progress",
        "serialized_game_state": game_state_dict,
    }
    supabase.table("matches").insert(match_record).execute()

    # 7) Return initial state
    return {
        "match_id": match_id,
        "game_state": game_state_dict,
    }


# -------------------------------------------------------------------
# Battle: Take an action (v0: only END_TURN)
# -------------------------------------------------------------------

@app.post("/battle/action")
def battle_action(payload: BattleActionRequest) -> Dict[str, Any]:
    """
    Minimal action endpoint for v0:
    - Currently supports only END_TURN
    - Loads match.game_state from Supabase
    - Mutates turn/current_player/phase
    - Applies simple Start+Draw for the next player
    - Saves back to Supabase
    - Returns updated game_state
    """

    # 1) Load the match + serialized_game_state
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

    # 2) Basic validation: is it this player's turn?
    current_player = game_state.get("current_player")
    if current_player != payload.player_index:
        raise HTTPException(status_code=400, detail="It is not this player's turn")

    # 3) Handle the action
    if payload.action == "END_TURN":
        next_player = 2 if current_player == 1 else 1

        # Bump turn counter
        game_state["turn"] = int(game_state.get("turn", 1)) + 1
        game_state["current_player"] = next_player

        # ---- START OF TURN for next_player ----
        players = game_state.get("players") or {}
        pkey = str(next_player)
        p_state = players.get(pkey)
        if p_state is None:
            raise HTTPException(status_code=500, detail="Next player state missing")

        # 3a) Flip that player's monsters face-up
        monster_zones = p_state.get("monster_zones") or []
        for idx, slot in enumerate(monster_zones):
            if slot is not None:
                slot["face_down"] = False
        p_state["monster_zones"] = monster_zones

        # 3b) Draw 2 cards
        deck = p_state.get("deck") or []
        hand = p_state.get("hand") or []

        draws = min(2, len(deck))
        for _ in range(draws):
            drawn = deck.pop(0)
            hand.append(drawn)

        p_state["deck"] = deck
        p_state["hand"] = hand

        players[pkey] = p_state
        game_state["players"] = players

        # Set phase to MAIN for the new active player
        game_state["phase"] = "main"

        # 3c) Log the event
        log = game_state.get("log") or []
        log.append(
            {
                "type": "END_TURN",
                "from_player": payload.player_index,
                "to_player": next_player,
                "turn": game_state["turn"],
                "phase": game_state["phase"],
            }
        )
        game_state["log"] = log

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {payload.action}")

    # 4) Persist updated state back into Supabase
    supabase.table("matches").update(
        {
            "serialized_game_state": game_state,
        }
    ).eq("id", payload.match_id).execute()

    # 5) Return updated state
    return {
        "match_id": payload.match_id,
        "game_state": game_state,
    }
