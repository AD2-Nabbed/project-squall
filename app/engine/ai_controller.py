"""
AI Controller for NPC turns in PVE matches.

Simple rule-based AI that makes decisions based on game state.
"""
from typing import Dict, Any, List, Optional
import random


def get_ai_action(game_state: Dict[str, Any], ai_player_index: int) -> Optional[Dict[str, Any]]:
    """
    Determine the next action for an AI-controlled player.
    
    Returns a dict with action type and payload, or None to end turn.
    
    Priority order:
    1. Summon hero if possible (2 tributes available)
    2. Summon highest-star monster if possible (with tribute if needed)
    3. Play spell if available
    4. Set trap if available
    5. Attack with strongest monster
    6. End turn
    """
    player = game_state["players"].get(str(ai_player_index))
    if not player:
        print(f"AI: Player {ai_player_index} not found in game state")
        return {"action": "END_TURN"}
    
    # Check if it's AI's turn
    if game_state.get("current_player") != ai_player_index:
        print(f"AI: Not AI's turn. Current player: {game_state.get('current_player')}, AI: {ai_player_index}")
        return None
    
    # Check per-turn limits
    turn_state = game_state.get("turn_state", {})
    pkey = str(ai_player_index)
    current_turn = game_state.get("turn", 1)
    p_turn = turn_state.get(pkey, {"summons": 0, "spells_traps": 0, "hero_ability": 0, "turn": current_turn})
    
    # Reset if it's a new turn
    if p_turn.get("turn") != current_turn:
        p_turn = {"summons": 0, "spells_traps": 0, "hero_ability": 0, "turn": current_turn}
        turn_state[pkey] = p_turn
        game_state["turn_state"] = turn_state
    
    has_summoned = p_turn.get("summons", 0) >= 1
    has_played_spell_trap = p_turn.get("spells_traps", 0) >= 1
    has_used_hero_ability = p_turn.get("hero_ability", 0) >= 1
    
    hand = player.get("hand", [])
    monster_zones = player.get("monster_zones", [])
    spell_trap_zones = player.get("spell_trap_zones", [])
    hero = player.get("hero")
    
    print(f"AI Turn {current_turn} - Hand: {len(hand)} cards, Monsters on board: {sum(1 for m in monster_zones if m is not None)}, "
          f"Has summoned: {has_summoned}, Has played spell/trap: {has_played_spell_trap}, Has used hero ability: {has_used_hero_ability}")
    
    # 1. Summon hero if we have 2 monsters and hero in hand (only if haven't summoned yet)
    if not hero and not has_summoned:
        hero_card = next((c for c in hand if c.get("card_type") == "hero" or c.get("stars") == 6), None)
        if hero_card:
            available_tributes = [m for m in monster_zones if m is not None]
            if len(available_tributes) >= 2:
                print(f"AI: Summoning hero {hero_card.get('name', 'unknown')} with 2 tributes")
                return {
                    "action": "PLAY_MONSTER",
                    "play_monster": {
                        "card_instance_id": hero_card["instance_id"],
                        "zone_index": 0,  # Hero goes to hero zone, but zone_index still needed
                        "tribute_instance_ids": [t["instance_id"] for t in available_tributes[:2]],
                    }
                }
            else:
                print(f"AI: Hero in hand but only {len(available_tributes)} tributes available (need 2)")
    
    # 2. Summon highest-star monster we can afford (only if haven't summoned yet)
    if not has_summoned:
        monsters_in_hand = [c for c in hand if c.get("card_type") == "monster" and c.get("stars", 0) < 6]
        if monsters_in_hand:
            # Sort by stars (descending)
            monsters_in_hand.sort(key=lambda x: x.get("stars", 0), reverse=True)
            
            for monster in monsters_in_hand:
                stars = monster.get("stars", 0)
                empty_zone = next((i for i, m in enumerate(monster_zones) if m is None), None)
                
                if empty_zone is None:
                    print(f"AI: No empty monster zones available")
                    break  # No empty zones
                
                # Check tribute requirements
                if stars >= 4:
                    # Needs 1 tribute
                    available_tributes = [m for m in monster_zones if m is not None]
                    if len(available_tributes) >= 1:
                        print(f"AI: Summoning {monster.get('name', 'unknown')} ({stars} stars) with 1 tribute")
                        return {
                            "action": "PLAY_MONSTER",
                            "play_monster": {
                                "card_instance_id": monster["instance_id"],
                                "zone_index": empty_zone,
                                "tribute_instance_ids": [available_tributes[0]["instance_id"]],
                            }
                        }
                    else:
                        print(f"AI: {monster.get('name', 'unknown')} needs tribute but none available")
                        continue
                else:
                    # 1-3 stars, no tribute needed
                    print(f"AI: Summoning {monster.get('name', 'unknown')} ({stars} stars) - no tribute needed")
                    return {
                        "action": "PLAY_MONSTER",
                        "play_monster": {
                            "card_instance_id": monster["instance_id"],
                            "zone_index": empty_zone,
                            "tribute_instance_ids": [],
                        }
                    }
        else:
            print(f"AI: No monsters in hand to summon")
    
    # 3. Play spell if available (only if haven't played spell/trap yet)
    if not has_played_spell_trap:
        spells = [c for c in hand if c.get("card_type") == "spell"]
        # Try each spell until we find one we can play
        for spell in spells:
            # Check if spell needs a target
            effect_params = spell.get("effect_params") or {}
            if isinstance(effect_params, str):
                try:
                    import json
                    effect_params = json.loads(effect_params)
                except:
                    effect_params = {}
            
            effects = effect_params.get("effects", [])
            needs_target = False
            target_type = None  # "monster" or "player"
            
            for eff in effects:
                keyword = eff.get("keyword", "")
                target = eff.get("target", "")
                # Check keyword for monster/player targeting
                if keyword and ("MONSTER" in keyword.upper() or "DAMAGE_MONSTER" in keyword.upper() or "HEAL_MONSTER" in keyword.upper() or "BUFF_MONSTER" in keyword.upper()):
                    needs_target = True
                    target_type = "monster"
                    break
                elif keyword and ("PLAYER" in keyword.upper() or "DAMAGE_PLAYER" in keyword.upper() or "HEAL_PLAYER" in keyword.upper()):
                    needs_target = True
                    target_type = "player"
                    break
                # Also check target field
                elif target:
                    target_str = str(target).upper()
                    if "MONSTER" in target_str or "ENEMY_MONSTER" in target_str:
                        needs_target = True
                        target_type = "monster"
                        break
                    elif "PLAYER" in target_str or "ENEMY_PLAYER" in target_str:
                        needs_target = True
                        target_type = "player"
                        break
            
            # Select target if needed
            target_player_index = None
            target_monster_instance_id = None
            
            if needs_target and target_type == "monster":
                # Check if this is a buff/heal spell (should target friendly) or damage spell (should target enemy)
                is_buff_spell = any("BUFF" in eff.get("keyword", "").upper() or "HEAL" in eff.get("keyword", "").upper() for eff in effects)
                is_damage_spell = any("DAMAGE" in eff.get("keyword", "").upper() for eff in effects)
                
                if is_buff_spell:
                    # Buff/heal spells target friendly monsters
                    friendly_monsters = [m for m in monster_zones if m is not None]
                    if not friendly_monsters:
                        print(f"AI: No friendly monsters available for buff/heal spell {spell.get('name', 'unknown')}")
                        continue  # Try next spell
                    
                    # For heal spells, prefer damaged monsters
                    if is_buff_spell and any("HEAL" in eff.get("keyword", "").upper() for eff in effects):
                        damaged_monsters = [m for m in friendly_monsters if m.get("hp", 0) < m.get("max_hp", m.get("hp", 0))]
                        if damaged_monsters:
                            friendly_monsters = damaged_monsters
                    
                    target_monster = random.choice(friendly_monsters)
                    target_monster_instance_id = target_monster["instance_id"]
                    target_player_index = ai_player_index
                    print(f"AI: Selecting friendly target for {spell.get('name', 'spell')}: {target_monster.get('name', 'unknown')}")
                else:
                    # Damage spells target enemy monsters
                    enemy_player_index = 1 if ai_player_index == 2 else 2
                    enemy = game_state["players"].get(str(enemy_player_index))
                    if not enemy:
                        print(f"AI: Enemy player {enemy_player_index} not found, skipping spell {spell.get('name', 'unknown')}")
                        continue
                    
                    enemy_monsters = [m for m in enemy.get("monster_zones", []) if m is not None]
                    if not enemy_monsters:
                        print(f"AI: No enemy monsters available, skipping spell {spell.get('name', 'unknown')}")
                        continue  # Try next spell
                    
                    # Target a random enemy monster
                    target_monster = random.choice(enemy_monsters)
                    target_monster_instance_id = target_monster["instance_id"]
                    target_player_index = enemy_player_index
                    print(f"AI: Selecting enemy target for {spell.get('name', 'spell')}: {target_monster.get('name', 'unknown')}")
            elif needs_target and target_type == "player":
                # Target enemy player
                enemy_player_index = 1 if ai_player_index == 2 else 2
                target_player_index = enemy_player_index
            
            # Only play spell if we have a valid target (or no target needed)
            if not needs_target:
                # Spell doesn't need a target
                print(f"AI: Playing spell {spell.get('name', 'unknown')} - no target needed")
                return {
                    "action": "PLAY_SPELL",
                    "play_spell": {
                        "card_instance_id": spell["instance_id"],
                        "target_player_index": None,
                        "target_monster_instance_id": None,
                    }
                }
            elif needs_target and (target_player_index is not None or target_monster_instance_id is not None):
                # Spell needs target and we have one
                print(f"AI: Playing spell {spell.get('name', 'unknown')} with target: player={target_player_index}, monster={target_monster_instance_id}")
                return {
                    "action": "PLAY_SPELL",
                    "play_spell": {
                        "card_instance_id": spell["instance_id"],
                        "target_player_index": target_player_index,
                        "target_monster_instance_id": target_monster_instance_id,
                    }
                }
            else:
                # Spell needs target but we don't have one - try next spell
                print(f"AI: Spell {spell.get('name', 'unknown')} needs target but none available, trying next spell")
                continue
    
    # 4. Set trap if available and have empty zone (only if haven't played spell/trap yet)
    if not has_played_spell_trap:
        traps = [c for c in hand if c.get("card_type") == "trap"]
        if traps:
            empty_trap_zone = next((i for i, s in enumerate(spell_trap_zones) if s is None), None)
            if empty_trap_zone is not None:
                trap = random.choice(traps)
                return {
                    "action": "PLAY_TRAP",
                    "play_trap": {
                        "card_instance_id": trap["instance_id"],
                        "zone_index": empty_trap_zone,
                    }
                }
    
    # 5. Use hero ability if available (only if haven't used it yet)
    if hero and not has_used_hero_ability:
        # Check if hero has active ability
        hero_active = hero.get("effect_params", {}).get("active") or {}
        if hero_active.get("effect_tags"):
            return {
                "action": "ACTIVATE_HERO_ABILITY",
                "activate_hero_ability": {
                    "target_player_index": None,
                    "target_monster_instance_id": None,
                }
            }
    
    # 6. Attack with strongest available monster
    attackable_monsters = [
        (i, m) for i, m in enumerate(monster_zones)
        if m is not None and not m.get("face_down", True) and m.get("can_attack", False)
    ]
    
    if attackable_monsters:
        # Sort by ATK (descending)
        attackable_monsters.sort(key=lambda x: x[1].get("atk", 0), reverse=True)
        zone_idx, attacker = attackable_monsters[0]
        
        # Check opponent's monsters
        opponent_index = 1 if ai_player_index == 2 else 2
        opponent = game_state["players"].get(str(opponent_index))
        if opponent:
            opponent_monsters = [m for m in opponent.get("monster_zones", []) if m is not None]
            
            if opponent_monsters:
                # Attack weakest opponent monster
                opponent_monsters.sort(key=lambda x: x.get("hp", 0))
                target = opponent_monsters[0]
                print(f"AI: Attacking {target.get('name', 'monster')} with {attacker.get('name', 'monster')}")
                return {
                    "action": "ATTACK_MONSTER",
                    "attack_monster": {
                        "attacker_instance_id": attacker["instance_id"],
                        "defender_instance_id": target["instance_id"],
                    }
                }
            else:
                # Direct attack
                print(f"AI: Direct attacking player with {attacker.get('name', 'monster')}")
                return {
                    "action": "ATTACK_PLAYER",
                    "attack_player": {
                        "attacker_instance_id": attacker["instance_id"],
                    }
                }
    
    # 7. No more actions available - end turn
    print(f"AI: No more actions available. Ending turn. (summoned: {has_summoned}, spell/trap: {has_played_spell_trap}, hero ability: {has_used_hero_ability}, attackable: {len(attackable_monsters)})")
    return {"action": "END_TURN"}


def process_ai_turn(game_state: Dict[str, Any], ai_player_index: int, max_actions: int = 10) -> Dict[str, Any]:
    """
    Process a full AI turn by making multiple actions until the AI ends its turn.
    
    Returns the updated game_state after AI actions.
    """
    action_count = 0
    
    while action_count < max_actions:
        # Check if it's still AI's turn
        if game_state.get("current_player") != ai_player_index:
            break
        
        # Get AI action
        ai_action = get_ai_action(game_state, ai_player_index)
        if not ai_action or ai_action.get("action") == "END_TURN":
            # AI wants to end turn - we'll handle this in the main action handler
            break
        
        # Execute the action (this would normally call battle_action, but we'll simulate)
        # For now, return the action to be executed by the main handler
        action_count += 1
    
    return game_state

