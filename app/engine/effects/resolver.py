from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# --- Public API -----------------------------------------------------------------


@dataclass
class EffectContext:
    """
    Context passed into keyword handlers.

    This deliberately stays very generic so the battle engine can evolve
    without having to rewrite every keyword function.

    Attributes
    ----------
    game_state:
        Full in-memory game state (the same structure you already serialize).
    source_player:
        Index of the player who controls the card (1 or 2).
    source_card:
        The card instance dict that is generating the effect.
    targets:
        Arbitrary target data resolved by the action layer. For example:
          - {"monster": {"player_index": 2, "zone_index": 0}}
          - {"player": 1}
          - {"monsters": [...]}
    trigger:
        Optional trigger string for traps / reactive effects, e.g.
        "ON_MONSTER_ATTACKS_PLAYER", "ON_INCOMING_SPELL", etc.
    trigger_event:
        Raw event payload that caused this effect to fire (attack log entry,
        spell cast description, etc.). Keyword handlers can inspect this if
        they need more detail than the high-level `trigger` string.
    """
    game_state: Dict[str, Any]
    source_player: int
    source_card: Dict[str, Any]
    targets: Dict[str, Any] = field(default_factory=dict)
    trigger: Optional[str] = None
    trigger_event: Optional[Dict[str, Any]] = None


@dataclass
class EffectResult:
    """
    Result of resolving one or more keyword effects.

    The battle engine can choose how to use this; nothing here mutates the
    persistent DB by itself – it only mutates the passed-in `game_state`.
    """
    log_events: List[Dict[str, Any]] = field(default_factory=list)
    destroyed_monsters: List[Tuple[int, int]] = field(default_factory=list)  # (player_index, zone_index)
    cancelled: bool = False  # used for things like SPELL_COUNTER_SPELL


def resolve_card_effects(
    ctx: EffectContext,
) -> EffectResult:
    """
    Entrypoint called by the action layer when a spell / trap / hero power
    needs to resolve its effects.

    It expects the card instance to have an `effect_params` payload that
    matches the CSV you imported, e.g.:

        {
          "max_copies_per_deck": 1,
          "effects": [
            {
              "keyword": "SPELL_DAMAGE_MONSTER",
              "target": "ENEMY_MONSTER",
              "amount": 150,
              "overflow_to_player": true
            }
          ]
        }
    """
    card_effect_params = ctx.source_card.get("effect_params") or {}

    # In case the card came from Supabase with effect_params as a JSON string.
    if isinstance(card_effect_params, str):
        import json  # local import to avoid forcing it on callers
        card_effect_params = json.loads(card_effect_params)

    effects = card_effect_params.get("effects") or []
    result = EffectResult()

    for raw_effect in effects:
        keyword = raw_effect.get("keyword")
        if not keyword:
            continue

        # Normalize keyword (uppercase, strip whitespace) for case-insensitive lookup
        keyword_normalized = keyword.upper().strip() if keyword else ""
        # Try normalized keyword first, then original as fallback
        handler = KEYWORD_HANDLERS.get(keyword_normalized) or KEYWORD_HANDLERS.get(keyword)
        if not handler:
            # Unknown keyword – safe no-op, but log it for debugging.
            result.log_events.append(
                {
                    "type": "EFFECT_UNKNOWN_KEYWORD",
                    "keyword": keyword,
                    "keyword_normalized": keyword_normalized,
                    "card_code": ctx.source_card.get("card_code"),
                    "available_handlers": list(KEYWORD_HANDLERS.keys())[:10],  # First 10 for debugging
                }
            )
            continue

        handler_result = handler(ctx, raw_effect)
        _merge_effect_results(result, handler_result)

        # Some keywords (like hard counters) might mark the chain as cancelled.
        if result.cancelled:
            break

    return result


# --- Internal helpers -----------------------------------------------------------


def _merge_effect_results(base: EffectResult, delta: Optional[EffectResult]) -> None:
    if not delta:
        return
    base.log_events.extend(delta.log_events)
    base.destroyed_monsters.extend(delta.destroyed_monsters)
    if delta.cancelled:
        base.cancelled = True


def _get_player(gs: Dict[str, Any], player_index: int) -> Dict[str, Any]:
    # game_state["players"] uses string keys "1", "2"
    return gs["players"][str(player_index)]


