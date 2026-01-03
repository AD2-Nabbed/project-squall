from typing import Any, Dict, List

from app.db.supabase_client import supabase


def load_deck_card_defs(deck_id: str) -> List[Dict[str, Any]]:
    """
    Load a deck's card *definitions* from Supabase and expand quantities into
    a flat list of card_def dicts.

    Each returned dict is shaped for CardInstance.new_from_definition():
      {
        "card_code": str,
        "name": str,
        "card_type": "monster" | "spell" | "trap" | "hero",
        "stars": int,
        "atk": int,
        "hp": int,
        "element_id": int | None,
        "effect_tags": list[str],
        "effect_params": dict,
      }
    """

    # 1) Make sure the deck exists (we don't enforce ownership here yet)
    deck_resp = (
        supabase.table("decks")
        .select("id, name")
        .eq("id", deck_id)
        .single()
        .execute()
    )
    deck_row = deck_resp.data
    if not deck_row:
        raise RuntimeError(f"Deck {deck_id} not found")

    # 2) Load card_types so we can map card_type_id -> code ("monster", "spell", etc.)
    ct_resp = supabase.table("card_types").select("card_type_id, code").execute()
    ct_rows = ct_resp.data or []
    type_map: Dict[int, str] = {row["card_type_id"]: row["code"] for row in ct_rows}

    # 3) Load deck_cards joined with cards
    dc_resp = (
        supabase.table("deck_cards")
        .select(
            "card_code, quantity, "
            "cards(name, card_type_id, stars, atk, hp, element_id, effect_tags, effect_params, rules_text, art_asset_id, hero_data)"
        )
        .eq("deck_id", deck_id)
        .execute()
    )

    dc_rows = dc_resp.data or []
    expanded_defs: List[Dict[str, Any]] = []

    for row in dc_rows:
        card_row = row["cards"]
        card_type_id = card_row["card_type_id"]
        card_type_code = type_map.get(card_type_id, "monster")

        base_def: Dict[str, Any] = {
            "card_code": row["card_code"],
            "name": card_row["name"],
            "card_type": card_type_code,
            "stars": card_row.get("stars") or 0,
            "atk": card_row.get("atk") or 0,
            "hp": card_row.get("hp") or 0,
            "element_id": card_row.get("element_id"),
            "effect_tags": card_row.get("effect_tags") or [],
            "effect_params": card_row.get("effect_params") or {},
            "hero_data": card_row.get("hero_data"),  # For hero active abilities
            # Use rules_text only for description (flavor_text is just for fun, not needed during playtest)
            "description": card_row.get("rules_text") or "",
            "art_asset_id": card_row.get("art_asset_id") or "",
        }

        qty = int(row.get("quantity") or 0)
        for _ in range(qty):
            expanded_defs.append(base_def.copy())

    return expanded_defs
