from dataclasses import asdict
from uuid import uuid4
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.engine.factory import create_new_game_state
from app.db.supabase_client import supabase
from app.db.decks import load_deck_card_defs
from app.db.npcs import pick_random_npc_with_deck


app = FastAPI(
    title="Project Squall Battle Server",
    version="0.1.0"
)


class BattleStartRequest(BaseModel):
    player_id: str        # players.id (uuid)
    deck_id: str          # decks.id chosen by the player
    npc_id: str | None = None  # optional: force a specific NPC later



def _example_deck(card_prefix: str) -> list[dict[str, Any]]:
    """
    Temporary helper: build a small fake deck list.
    Later this will come from Supabase (decks + deck_cards + cards).
    """
    return [
        {
            "card_code": f"{card_prefix}-MON-001",
            "name": f"{card_prefix} Imp",
            "card_type": "monster",
            "stars": 1,
            "atk": 50,
            "hp": 50,
            "element_id": None,
            "effect_tags": [],
            "effect_params": {},
        },
        {
            "card_code": f"{card_prefix}-MON-002",
            "name": f"{card_prefix} Soldier",
            "card_type": "monster",
            "stars": 2,
            "atk": 100,
            "hp": 100,
            "element_id": None,
            "effect_tags": [],
            "effect_params": {},
        },
        {
            "card_code": f"{card_prefix}-MON-003",
            "name": f"{card_prefix} Guardian",
            "card_type": "monster",
            "stars": 3,
            "atk": 150,
            "hp": 150,
            "element_id": None,
            "effect_tags": [],
            "effect_params": {},
        },
        {
            "card_code": f"{card_prefix}-MON-004",
            "name": f"{card_prefix} Bruiser",
            "card_type": "monster",
            "stars": 2,
            "atk": 150,
            "hp": 50,
            "element_id": None,
            "effect_tags": [],
            "effect_params": {},
        },
        {
            "card_code": f"{card_prefix}-MON-005",
            "name": f"{card_prefix} Wall",
            "card_type": "monster",
            "stars": 2,
            "atk": 50,
            "hp": 150,
            "element_id": None,
            "effect_tags": [],
            "effect_params": {},
        },
    ]


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/battle/start")
def battle_start(payload: BattleStartRequest) -> Dict[str, Any]:
    """
    Proper battle start:
    - Load player (name) from players table
    - Load the player's deck from decks/deck_cards/cards/card_types
    - Pick an NPC (or use provided npc_id) and load its deck
    - Create GameState via engine
    - Insert match row into Supabase
    - Return match_id + initial game_state
    """

    # 1) Load player & gamer_tag
    player_resp = (
        supabase.table("players")
        .select("id, gamer_tag")
        .eq("id", payload.player_id)
        .single()
        .execute()
    )
    player = player_resp.data
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    player_name = player["gamer_tag"]

    # 2) Load player deck definitions
    try:
        player_deck_defs = load_deck_card_defs(payload.deck_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3) Choose NPC + load its deck
    #    (for now: always random if npc_id is None)
    if payload.npc_id:
        from app.db.npcs import load_npc_with_deck
        npc, npc_deck_defs = load_npc_with_deck(payload.npc_id)
    else:
        npc, npc_deck_defs = pick_random_npc_with_deck()

    npc_name = npc["display_name"]
    npc_id = npc["id"]
    npc_deck_id = npc["deck_id"]

    # 4) Create GameState through engine
    match_id = str(uuid4())

    game_state = create_new_game_state(
        match_id=match_id,
        player1_name=player_name,
        player1_deck=player_deck_defs,
        player2_name=npc_name,
        player2_deck=npc_deck_defs,
    )

    # 5) Persist match to Supabase
    game_state_json = asdict(game_state)

    match_record = {
        "id": match_id,
        "player1_id": payload.player_id,
        "player1_deck_id": payload.deck_id,
        "player2_id": None,  # NPC, so null for now
        "player2_deck_id": npc_deck_id,
        "npc_id": npc_id,
        "serialized_game_state": game_state_json,
        "status": "in_progress",
    }

    supabase.table("matches").insert(match_record).execute()

    # 6) Return match_id + state to client
    return {
        "match_id": match_id,
        "game_state": game_state_json,
    }