def _clamp_hp(current: int, max_hp: Optional[int]) -> int:
    if max_hp is None:
        return current
    return max(0, min(current, max_hp))


def _apply_damage_to_player(
    gs: Dict[str, Any], player_index: int, amount: int
) -> EffectResult:
    player = _get_player(gs, player_index)
    before = player.get("hp", 0)
    after = max(0, before - max(0, amount))
    player["hp"] = after

    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_DAMAGE_PLAYER",
                "player_index": player_index,
                "amount": amount,
                "hp_before": before,
                "hp_after": after,
            }
        ]
    )


def _apply_heal_to_player(
    gs: Dict[str, Any], player_index: int, amount: int
) -> EffectResult:
    player = _get_player(gs, player_index)
    before = player.get("hp", 0)
    max_hp = player.get("max_hp")  # optional – you can add this later
    after_raw = before + max(0, amount)
    after = _clamp_hp(after_raw, max_hp)
    player["hp"] = after

    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_HEAL_PLAYER",
                "player_index": player_index,
                "amount": amount,
                "hp_before": before,
                "hp_after": after,
            }
        ]
    )


def _get_monster_ref_from_targets(
    ctx: EffectContext,
) -> Optional[Tuple[int, int, Dict[str, Any]]]:
    """
    Helper for single-target monster effects.

    Expects ctx.targets["monster"] in one of these shapes:

      - {"player_index": 1, "zone_index": 0}
      - {"player_index": 1, "zone_index": 0, "card": {...}}

    The action layer is responsible for putting the correct data in here.
    """
    monster_target = ctx.targets.get("monster")
    if not monster_target:
        return None

    player_index = monster_target.get("player_index")
    zone_index = monster_target.get("zone_index")
    if player_index is None or zone_index is None:
        return None

    gs_player = _get_player(ctx.game_state, player_index)
    zones = gs_player.get("monster_zones", [])
    if zone_index < 0 or zone_index >= len(zones):
        return None

    card = zones[zone_index]
    if card is None:
        return None

    return player_index, zone_index, card


def _apply_damage_to_monster(
    ctx: EffectContext, amount: int
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

    player_index, zone_index, card = ref
    before = card.get("hp", 0)
    after = max(0, before - max(0, amount))
    card["hp"] = after

    result = EffectResult(
        log_events=[
            {
                "type": "EFFECT_DAMAGE_MONSTER",
                "player_index": player_index,
                "zone_index": zone_index,
                "amount": amount,
                "hp_before": before,
                "hp_after": after,
                "card_instance_id": card.get("instance_id"),
            }
        ]
    )

    if after <= 0:
        # Let the higher-level battle engine actually move it to graveyard,
        # but we flag that this monster should be destroyed.
        result.destroyed_monsters.append((player_index, zone_index))

    return result


def _apply_heal_to_monster(
    ctx: EffectContext, amount: int
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

    player_index, zone_index, card = ref
    before = card.get("hp", 0)
    max_hp = card.get("max_hp")
    after_raw = before + max(0, amount)
    after = _clamp_hp(after_raw, max_hp)
    card["hp"] = after

    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_HEAL_MONSTER",
                "player_index": player_index,
                "zone_index": zone_index,
                "amount": amount,
                "hp_before": before,
                "hp_after": after,
                "card_instance_id": card.get("instance_id"),
            }
        ]
    )


def _apply_status_to_monster(
    ctx: EffectContext, status_code: str, duration_type: str, duration_value: Optional[int]
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

    player_index, zone_index, card = ref

    # Support both old format (list of strings) and new format (list of objects)
    statuses = card.get("statuses") or []
    
    # If statuses is a list of strings, convert to new format
    if statuses and isinstance(statuses[0], str):
        statuses = [{"code": s, "duration_type": "PERMANENT"} for s in statuses]
        card["statuses"] = statuses
    
    # Check if monster has STATUS_IMMUNE (prevents all status application)
    has_status_immune = any(s.get("code") == "STATUS_IMMUNE" for s in statuses)
    if has_status_immune and status_code != "STATUS_IMMUNE":
        # Monster is immune to statuses (except STATUS_IMMUNE itself can be applied)
        return EffectResult(
            log_events=[
                {
                    "type": "EFFECT_STATUS_BLOCKED",
                    "reason": "STATUS_IMMUNE",
                    "player_index": player_index,
                    "zone_index": zone_index,
                    "card_instance_id": card.get("instance_id"),
                    "blocked_status": status_code,
                }
            ]
        )
    
    status_entry = {
        "code": status_code,
        "duration_type": duration_type,
    }
    if duration_value is not None:
        status_entry["duration_value"] = duration_value
    
    # Check if status already exists (by code)
    if not any(s.get("code") == status_code for s in statuses):
        statuses.append(status_entry)
    
    card["statuses"] = statuses

    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_STATUS_APPLIED",
                "player_index": player_index,
                "zone_index": zone_index,
                "status": status_entry,
                "card_instance_id": card.get("instance_id"),
            }
        ]
    )


