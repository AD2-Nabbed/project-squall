import random
from typing import Optional, Dict, Any

from app.db.supabase_client import supabase


def pick_random_npc_with_deck(npc_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns a single NPC row that has a deck_id.

    - If npc_id is provided, returns that specific NPC (or raises if not found).
    - If npc_id is None, picks a random NPC that has a non-null deck_id.
    """

    # Columns: id, display_name, deck_id
    columns = "id, display_name, deck_id"

    if npc_id:
        resp = (
            supabase.table("npcs")
            .select(columns)
            .eq("id", npc_id)
            .single()
            .execute()
        )
        npc = resp.data
        if not npc:
            raise RuntimeError(f"NPC with id {npc_id} not found")
        if not npc.get("deck_id"):
            raise RuntimeError(f"NPC {npc_id} has no deck_id assigned")

        # Normalize expected field name
        npc["name"] = npc["display_name"]
        return npc

    # Load all NPCs
    resp = supabase.table("npcs").select(columns).execute()
    rows = resp.data or []

    # Only NPCs with assigned decks
    valid_rows = [r for r in rows if r.get("deck_id")]

    if not valid_rows:
        raise RuntimeError("No NPCs with decks found in 'npcs' table")

    npc = random.choice(valid_rows)

    # Normalize expected field name
    npc["name"] = npc["display_name"]

    return npc
