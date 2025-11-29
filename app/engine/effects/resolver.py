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

        handler = KEYWORD_HANDLERS.get(keyword)
        if not handler:
            # Unknown keyword – safe no-op, but log it for debugging.
            result.log_events.append(
                {
                    "type": "EFFECT_UNKNOWN_KEYWORD",
                    "keyword": keyword,
                    "card_code": ctx.source_card.get("card_code"),
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

    status_entry = {
        "code": status_code,
        "duration_type": duration_type,  # e.g. "UNTIL_CONTROLLER_NEXT_TURN", "FIXED_TURNS", "PERMANENT"
    }
    if duration_value is not None:
        status_entry["duration_value"] = duration_value

    statuses = card.get("statuses")
    if statuses is None:
        statuses = []
        card["statuses"] = statuses

    statuses.append(status_entry)

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

    # Optional overflow to the defending player if the monster died and there
    # was "excess" damage. The action layer should set ctx.targets["player"]
    # appropriately for this spell if you want overflow.
    if overflow_to_player and result.destroyed_monsters:
        overflow_amount = amount  # simple model: all damage overflows on kill
        target_player_index = ctx.targets.get("player")
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
    status_code = params.get("status_code")
    duration_type = params.get("duration_type", "PERMANENT")
    duration_value = params.get("duration_value")  # optional int
    return _apply_status_to_monster(ctx, status_code, duration_type, duration_value)


def handle_spell_draw_cards(
    ctx: EffectContext, params: Dict[str, Any]
) -> EffectResult:
    amount = int(params.get("amount", 0))
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

    atk_inc = int(params.get("atk_increase", 0))
    hp_inc = int(params.get("hp_increase", 0))

    player_index, zone_index, card = ref
    before_atk = card.get("atk", 0)
    before_hp = card.get("hp", 0)
    before_max_hp = card.get("max_hp")

    card["atk"] = before_atk + atk_inc
    new_hp = before_hp + hp_inc
    card["hp"] = _clamp_hp(new_hp, before_max_hp)

    # Optionally, you could also increase max_hp here if desired.

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
                "card_instance_id": card.get("instance_id"),
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
    Simple model: mark the chain as cancelled.

    The action layer should:
      1. Resolve the trap that uses SPELL_COUNTER_SPELL.
      2. If the returned EffectResult.cancelled is True, do NOT apply the
         original spell's effects and instead log that it was countered.
    """
    return EffectResult(
        cancelled=True,
        log_events=[
            {
                "type": "EFFECT_COUNTER_SPELL",
                "trap_card_instance_id": ctx.source_card.get("instance_id"),
            }
        ],
    )


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


# --- Registry -------------------------------------------------------------------


KEYWORD_HANDLERS: Dict[str, KeywordHandler] = {
    # Spells – core
    "SPELL_DAMAGE_MONSTER": handle_spell_damage_monster,
    "SPELL_DAMAGE_PLAYER": handle_spell_damage_player,
    "SPELL_HEAL_MONSTER": handle_spell_heal_monster,
    "SPELL_HEAL_PLAYER": handle_spell_heal_player,
    "SPELL_APPLY_STATUS": handle_spell_apply_status,
    "SPELL_DRAW_CARDS": handle_spell_draw_cards,
    "SPELL_BUFF_MONSTER": handle_spell_buff_monster,
    "SPELL_CLEANSE_MONSTER": handle_spell_cleanse_monster,
    # Reactive / traps
    "SPELL_COUNTER_SPELL": handle_spell_counter_spell,
    "TRAP_REFLECT_DAMAGE": handle_trap_reflect_damage,
    "TRAP_APPLY_STATUS": handle_trap_apply_status,
    "SPELL_REFLECT_INCOMING_STATUS": handle_spell_reflect_incoming_status,
    "SPELL_DUPLICATE_INCOMING_STATUS": handle_spell_duplicate_incoming_status,
}
