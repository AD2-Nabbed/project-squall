"""
Helper function to validate a deck by deck_id.
"""
from typing import Tuple, List
from app.db.supabase_client import supabase
from app.api.deck_validation import validate_deck


def validate_deck_by_id(deck_id: str) -> Tuple[bool, List[str]]:
    """
    Load a deck and validate it.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    # Load card types mapping
    type_resp = supabase.table("card_types").select("card_type_id, code").execute()
    type_map = {row["card_type_id"]: row["code"] for row in (type_resp.data or [])}
    
    # Get deck cards with full card details
    cards_resp = (
        supabase.table("deck_cards")
        .select("card_code, quantity, cards(*)")
        .eq("deck_id", deck_id)
        .execute()
    )
    
    cards = cards_resp.data or []
    
    # Map card_type_id to code for each card
    for item in cards:
        card = item.get("cards", {})
        if card and "card_type_id" in card:
            card_type_id = card["card_type_id"]
            card["card_type"] = type_map.get(card_type_id, "unknown")
    
    return validate_deck(cards)

