from __future__ import annotations

from typing import List, Dict

from app.db.supabase_client import supabase


def load_deck_card_defs(deck_id: str) -> List[Dict]:
    """
    Given a deck_id, load its card list from Supabase and return a list of
    card definition dicts ready for CardInstance.new_from_definition().

    This uses:
      - deck_cards (deck_id, card_code, quantity)
      - cards (card_code, name, card_type_id, stars, atk, hp, element_id, effect_tags, effect_params)
      - card_types (id, code) where code is 'monster', 'spell', 'trap', 'hero'
    """

    # 1) deck_cards for this deck
    dc_resp = (
        supabase.table("deck_cards")
        .select("card_code, quantity")
        .eq("deck_id", deck_id)
        .execute()
    )
    deck_rows = dc_resp.data or []
    if not deck_rows:
        raise ValueError(f"Deck {deck_id} has no cards")

    # 2) load all cards used in this deck
    card_codes = [row["card_code"] for row in deck_rows]
    cards_resp = (
        supabase.table("cards")
        .select("*")
        .in_("card_code", card_codes)
        .execute()
    )
    card_rows = cards_resp.data or []
    if not card_rows:
        raise ValueError(f"No cards found for deck {deck_id}")

    cards_by_code = {c["card_code"]: c for c in card_rows}

    # 3) load card_types mapping: id -> code ('monster', 'spell', etc.)
    ct_resp = supabase.table("card_types").select("id, code").execute()
    type_rows = ct_resp.data or []
    type_map = {row["id"]: row["code"] for row in type_rows}

    deck_defs: List[Dict] = []

    for row in deck_rows:
        code = row["card_code"]
        qty = row["quantity"]
        card = cards_by_code.get(code)
        if not card:
            raise ValueError(f"Card {code} referenced in deck but not found in cards table")

        card_type_id = card.get("card_type_id")
        card_type_code = type_map.get(card_type_id)
        if not card_type_code:
            raise ValueError(f"No card_type mapping for id {card_type_id} (card {code})")

        base_def = {
            "card_code": card["card_code"],
            "name": card["name"],
            "card_type": card_type_code,  # 'monster' | 'spell' | 'trap' | 'hero'
            "stars": card["stars"],
            "atk": card.get("atk") or 0,
            "hp": card.get("hp") or 0,
            "element_id": card.get("element_id"),
            "effect_tags": card.get("effect_tags") or [],
            "effect_params": card.get("effect_params") or {},
        }

        # Expand by quantity
        for _ in range(qty):
            deck_defs.append(base_def)

    return deck_defs