# --- Keyword handlers -----------------------------------------------------------


KeywordHandler = Callable[[EffectContext, Dict[str, Any]], EffectResult]


def handle_spell_damage_monster(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    amount = int(params.get("amount", 0))
    overflow_to_player = bool(params.get("overflow_to_player", False))

    result = _apply_damage_to_monster(ctx, amount)

    # Optional overflow to the defending player if there was excess damage.
    # Overflow = max(0, damage_amount - monster_hp_before)
    # Example: 150 damage to 150 HP monster = 0 overflow
    #          150 damage to 100 HP monster = 50 overflow
    #          150 damage to 0 HP monster = 150 overflow
    if overflow_to_player:
        # Get the monster's HP before damage from the log event
        hp_before = None
        if result.log_events:
            for event in result.log_events:
                if event.get("type") == "EFFECT_DAMAGE_MONSTER":
                    hp_before = event.get("hp_before", 0)
                    break
        
        if hp_before is not None:
            # Calculate overflow: excess damage beyond what was needed to kill the monster
            overflow_amount = max(0, amount - hp_before)
            
            if overflow_amount > 0:
                # Get the target player (the controller of the monster that was damaged)
                target_player_index = ctx.targets.get("player")
                if not isinstance(target_player_index, int):
                    # If not specified, get it from the monster that was damaged
                    if result.log_events:
                        for event in result.log_events:
                            if event.get("type") == "EFFECT_DAMAGE_MONSTER":
                                target_player_index = event.get("player_index")
                                break
                
                if isinstance(target_player_index, int):
                    overflow_res = _apply_damage_to_player(
                        ctx.game_state, target_player_index, overflow_amount
                    )
                    _merge_effect_results(result, overflow_res)

    return result


def handle_spell_damage_player(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    amount = int(params.get("amount", 0))

    # If the action layer didn’t specify a player target, default to the
    # opposing player.
    target_player_index = ctx.targets.get("player")
    if not isinstance(target_player_index, int):
        target_player_index = 1 if ctx.source_player == 2 else 2

    return _apply_damage_to_player(ctx.game_state, target_player_index, amount)


def handle_spell_heal_player(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    amount = int(params.get("amount", 0))

    target_player_index = ctx.targets.get("player")
    if not isinstance(target_player_index, int):
        # Default heal to the caster if no explicit target.
        target_player_index = ctx.source_player

    return _apply_heal_to_player(ctx.game_state, target_player_index, amount)


def handle_spell_heal_monster(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    amount = int(params.get("amount", 0))
    return _apply_heal_to_monster(ctx, amount)


def handle_spell_apply_status(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    # Support both "status" and "status_code"
    status_code = params.get("status_code") or params.get("status")
    duration_type = params.get("duration_type", "PERMANENT")
    duration_value = params.get("duration_value")  # optional int
    return _apply_status_to_monster(ctx, status_code, duration_type, duration_value)


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


def _find_lowest_hp_monster(game_state: Dict[str, Any], player_index: int) -> Optional[Tuple[int, Dict[str, Any]]]:
    """Return (zone_index, card) of the lowest-HP monster for the given player, or None."""
    players = game_state.get("players", {})
    p_state = players.get(str(player_index))
    if not p_state:
        return None
    monster_zones = p_state.get("monster_zones") or []
    lowest = None
    for idx, card in enumerate(monster_zones):
        if card is None:
            continue
        hp = card.get("hp", 0)
        if lowest is None or hp < lowest[1].get("hp", 0):
            lowest = (idx, card)
    return lowest


def handle_hero_active_soul_rend(ctx: EffectContext, params: Dict[str, Any]) -> EffectResult:
    """
    Hero active: Soul Rend
    - Cost: charge_cost (default 3) from hero_charges
    - Destroy one face-up enemy monster (target must be face-up if target_face_up=True)
    - If destroyed monster hp_before > threshold (default 200), buff lowest-HP ally monster +hp_buff (default 100 HP)
    """
    source_card = ctx.source_card
    charge_cost = int(params.get("charge_cost", 3))
    hp_threshold = int(params.get("if_target_hp_gt", 200))
    buff_amount = int(params.get("buff_lowest_ally_hp_increase", 100))
    require_face_up = bool(params.get("target_face_up", True))

    # Charges live on the hero card
    current_charges = int(source_card.get("hero_charges", 0) or 0)
    if current_charges < charge_cost:
        return EffectResult(
            cancelled=True,
            log_events=[
                {
                    "type": "EFFECT_HERO_NOT_ENOUGH_CHARGES",
                    "needed": charge_cost,
                    "current": current_charges,
                }
            ],
        )

    # Target monster
    ref = _get_monster_ref_from_targets(ctx)
    if not ref:
        return EffectResult(
            log_events=[
                {
                    "type": "EFFECT_NO_TARGET",
                    "reason": "MONSTER_NOT_FOUND",
                    "card_code": source_card.get("card_code"),
                }
            ]
        )

    target_player_index, target_zone_index, target_card = ref

    if require_face_up and target_card.get("face_down", False):
        return EffectResult(
            cancelled=True,
            log_events=[
                {
                    "type": "EFFECT_INVALID_TARGET",
                    "reason": "TARGET_MUST_BE_FACE_UP",
                    "card_code": source_card.get("card_code"),
                    "card_instance_id": target_card.get("instance_id"),
                }
            ],
        )

    hp_before = target_card.get("hp", 0)

    # Spend charges
    source_card["hero_charges"] = current_charges - charge_cost

    # Destroy target
    target_card["hp"] = 0
    destroyed = [(target_player_index, target_zone_index)]

    log_events = [
        {
            "type": "EFFECT_HERO_SPEND_CHARGE",
            "spent": charge_cost,
            "remaining": source_card.get("hero_charges", 0),
        },
        {
            "type": "EFFECT_DESTROY_MONSTER",
            "player_index": target_player_index,
            "zone_index": target_zone_index,
            "card_instance_id": target_card.get("instance_id"),
            "hp_before": hp_before,
            "reason": "SOUL_REND",
        },
    ]

    # Conditional buff to lowest-HP ally
    if hp_before > hp_threshold and buff_amount > 0:
        lowest = _find_lowest_hp_monster(ctx.game_state, ctx.source_player)
        if lowest:
            ally_zone_idx, ally_card = lowest
            before_hp = ally_card.get("hp", 0)
            before_max_hp = ally_card.get("max_hp") or before_hp
            ally_card["hp"] = before_hp + buff_amount
            ally_card["max_hp"] = before_max_hp + buff_amount
            log_events.append(
                {
                    "type": "EFFECT_BUFF_MONSTER",
                    "player_index": ctx.source_player,
                    "zone_index": ally_zone_idx,
                    "hp_before": before_hp,
                    "hp_after": ally_card["hp"],
                    "max_hp_before": before_max_hp,
                    "max_hp_after": ally_card["max_hp"],
                    "card_instance_id": ally_card.get("instance_id"),
                    "reason": "SOUL_REND_BUFF",
                }
            )

    return EffectResult(
        log_events=log_events,
        destroyed_monsters=destroyed,
    )

def handle_spell_buff_monster(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    # Support both naming conventions
    atk_inc = int(params.get("atk_increase") or params.get("amount_atk") or params.get("atk_delta", 0))
    hp_inc = int(params.get("hp_increase") or params.get("amount_hp") or params.get("hp_delta", 0))
    
    # Check if this should target all monsters
    target_all = params.get("target_all", False) or params.get("target") == "ALL_MONSTERS"
    target_self = params.get("target") == "SELF_MONSTERS" or params.get("target") == "OWN_MONSTERS"
    
    result = EffectResult()
    game_state = ctx.game_state
    players = game_state.get("players", {})
    
    if target_all or target_self:
        # Buff all monsters on the caster's side (or both sides if target_all)
        target_players = [ctx.source_player] if target_self else [1, 2]
        
        for p_idx in target_players:
            pkey = str(p_idx)
            p_state = players.get(pkey)
            if not p_state:
                continue
            
            monster_zones = p_state.get("monster_zones") or []
            for zone_idx, card in enumerate(monster_zones):
                if card is None:
                    continue
                
                before_atk = card.get("atk", 0)
                before_hp = card.get("hp", 0)
                before_max_hp = card.get("max_hp") or before_hp
                
                card["atk"] = before_atk + atk_inc
                new_hp = before_hp + hp_inc
                new_max_hp = before_max_hp + hp_inc
                card["hp"] = _clamp_hp(new_hp, new_max_hp)
                card["max_hp"] = new_max_hp
                
                result.log_events.append({
                    "type": "EFFECT_BUFF_MONSTER",
                    "player_index": p_idx,
                    "zone_index": zone_idx,
                    "atk_before": before_atk,
                    "atk_after": card["atk"],
                    "hp_before": before_hp,
                    "hp_after": card["hp"],
                    "max_hp_before": before_max_hp,
                    "max_hp_after": new_max_hp,
                    "card_instance_id": card.get("instance_id"),
                })
    else:
        # Single target mode
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
        
        player_index, zone_index, card = ref
        
        # Ensure we're only buffing friendly monsters (not enemy monsters)
        if player_index != ctx.source_player:
            return EffectResult(
                log_events=[
                    {
                        "type": "EFFECT_INVALID_TARGET",
                        "reason": "CANNOT_BUFF_ENEMY_MONSTER",
                        "card_code": ctx.source_card.get("card_code"),
                    }
                ]
            )
        
        before_atk = card.get("atk", 0)
        before_hp = card.get("hp", 0)
        before_max_hp = card.get("max_hp") or before_hp
        
        card["atk"] = before_atk + atk_inc
        new_hp = before_hp + hp_inc
        new_max_hp = before_max_hp + hp_inc
        card["hp"] = _clamp_hp(new_hp, new_max_hp)
        card["max_hp"] = new_max_hp
        
        result.log_events.append({
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
        })
    
    return result


def handle_spell_haste(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    """
    Grants haste to a monster, allowing it to attack immediately.
    Can be used to:
    - Allow a newly summoned monster to attack this turn
    - Allow a monster that just attacked to attack again
    Also flips the monster face-up if it was face-down, since face-down monsters cannot attack.
    """
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
    
    player_index, zone_index, card = ref
    
    # Flip face-up if face-down (face-down monsters cannot attack)
    if card.get("face_down", False):
        card["face_down"] = False
    
    # Set can_attack to True
    card["can_attack"] = True
    
    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_HASTE",
                "player_index": player_index,
                "zone_index": zone_index,
                "card_instance_id": card.get("instance_id"),
                "monster_name": card.get("name"),
            }
        ]
    )


def handle_hero_active_damage(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    """
    Hero active ability that deals damage to a target monster.
    Used for Flamecaller's 100 damage ability.
    Always applies overflow damage to the player (like a fireball spell).
    """
    amount = int(params.get("amount") or params.get("damage", 0))
    if amount <= 0:
        return EffectResult()
    
    # Target monster if provided; otherwise target player if supplied.
    ref = _get_monster_ref_from_targets(ctx)
    if ref:
        # Use _apply_damage_to_monster to get proper destruction tracking and log events
        result = _apply_damage_to_monster(ctx, amount)
        
        # Always apply overflow damage (hero abilities are like fireballs)
        # Get the monster's HP before damage from the log event
        hp_before = None
        if result.log_events:
            for event in result.log_events:
                if event.get("type") == "EFFECT_DAMAGE_MONSTER":
                    hp_before = event.get("hp_before", 0)
                    break
        
        if hp_before is not None:
            # Calculate overflow: excess damage beyond what was needed to kill the monster
            overflow_amount = max(0, amount - hp_before)
            
            if overflow_amount > 0:
                # Get the target player (the controller of the monster that was damaged)
                target_player_index = ctx.targets.get("player")
                if not isinstance(target_player_index, int):
                    # If not specified, get it from the monster that was damaged
                    if result.log_events:
                        for event in result.log_events:
                            if event.get("type") == "EFFECT_DAMAGE_MONSTER":
                                target_player_index = event.get("player_index")
                                break
                
                if isinstance(target_player_index, int):
                    overflow_res = _apply_damage_to_player(
                        ctx.game_state, target_player_index, overflow_amount
                    )
                    _merge_effect_results(result, overflow_res)
                    
                    # Update the log event to include overflow info
                    for event in result.log_events:
                        if event.get("type") == "EFFECT_DAMAGE_MONSTER":
                            event["overflow_to_player"] = overflow_amount
                            break
        
        return result
    
    # If no monster target, try player target
    player_target = ctx.targets.get("player")
    if isinstance(player_target, int):
        return _apply_damage_to_player(ctx.game_state, player_target, amount)
    
    # No valid target
    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_NO_TARGET",
                "reason": "NO_MONSTER_OR_PLAYER_TARGET",
                "card_code": ctx.source_card.get("card_code"),
            }
        ]
    )


def handle_hero_active_freeze(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    """
    Hero active ability that freezes a monster (cannot attack for one round),
    then grants immunity to statuses for one round to prevent freeze spam.
    Used for Frost Warden's ability.
    
    Rotation:
    - Freeze applied: Monster frozen for 1 round (2 turns = until end of affected player's next turn)
    - When freeze expires: Status Immune applied for 1 round (2 turns = until end of affected player's next turn)
    """
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
    
    player_index, zone_index, card = ref
    
    # Apply freeze status (1 round = 2 turns = until end of affected player's next turn)
    statuses = card.get("statuses") or []
    statuses.append({
        "code": "FROZEN",
        "duration_type": "FIXED_TURNS",
        "duration_value": 2,  # 1 round = 2 turns
        "on_expire": "STATUS_IMMUNE",  # When freeze expires, apply status immunity
    })
    
    card["statuses"] = statuses
    card["can_attack"] = False  # Freeze prevents attack
    
    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_FREEZE_MONSTER",
                "player_index": player_index,
                "zone_index": zone_index,
                "card_instance_id": card.get("instance_id"),
                "monster_name": card.get("name"),
            }
        ]
    )


