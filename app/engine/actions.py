from __future__ import annotations

from typing import Optional, List, Dict, Any

from app.engine.models import (
    GameState,
    PlayerState,
    CardInstance,
    Phase,
    MatchStatus,
)


def _other_player_index(player_index: int) -> int:
    return 2 if player_index == 1 else 1


# ---------------------------------------------------------------------------
# Draw logic
# ---------------------------------------------------------------------------

def draw_cards(player: PlayerState, amount: int) -> None:
    """
    Draw up to `amount` cards from the player's deck into their hand.
    Stops early if the deck is empty.
    """
    for _ in range(amount):
        if not player.deck:
            break
        player.hand.append(player.deck.pop(0))


# ---------------------------------------------------------------------------
# Turn flow
# ---------------------------------------------------------------------------

def start_new_turn(game_state: GameState, next_player_index: int) -> None:
    """
    Advance the GameState to the next player's turn.

    - Increments turn counter.
    - Sets current_player and phase to MAIN.
    - Draws 2 cards for the active player.
    - Resets can_attack for that player's existing monsters.
    """
    game_state.turn += 1
    game_state.current_player = next_player_index
    game_state.phase = Phase.MAIN

    active_player = game_state.players[next_player_index]

    # Draw 2 cards each turn (your rule)
    draw_cards(active_player, 2)

    # Reset attacks for monsters that are already on the field
    for card in active_player.monster_zones:
        if card is not None:
            card.can_attack = True


def apply_end_turn(game_state: GameState, from_player_index: int) -> None:
    """
    Handles END_TURN:
      - Appends a log entry.
      - Switches to the other player.
      - Starts the new turn (which draws 2 cards and refreshes attacks).
    """
    to_player_index = _other_player_index(from_player_index)

    game_state.log.append(
        {
            "type": "END_TURN",
            "from_player": from_player_index,
            "to_player": to_player_index,
            "turn": game_state.turn + 1,  # because we're about to increment
            "phase": "main",
        }
    )

    start_new_turn(game_state, to_player_index)


# ---------------------------------------------------------------------------
# Summoning (normal + tribute)
# ---------------------------------------------------------------------------

def _remove_tributes_and_summon(
    game_state: GameState,
    player_index: int,
    card_from_hand: CardInstance,
    target_zone_index: int,
    tribute_zone_indices: List[int],
) -> None:
    """
    Shared helper for PLAY_MONSTER.

    - Removes tribute monsters from the board and moves them to the graveyard.
    - Places the new monster in the target zone.
    - Sets can_attack depending on whether this was a tribute summon.
      * Normal summon  -> can_attack = False
      * Tribute summon -> can_attack = True
    """
    player = game_state.players[player_index]

    # Resolve tributes first
    is_tribute_summon = len(tribute_zone_indices) > 0

    # Sort descending so we can safely pop by index if needed
    for zone_idx in sorted(tribute_zone_indices, reverse=True):
        if zone_idx < 0 or zone_idx >= len(player.monster_zones):
            raise ValueError(f"Invalid tribute zone index: {zone_idx}")

        tribute_card = player.monster_zones[zone_idx]
        if tribute_card is None:
            raise ValueError(f"No card in tribute zone {zone_idx}")

        # Move tribute to graveyard
        player.graveyard.append(tribute_card)
        player.monster_zones[zone_idx] = None

    # Place the new monster
    if player.monster_zones[target_zone_index] is not None:
        raise ValueError("Target monster zone is already occupied.")

    # Summoning sickness rules:
    #   - Normal summon  -> cannot attack this turn
    #   - Tribute summon -> can attack immediately
    if is_tribute_summon:
        card_from_hand.can_attack = True
    else:
        card_from_hand.can_attack = False

    card_from_hand.face_down = False  # we are treating all as face-up summons for now

    player.monster_zones[target_zone_index] = card_from_hand


def apply_play_monster(
    game_state: GameState,
    player_index: int,
    hand_instance_id: str,
    target_zone_index: int,
    tribute_zone_indices: Optional[List[int]] = None,
) -> None:
    """
    PLAY_MONSTER action.

    - Finds the card in the player's hand by instance_id.
    - (Optional) uses monsters in `tribute_zone_indices` as tributes.
    - Places the card into `target_zone_index`.
    - Logs the event.
    """
    tribute_zone_indices = tribute_zone_indices or []

    player = game_state.players[player_index]

    # Find the card in hand
    card_idx_in_hand = None
    for i, c in enumerate(player.hand):
        if c.instance_id == hand_instance_id:
            card_idx_in_hand = i
            break

    if card_idx_in_hand is None:
        raise ValueError("Card with given instance_id not found in hand.")

    card = player.hand.pop(card_idx_in_hand)

    _remove_tributes_and_summon(
        game_state=game_state,
        player_index=player_index,
        card_from_hand=card,
        target_zone_index=target_zone_index,
        tribute_zone_indices=tribute_zone_indices,
    )

    game_state.log.append(
        {
            "type": "PLAY_MONSTER",
            "player": player_index,
            "zone": target_zone_index,
            "card_name": card.name,
            "card_instance_id": card.instance_id,
            "stars": card.stars,
            "tributes": tribute_zone_indices,
        }
    )


# ---------------------------------------------------------------------------
# Combat (with symmetric spillover)
# ---------------------------------------------------------------------------

