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
    spell_log_entry: Dict[str, Any] = {
        "type": "PLAY_SPELL",
        "player": player_index,
        "card_instance_id": card_instance_id,
        "card_name": card.get("name"),
        "effects": effect_result.log_events,
    }
    log.append(spell_log_entry)

    # Check lethal from non-combat effects
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
    trap_log_entry: Dict[str, Any] = {
        "type": "ACTIVATE_TRAP",
        "player": player_index,
        "trap_instance_id": trap_instance_id,
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
```

## 2. Fix parameter name compatibility in resolver

The resolver expects different parameter names than what's currently in the DB. Update the resolver to support both:

```python:app/engine/effects/resolver.py
# Update handle_spell_buff_monster (around line 450):
def handle_spell_buff_monster(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    ref = _get_monster_ref_from_targets(ctx)
    if not ref:
        return EffectResult(
            log_events=[
                {
                    "type": "EFFECT_NO_TARGET",
                    "reason": "MONSTER_NOT_FOUND",
                    "card_code": ctx.source_card.get("card_code"),
                }
            ]
        )

    # Support both naming conventions
    atk_inc = int(params.get("atk_increase") or params.get("amount_atk") or params.get("atk_delta", 0))
    hp_inc = int(params.get("hp_increase") or params.get("amount_hp") or params.get("hp_delta", 0))

    player_index, zone_index, card = ref
    before_atk = card.get("atk", 0)
    before_hp = card.get("hp", 0)
    before_max_hp = card.get("max_hp") or before_hp

    card["atk"] = before_atk + atk_inc
    new_hp = before_hp + hp_inc
    new_max_hp = before_max_hp + hp_inc
    card["hp"] = _clamp_hp(new_hp, new_max_hp)
    card["max_hp"] = new_max_hp  # Update max_hp for buffs

    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_BUFF_MONSTER",
                "player_index": player_index,
                "zone_index": zone_index,
                "atk_before": before_atk,
                "atk_after": card["atk"],
                "hp_before": before_hp,
                "hp_after": card["hp"],
                "max_hp_before": before_max_hp,
                "max_hp_after": new_max_hp,
                "card_instance_id": card.get("instance_id"),
            }
        ]
    )

# Update handle_spell_draw_cards (around line 415):
def handle_spell_draw_cards(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    # Support both "count" and "amount"
    amount = int(params.get("count") or params.get("amount", 0))
    if amount <= 0:
        return EffectResult()

    player_index = ctx.targets.get("player")
    if not isinstance(player_index, int):
        player_index = ctx.source_player

    gs_player = _get_player(ctx.game_state, player_index)
    deck = gs_player.get("deck", [])
    hand = gs_player.get("hand", [])

    drawn: List[Dict[str, Any]] = []
    for _ in range(amount):
        if not deck:
            break
        card = deck.pop(0)
        hand.append(card)
        drawn.append(card)

    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_DRAW_CARDS",
                "player_index": player_index,
                "amount": len(drawn),
                "card_instance_ids": [c.get("instance_id") for c in drawn],
            }
        ]
    )

# Update handle_spell_apply_status (around line 406):
def handle_spell_apply_status(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    # Support both "status" and "status_code"
    status_code = params.get("status_code") or params.get("status")
    duration_type = params.get("duration_type", "PERMANENT")
    duration_value = params.get("duration_value")  # optional int
    return _apply_status_to_monster(ctx, status_code, duration_type, duration_value)
```

## 3. Code cleanup suggestions

### A. Extract helper functions

Create a helper module `app/engine/actions.py` to reduce `main.py` size:

```python:app/engine/actions.py
"""Helper functions for battle actions that can be reused."""
from typing import Dict, Any, List, Optional, Tuple

def handle_destroyed_monsters(
    game_state: Dict[str, Any],
    destroyed_monsters: List[Tuple[int, int]],
) -> None:
    """Move destroyed monsters to graveyard."""
    players = game_state.get("players", {})
    for player_idx, zone_idx in destroyed_monsters:
        pkey = str(player_idx)
        player_state = players.get(pkey)
        if not player_state:
            continue
        
        monster_zones = player_state.get("monster_zones") or []
        if zone_idx < len(monster_zones) and monster_zones[zone_idx] is not None:
            destroyed_card = monster_zones[zone_idx]
            graveyard = player_state.get("graveyard") or []
            graveyard.append(destroyed_card)
            monster_zones[zone_idx] = None
            player_state["graveyard"] = graveyard
            player_state["monster_zones"] = monster_zones
```

### B. Remove duplicate code

The `_get_effects_from_card` function (line 219) is no longer needed since the resolver handles this internally.

### C. Standardize status handling

The resolver uses structured status objects `{"code": str, "duration_type": str, ...}`, but the current code uses simple strings. Update the resolver's `_apply_status_to_monster` to support both formats for backward compatibility:

```python:app/engine/effects/resolver.py
# In _apply_status_to_monster, support both formats:
def _apply_status_to_monster(
    ctx: EffectContext, status_code: str, duration_type: str, duration_value: Optional[int]
) -> EffectResult:
    # ... existing code ...
    
    # Support both old format (list of strings) and new format (list of objects)
    statuses = card.get("statuses") or []
    
    # If statuses is a list of strings, convert to new format
    if statuses and isinstance(statuses[0], str):
        statuses = [{"code": s, "duration_type": "PERMANENT"} for s in statuses]
        card["statuses"] = statuses
    
    status_entry = {
        "code": status_code,
        "duration_type": duration_type,
    }
    if duration_value is not None:
        status_entry["duration_value"] = duration_value
    
    # Check if status already exists (by code)
    if not any(s.get("code") == status_code for s in statuses):
        statuses.append(status_entry)
    
    # ... rest of function ...
```

### D. Create a game state helper module

Extract common game state operations:

```python:app/engine/game_state_helpers.py
"""Helper functions for manipulating serialized game state."""
from typing import Dict, Any, Optional

def get_player_state(game_state: Dict[str, Any], player_index: int) -> Dict[str, Any]:
    """Get player state by index."""
    return game_state.get("players", {}).get(str(player_index), {})

def find_monster_by_instance_id(
    game_state: Dict[str, Any],
    instance_id: str,
) -> Optional[Dict[str, Any]]:
    """Find a monster by instance_id across all players."""
    players = game_state.get("players", {})
    for pkey, p_state in players.items():
        monster_zones = p_state.get("monster_zones") or []
        for idx, slot in enumerate(monster_zones):
            if slot is not None and slot.get("instance_id") == instance_id:
                return {
                    "player_index": int(pkey),
                    "zone_index": idx,
                    "card": slot,
                }
    return None
```

### E. Split `battle_action` into smaller functions

Break the large `battle_action` function into action-specific handlers:

```python:app/engine/action_handlers.py
<code_block_to_apply_changes_from>
```

## Summary

1. Route `PLAY_SPELL` and `ACTIVATE_TRAP` through the resolver
2. Update resolver parameter names for compatibility
3. Extract helper functions to reduce duplication
4. Remove unused code (`_get_effects_from_card`)
5. Standardize status format handling
6. Split `battle_action` into smaller, focused functions

This aligns with the system rules: keyword-based resolution, no hardcoded effects, and easier extension via DB rows.

Should I provide the complete refactored `main.py` with these changes integrated?