def handle_spell_cleanse_monster(
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

    player_index, zone_index, card = ref
    before_statuses = list(card.get("statuses") or [])
    card["statuses"] = []

    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_CLEANSE_MONSTER",
                "player_index": player_index,
                "zone_index": zone_index,
                "removed_statuses": before_statuses,
                "card_instance_id": card.get("instance_id"),
            }
        ]
    )


# --- Trap / reactive keywords ---------------------------------------------------


def handle_spell_counter_spell(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    """
    Counter spell: mark the chain as cancelled.
    By default, reflects the spell back to the caster's side unless reflect_spell is False.

    The action layer should:
      1. Resolve the trap that uses SPELL_COUNTER_SPELL or TRAP_COUNTER_SPELL.
      2. If the returned EffectResult.cancelled is True, do NOT apply the
         original spell's effects and instead log that it was countered.
      3. If reflect_spell is True (default), the spell should be reflected back to the caster.
    """
    # Default: only counter. Reflect only if explicitly enabled.
    reflect_spell = params.get("reflect_spell")
    if reflect_spell is None and "reflect" in params:
        reflect_spell = params.get("reflect")
    reflect_spell = bool(reflect_spell)
    
    result = EffectResult(
        cancelled=True,
        log_events=[
            {
                "type": "EFFECT_COUNTER_AND_REFLECT_SPELL" if reflect_spell else "EFFECT_COUNTER_SPELL",
                "trap_card_instance_id": ctx.source_card.get("instance_id"),
                "reflect_spell": reflect_spell,
            }
        ],
    )
    
    return result


def handle_trap_reflect_damage(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    """
    Reflects some percentage of incoming damage back to the attacker.

    The action layer must provide a trigger_event like:
      {
        "type": "ATTACK_MONSTER" / "ATTACK_DIRECT" / "SPELL_DAMAGE",
        "amount": <int>,
        "attacking_player": <int>,
        "defending_player": <int>,
        ...
      }
    """
    trigger = ctx.trigger_event or {}
    raw_amount = int(trigger.get("amount", 0))
    pct = int(params.get("percentage", 100))
    reflected = max(0, raw_amount * pct // 100)

    attacking_player = trigger.get("attacking_player")
    if not isinstance(attacking_player, int) or reflected <= 0:
        return EffectResult()

    return _apply_damage_to_player(ctx.game_state, attacking_player, reflected)


def handle_trap_apply_status(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    status_code = params.get("status_code")
    duration_type = params.get("duration_type", "PERMANENT")
    duration_value = params.get("duration_value")
    return _apply_status_to_monster(ctx, status_code, duration_type, duration_value)


def handle_spell_reflect_incoming_status(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    """
    For now this is just a log + hint to the action layer.

    The idea:
      - A spell tries to apply a status to one of your monsters.
      - You have a trap with this keyword.
      - The engine decides which monster on the opponent's board should
        receive the reflected status and populates ctx.targets["monster"]
        accordingly before calling this handler.
    """
    # We rely on the action layer to have already chosen the reflected target
    # and copied the original status parameters into `params`.
    status_code = params.get("status_code")
    duration_type = params.get("duration_type", "PERMANENT")
    duration_value = params.get("duration_value")

    result = _apply_status_to_monster(ctx, status_code, duration_type, duration_value)
    for evt in result.log_events:
        evt["type"] = "EFFECT_STATUS_REFLECTED"
    return result


def handle_spell_duplicate_incoming_status(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    """
    Similar to reflect, but the original target still gets the status and we
    also apply it to another target, chosen by the action layer.

    The action layer should:
      - Apply the original status using SPELL_APPLY_STATUS.
      - Then call this handler with ctx.targets pointing at the copy target
        and `params` containing the same status fields.
    """
    status_code = params.get("status_code")
    duration_type = params.get("duration_type", "PERMANENT")
    duration_value = params.get("duration_value")

    result = _apply_status_to_monster(ctx, status_code, duration_type, duration_value)
    for evt in result.log_events:
        evt["type"] = "EFFECT_STATUS_DUPLICATED"
    return result


def handle_trap_negate_attack(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    """
    Negates an attack and optionally reflects damage back to the attacker.
    
    The action layer should:
      - Call this when a trap with ON_ATTACK_DECLARED is triggered.
      - The trigger_event should contain attacker_instance_id, attacker_atk, etc.
      - This handler will cancel the attack and optionally deal damage to the attacker.
    """
    trigger_event = ctx.trigger_event or {}
    attacker_instance_id = trigger_event.get("attacker_instance_id")
    
    if not attacker_instance_id:
        return EffectResult(
            log_events=[
                {
                    "type": "EFFECT_NO_TARGET",
                    "reason": "NO_ATTACKER",
                    "card_code": ctx.source_card.get("card_code"),
                }
            ]
        )
    
    # Find attacker
    from app.engine.game_state_helpers import find_monster_by_instance_id
    found = find_monster_by_instance_id(ctx.game_state, attacker_instance_id)
    if not found:
        return EffectResult(
            log_events=[
                {
                    "type": "EFFECT_NO_TARGET",
                    "reason": "ATTACKER_NOT_FOUND",
                    "card_code": ctx.source_card.get("card_code"),
                }
            ]
        )
    
    attacker = found["card"]
    attacker_player_index = found["player_index"]
    attacker_zone_index = found["zone_index"]
    
    # Get attacker's ATK for reflection
    attacker_atk = trigger_event.get("attacker_atk") or attacker.get("atk", 0)
    
    # Check if we should reflect damage (default: yes, deal attacker's ATK as damage)
    reflect_damage = params.get("reflect_damage", True)
    damage_amount = params.get("damage_amount")
    
    destroyed: List[Tuple[int, int]] = []

    if reflect_damage:
        # Default to dealing attacker's ATK as damage, or use specified amount
        damage_to_deal = int(damage_amount) if damage_amount is not None else int(attacker_atk)
        
        hp_before = attacker.get("hp", 0)
        hp_after = max(0, hp_before - damage_to_deal)
        attacker["hp"] = hp_after

        if hp_after <= 0:
            destroyed.append((attacker_player_index, attacker_zone_index))
        
        return EffectResult(
            cancelled=True,  # Cancel the attack
            destroyed_monsters=destroyed,
            log_events=[
                {
                    "type": "EFFECT_NEGATE_ATTACK",
                    "trap_card_instance_id": ctx.source_card.get("instance_id"),
                    "attacker_instance_id": attacker_instance_id,
                },
                {
                    "type": "EFFECT_DAMAGE_MONSTER",
                    "player_index": attacker_player_index,
                    "zone_index": attacker_zone_index,
                    "amount": damage_to_deal,
                    "hp_before": hp_before,
                    "hp_after": hp_after,
                    "card_instance_id": attacker_instance_id,
                }
            ]
        )
    else:
        # Just negate, no damage
        return EffectResult(
            cancelled=True,
            destroyed_monsters=destroyed,
            log_events=[
                {
                    "type": "EFFECT_NEGATE_ATTACK",
                    "trap_card_instance_id": ctx.source_card.get("instance_id"),
                    "attacker_instance_id": attacker_instance_id,
                }
            ]
        )


def handle_trap_prevent_destruction(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    """
    Prevents a monster from being destroyed by setting its HP to a minimum value (default 1).
    
    The action layer should:
      - Call this when a trap with ON_ALLY_MONSTER_WOULD_BE_DESTROYED is triggered.
      - The trigger_event should contain monster_instance_id, player_index, zone_index.
      - This handler will set the monster's HP to prevent_destruction_hp (default 1).
    """
    # Get target monster from trigger_event or targets
    trigger_event = ctx.trigger_event or {}
    monster_instance_id = trigger_event.get("monster_instance_id")
    
    # Try to find monster from targets first
    ref = _get_monster_ref_from_targets(ctx)
    if not ref and monster_instance_id:
        # Fallback: find by instance_id from trigger_event
        from app.engine.game_state_helpers import find_monster_by_instance_id
        found = find_monster_by_instance_id(ctx.game_state, monster_instance_id)
        if found:
            ref = (found["player_index"], found["zone_index"], found["card"])
    
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
    
    player_index, zone_index, card = ref
    
    # Get HP to set (default 1)
    prevent_destruction_hp = int(params.get("prevent_destruction_hp", 1))
    
    hp_before = card.get("hp", 0)
    # If the monster would be destroyed (hp_before <= 0), set to prevent_destruction_hp.
    # If it's already above 0, leave it (trap triggers after combat when it hit 0).
    if hp_before <= 0:
        card["hp"] = prevent_destruction_hp
        hp_after = prevent_destruction_hp
    else:
        hp_after = hp_before
    
    return EffectResult(
        log_events=[
            {
                "type": "EFFECT_PREVENT_DESTRUCTION",
                "player_index": player_index,
                "zone_index": zone_index,
                "card_instance_id": card.get("instance_id"),
                "hp_before": hp_before,
                "hp_after": hp_after,
            }
        ]
    )


# --- Registry -------------------------------------------------------------------


KEYWORD_HANDLERS: Dict[str, KeywordHandler] = {
    # Spells – core
    "SPELL_DAMAGE_MONSTER": handle_spell_damage_monster,
    "SPELL_DAMAGE_PLAYER": handle_spell_damage_player,
    "SPELL_HEAL_MONSTER": handle_spell_heal_monster,
    "SPELL_HEAL_PLAYER": handle_spell_heal_player,
    "SPELL_APPLY_STATUS": handle_spell_apply_status,
    "SPELL_DRAW_CARDS": handle_spell_draw_cards,
    "SPELL_DRAW": handle_spell_draw_cards,  # Alias
    "SPELL_BUFF_MONSTER": handle_spell_buff_monster,
    "SPELL_CLEANSE_MONSTER": handle_spell_cleanse_monster,
    "SPELL_HASTE": handle_spell_haste,
    # Hero abilities
    "HERO_ACTIVE_DAMAGE": handle_hero_active_damage,
    "HERO_ACTIVE_FREEZE": handle_hero_active_freeze,
    "HERO_ACTIVE_SOUL_REND": handle_hero_active_soul_rend,
    # Reactive / traps
    "SPELL_COUNTER_SPELL": handle_spell_counter_spell,
    "TRAP_COUNTER_SPELL": handle_spell_counter_spell,  # Alias for trap counter spells
    "TRAP_NEGATE_ATTACK": handle_trap_negate_attack,
    "TRAP_REFLECT_DAMAGE": handle_trap_reflect_damage,
    "TRAP_APPLY_STATUS": handle_trap_apply_status,
    "TRAP_PREVENT_DESTRUCTION": handle_trap_prevent_destruction,
    "SPELL_REFLECT_INCOMING_STATUS": handle_spell_reflect_incoming_status,
    "SPELL_DUPLICATE_INCOMING_STATUS": handle_spell_duplicate_incoming_status,
}