def _check_monster_present(player: PlayerState, zone_index: int) -> CardInstance:
    if zone_index < 0 or zone_index >= len(player.monster_zones):
        raise ValueError("Invalid monster zone index.")

    card = player.monster_zones[zone_index]
    if card is None:
        raise ValueError("No monster in the specified zone.")

    return card


def resolve_attack_monster(
    game_state: GameState,
    attacking_player_index: int,
    attacker_zone_index: int,
    defender_zone_index: int,
) -> None:
    """
    Resolves monster vs monster combat with:
      - Simultaneous damage
      - Spillover to each player's HP

    Rules:
      attacker_hp_before = attacker.hp
      defender_hp_before = defender.hp

      defender.hp -= attacker.atk
      attacker.hp -= defender.atk

      overflow_to_defender_player = max(0, attacker.atk - defender_hp_before)
      overflow_to_attacker_player = max(0, defender.atk - attacker_hp_before)

      Player HP is reduced by those overflow amounts.
    """
    attacker_player = game_state.players[attacking_player_index]
    defending_player_index = _other_player_index(attacking_player_index)
    defender_player = game_state.players[defending_player_index]

    attacker_card = _check_monster_present(attacker_player, attacker_zone_index)
    defender_card = _check_monster_present(defender_player, defender_zone_index)

    if not attacker_card.can_attack:
        raise ValueError("This monster cannot attack this turn.")

    # Snapshot before combat
    attacker_hp_before = attacker_card.hp
    defender_hp_before = defender_card.hp
    attacker_atk = attacker_card.atk
    defender_atk = defender_card.atk

    # Simultaneous damage to monsters
    defender_card.hp = max(0, defender_hp_before - attacker_atk)
    attacker_card.hp = max(0, attacker_hp_before - defender_atk)

    # Spillover damage to players
    overflow_to_defender = max(0, attacker_atk - defender_hp_before)
    overflow_to_attacker = max(0, defender_atk - attacker_hp_before)

    defender_player.hp = max(0, defender_player.hp - overflow_to_defender)
    attacker_player.hp = max(0, attacker_player.hp - overflow_to_attacker)

    # Track whether they died
    defender_died = defender_card.hp <= 0
    attacker_died = attacker_card.hp <= 0

    # Move dead monsters to graveyard
    if defender_died:
        defender_player.graveyard.append(defender_card)
        defender_player.monster_zones[defender_zone_index] = None

    if attacker_died:
        attacker_player.graveyard.append(attacker_card)
        attacker_player.monster_zones[attacker_zone_index] = None
    else:
        # Attacker used its attack for this turn
        attacker_card.can_attack = False

    # Log the attack result
    game_state.log.append(
        {
            "type": "ATTACK_MONSTER",
            "attacking_player": attacking_player_index,
            "defending_player": defending_player_index,
            "attacker_zone_index": attacker_zone_index,
            "defender_zone_index": defender_zone_index,
            "attacker_instance_id": attacker_card.instance_id,
            "defender_instance_id": defender_card.instance_id,
            "attacker_atk": attacker_atk,
            "defender_atk": defender_atk,
            "attacker_hp_before": attacker_hp_before,
            "defender_hp_before": defender_hp_before,
            "attacker_hp_after": attacker_card.hp if not attacker_died else 0,
            "defender_hp_after": defender_card.hp if not defender_died else 0,
            "overflow_to_attacker_player": overflow_to_attacker,
            "overflow_to_defender_player": overflow_to_defender,
        }
    )

    _check_for_lethal(game_state)


def resolve_direct_attack(
    game_state: GameState,
    attacking_player_index: int,
    attacker_zone_index: int,
) -> None:
    """
    Resolves a direct attack on the opposing player's HP.

    Only allowed if the defending player controls no monsters.
    No 'overflow' concept here; the monster's ATK is just direct HP damage.
    """
    attacker_player = game_state.players[attacking_player_index]
    defending_player_index = _other_player_index(attacking_player_index)
    defender_player = game_state.players[defending_player_index]

    # Cannot direct attack if defender has any monsters
    if any(defender_player.monster_zones):
        raise ValueError("Cannot direct attack while the opponent controls monsters.")

    attacker_card = _check_monster_present(attacker_player, attacker_zone_index)

    if not attacker_card.can_attack:
        raise ValueError("This monster cannot attack this turn.")

    damage = attacker_card.atk
    defender_player.hp = max(0, defender_player.hp - damage)

    attacker_card.can_attack = False

    game_state.log.append(
        {
            "type": "DIRECT_ATTACK",
            "attacking_player": attacking_player_index,
            "defending_player": defending_player_index,
            "attacker_zone_index": attacker_zone_index,
            "attacker_instance_id": attacker_card.instance_id,
            "damage": damage,
        }
    )

    _check_for_lethal(game_state)


# ---------------------------------------------------------------------------
# Win condition
# ---------------------------------------------------------------------------

def _check_for_lethal(game_state: GameState) -> None:
    """
    Checks if either player's HP has reached 0 or below and sets
    game_state.status / winner accordingly.

    - If both reach 0 in the same combat, it's a draw (winner = None).
    """
    p1 = game_state.players[1]
    p2 = game_state.players[2]

    p1_dead = p1.hp <= 0
    p2_dead = p2.hp <= 0

    if not p1_dead and not p2_dead:
        return

    game_state.status = MatchStatus.COMPLETED

    if p1_dead and p2_dead:
        game_state.winner = None  # draw
    elif p2_dead:
        game_state.winner = 1
    elif p1_dead:
        game_state.winner = 2
