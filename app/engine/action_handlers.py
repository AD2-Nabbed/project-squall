"""Individual action handlers for battle actions."""
from typing import Dict, Any, Optional, List, Tuple
from app.engine.effects.resolver import resolve_card_effects, EffectContext, EffectResult
from fastapi import HTTPException
from app.engine.game_state_helpers import find_monster_by_instance_id

def handle_play_spell(
    game_state: Dict[str, Any],
    player_index: int,
    card_instance_id: str,
    target_player_index: Optional[int],
    target_monster_instance_id: Optional[str],
) -> None:
    """Handle PLAY_SPELL action."""
    players = game_state.get("players", {})
    pkey = str(player_index)
    p_state = players.get(pkey)
    if not p_state:
        raise HTTPException(status_code=400, detail="Player not found")

    hand = p_state.get("hand") or []
    hand_idx = next(
        (i for i, c in enumerate(hand) if c["instance_id"] == card_instance_id),
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
    p_state["hand"] = hand

    # Build target context for resolver
    targets: Dict[str, Any] = {}
    if target_player_index is not None:
        targets["player"] = target_player_index
    
    if target_monster_instance_id:
        found = find_monster_by_instance_id(game_state, target_monster_instance_id)
        if found:
            targets["monster"] = {
                "player_index": found["player_index"],
                "zone_index": found["zone_index"],
            }

    # Create effect context and resolve
    ctx = EffectContext(
        game_state=game_state,
        source_player=player_index,
        source_card=card,
        targets=targets,
    )

    effect_result = resolve_card_effects(ctx)

    # Handle destroyed monsters (move to graveyard)
    for player_idx, zone_idx in effect_result.destroyed_monsters:
        pkey_destroyed = str(player_idx)
        destroyed_state = players[pkey_destroyed]
        monster_zones = destroyed_state.get("monster_zones") or []
        if zone_idx < len(monster_zones) and monster_zones[zone_idx] is not None:
            destroyed_card = monster_zones[zone_idx]
            graveyard = destroyed_state.get("graveyard") or []
            graveyard.append(destroyed_card)
            monster_zones[zone_idx] = None
            destroyed_state["graveyard"] = graveyard
            destroyed_state["monster_zones"] = monster_zones
            players[pkey_destroyed] = destroyed_state

    # Move spell to graveyard after resolution
    graveyard = p_state.get("graveyard") or []
    graveyard.append(card)
    p_state["graveyard"] = graveyard
    players[pkey] = p_state
    game_state["players"] = players

    # Build spell log entry
    log = game_state.get("log") or []
    spell_log_entry: Dict[str, Any] = {
        "type": "PLAY_SPELL",
        "player": player_index,
        "card_instance_id": card_instance_id,
        "card_name": card.get("name"),
        "effects": effect_result.log_events,
    }
    log.append(spell_log_entry)
    game_state["log"] = log

    # Check lethal from non-combat effects
    from app.main import _check_lethal_after_noncombat
    _check_lethal_after_noncombat(
        game_state=game_state,
        players=players,
        log=log,
        reason="spell_effects",
    )

def handle_activate_trap(
    game_state: Dict[str, Any],
    player_index: int,
    trap_instance_id: str,
    target_player_index: Optional[int],
    target_monster_instance_id: Optional[str],
    trigger_event: Optional[Dict[str, Any]] = None,
) -> None:
    """Handle ACTIVATE_TRAP action."""
    players = game_state.get("players", {})
    pkey = str(player_index)
    p_state = players.get(pkey)
    if not p_state:
        raise HTTPException(status_code=400, detail="Player not found")

    st_zones = p_state.get("spell_trap_zones") or []
    trap_card = None
    trap_zone_index = None
    for idx, slot in enumerate(st_zones):
        if slot is not None and slot.get("instance_id") == trap_instance_id:
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
    if target_player_index is not None:
        targets["player"] = target_player_index
    
    if target_monster_instance_id:
        found = find_monster_by_instance_id(game_state, target_monster_instance_id)
        if found:
            targets["monster"] = {
                "player_index": found["player_index"],
                "zone_index": found["zone_index"],
            }

    # Create effect context and resolve
    ctx = EffectContext(
        game_state=game_state,
        source_player=player_index,
        source_card=trap_card,
        targets=targets,
        trigger_event=trigger_event,
    )

    effect_result = resolve_card_effects(ctx)

    # Handle destroyed monsters (move to graveyard)
    for player_idx, zone_idx in effect_result.destroyed_monsters:
        pkey_destroyed = str(player_idx)
        destroyed_state = players[pkey_destroyed]
        monster_zones = destroyed_state.get("monster_zones") or []
        if zone_idx < len(monster_zones) and monster_zones[zone_idx] is not None:
            destroyed_card = monster_zones[zone_idx]
            graveyard = destroyed_state.get("graveyard") or []
            graveyard.append(destroyed_card)
            monster_zones[zone_idx] = None
            destroyed_state["graveyard"] = graveyard
            destroyed_state["monster_zones"] = monster_zones
            players[pkey_destroyed] = destroyed_state

    # Remove trap from zone and put into graveyard
    st_zones[trap_zone_index] = None
    p_state["spell_trap_zones"] = st_zones

    graveyard = p_state.get("graveyard") or []
    graveyard.append(trap_card)
    p_state["graveyard"] = graveyard

    players[pkey] = p_state
    game_state["players"] = players

    # Build trap log entry
    log = game_state.get("log") or []
    trap_log_entry: Dict[str, Any] = {
        "type": "ACTIVATE_TRAP",
        "player": player_index,
        "trap_instance_id": trap_instance_id,
        "card_name": trap_card.get("name"),
        "effects": effect_result.log_events,
    }
    log.append(trap_log_entry)
    game_state["log"] = log

    # Check lethal from non-combat effects
    from app.main import _check_lethal_after_noncombat
    _check_lethal_after_noncombat(
        game_state=game_state,
        players=players,
        log=log,
        reason="trap_effects",
    )
