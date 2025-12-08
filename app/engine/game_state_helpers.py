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
