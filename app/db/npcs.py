from __future__ import annotations

import random
from typing import Tuple, List, Dict

from app.db.supabase_client import supabase
from app.db.decks import load_deck_card_defs


def load_npc_with_deck(npc_id: str) -> Tuple[Dict, List[Dict]]:
    """
    Load a specific NPC (id, display_name, deck_id) and its deck defs.
    """
    resp = (
        supabase.table("npcs")
        .select("id, display_name, deck_id")
        .eq("id", npc_id)
        .single()
        .execute()
    )
    npc = resp.data
    if not npc:
        raise ValueError(f"NPC {npc_id} not found")

    deck_defs = load_deck_card_defs(npc["deck_id"])
    return npc, deck_defs


def pick_random_npc_with_deck() -> Tuple[Dict, List[Dict]]:
    """
    Load all NPCs, choose one at random in Python, and return npc + deck defs.
    Fine for small NPC counts; later we can optimize with SQL/RPC if needed.
    """
    resp = supabase.table("npcs").select("id, display_name, deck_id").execute()
    npcs = resp.data or []
    if not npcs:
        raise RuntimeError("No NPCs defined in npcs table")

    npc = random.choice(npcs)
    deck_defs = load_deck_card_defs(npc["deck_id"])
    return npc, deck_defs
