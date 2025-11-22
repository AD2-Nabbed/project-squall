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


class PlayMonsterPayload(BaseModel):
    card_instance_id: str
    zone_index: int  # 0-3 for now
    tribute_instance_ids: List[str] = []


class AttackMonsterPayload(BaseModel):
    attacker_instance_id: str
    defender_instance_id: str  # must target a monster on the opponent's field


class AttackPlayerPayload(BaseModel):
    attacker_instance_id: str


class BattleActionRequest(BaseModel):
    match_id: str
    player_index: int  # 1 or 2
    action: Literal["END_TURN", "PLAY_MONSTER", "ATTACK_MONSTER", "ATTACK_PLAYER"]
    play_monster: Optional[PlayMonsterPayload] = None
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

    # 3) Pick NPC (random or forced)
    npc = pick_random_npc_with_deck(payload.npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="No NPC with a deck found")

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
        "npc_id": npc["id"],
        "mode": "PVE",
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
# Battle: Take an action
# -------------------------------------------------------------------


@app.post("/battle/action")
def battle_action(payload: BattleActionRequest) -> Dict[str, Any]:
    """
    v0 action endpoint:
    - END_TURN
    - PLAY_MONSTER
    - ATTACK_MONSTER
    - ATTACK_PLAYER
    Loads match.game_state from Supabase, mutates, saves back, returns updated state.
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

    # ----------------------------------------------------------------
    # END_TURN
    # ----------------------------------------------------------------
    if payload.action == "END_TURN":
        next_player = 2 if current_player == 1 else 1

        # Bump turn counter
        game_state["turn"] = int(game_state.get("turn", 1)) + 1
        game_state["current_player"] = next_player

        # ---- START OF TURN for next_player ----
        nkey = str(next_player)
        p_state = players.get(nkey)
        if p_state is None:
            raise HTTPException(status_code=500, detail="Next player state missing")

        # Flip that player's monsters face-up AND ready them to attack
        monster_zones = p_state.get("monster_zones") or []
        for idx, slot in enumerate(monster_zones):
            if slot is not None:
                slot["face_down"] = False
                # if the monster is alive, it can attack this turn
                if slot.get("hp", 0) > 0:
                    slot["can_attack"] = True
        p_state["monster_zones"] = monster_zones

        # Draw 2 cards
        deck = p_state.get("deck") or []
        hand = p_state.get("hand") or []

        draws = min(2, len(deck))
        for _ in range(draws):
            drawn = deck.pop(0)
            hand.append(drawn)

        p_state["deck"] = deck
        p_state["hand"] = hand

        players[nkey] = p_state
        game_state["players"] = players

        # Set phase to MAIN for the new active player
        game_state["phase"] = "main"

        # Log the event
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

    # ----------------------------------------------------------------
    # PLAY_MONSTER
    # ----------------------------------------------------------------
    elif payload.action == "PLAY_MONSTER":
        if payload.play_monster is None:
            raise HTTPException(status_code=400, detail="Missing play_monster payload")

        pm = payload.play_monster
        p_state = players[pkey]

        monster_zones = p_state.get("monster_zones") or []
        if pm.zone_index < 0 or pm.zone_index >= len(monster_zones):
            raise HTTPException(status_code=400, detail="Invalid monster zone index")

        if monster_zones[pm.zone_index] is not None:
            raise HTTPException(status_code=400, detail="Monster zone is already occupied")

        hand = p_state.get("hand") or []
        hand_idx = next(
            (i for i, c in enumerate(hand) if c["instance_id"] == pm.card_instance_id),
            None,
        )
        if hand_idx is None:
            raise HTTPException(status_code=400, detail="Card not in hand")

        card = hand.pop(hand_idx)

        # Simple tribute rule: 4+ stars require at least one tribute
        tribute_ids = pm.tribute_instance_ids or []
        is_tribute_summon = len(tribute_ids) > 0

        if card.get("stars", 0) >= 4:
            if not tribute_ids:
                raise HTTPException(status_code=400, detail="Tributes required for high-star monster")

            # remove tributes from monster_zones and send to graveyard
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
            p_state["graveyard"] = graveyard

        # Put the monster on the field
        card["face_down"] = False
        # Summoning sickness rules:
        #   - Normal summon  -> cannot attack this turn
        #   - Tribute summon -> can attack immediately
        card["can_attack"] = bool(is_tribute_summon)

        monster_zones[pm.zone_index] = card

        p_state["monster_zones"] = monster_zones
        p_state["hand"] = hand
        players[pkey] = p_state
        game_state["players"] = players

        # Phase goes to MAIN once first monster is played
        game_state["phase"] = "main"

        log = game_state.get("log") or []
        log.append(
            {
                "type": "PLAY_MONSTER",
                "player": payload.player_index,
                "card_instance_id": pm.card_instance_id,
                "card_name": card.get("name"),
                "zone": pm.zone_index,
                "tributes": tribute_ids,
                "stars": card.get("stars"),
            }
        )
        game_state["log"] = log

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

        # Flip defender face-up if needed
        defender["face_down"] = False

        # Snapshot monster HP before combat
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

        # Move dead defender to graveyard
        if defender_died:
            def_graveyard.append(defender)
            def_mz[defender_zone_index] = None

        # Move dead attacker to graveyard or mark that it used its attack
        if attacker_died:
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

        log = game_state.get("log") or []
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

        game_state["log"] = log

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

        log = game_state.get("log") or []
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

        game_state["log"] = log

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
