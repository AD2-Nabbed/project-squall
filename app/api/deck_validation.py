"""
Deck validation rules and functions.
"""
from typing import Dict, Any, List, Tuple, Optional


# Deck validation rules
MIN_DECK_SIZE = 20
MAX_DECK_SIZE = 30
MAX_COPIES_MONSTER = 2
MAX_COPIES_SPELL = 1
MAX_COPIES_TRAP = 1
MAX_COPIES_HERO = 1
REQUIRED_HEROES = 1


class DeckValidationError(Exception):
    """Raised when a deck fails validation."""
    pass


def validate_deck(deck_cards: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate a deck against the deck building rules.
    
    Args:
        deck_cards: List of deck card entries, each with:
            - card_code: str
            - quantity: int
            - cards: dict with card_type field (or card_type_id that needs mapping)
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Count total cards and by type
    total_cards = 0
    card_counts: Dict[str, int] = {}  # card_code -> quantity
    hero_count = 0
    
    # Map card_type_id to card_type if needed
    for item in deck_cards:
        card = item.get("cards", {})
        if not card:
            continue
            
        # Get card type (might be card_type_id or card_type)
        card_type = card.get("card_type")
        if not card_type:
            # If we have card_type_id, we'd need to map it, but for now skip
            continue
            
        card_code = item.get("card_code")
        quantity = item.get("quantity", 0)
        
        total_cards += quantity
        
        # Count heroes
        if card_type.lower() == "hero":
            hero_count += quantity
        
        # Track card counts
        if card_code:
            card_counts[card_code] = card_counts.get(card_code, 0) + quantity
    
    # Validate total deck size
    if total_cards < MIN_DECK_SIZE:
        errors.append(f"Deck too small: {total_cards} cards (minimum {MIN_DECK_SIZE})")
    
    if total_cards > MAX_DECK_SIZE:
        errors.append(f"Deck too large: {total_cards} cards (maximum {MAX_DECK_SIZE})")
    
    # Validate hero count
    if hero_count != REQUIRED_HEROES:
        if hero_count == 0:
            errors.append(f"Deck must contain exactly {REQUIRED_HEROES} hero (found {hero_count})")
        elif hero_count > REQUIRED_HEROES:
            errors.append(f"Deck contains too many heroes: {hero_count} (maximum {REQUIRED_HEROES})")
        else:
            errors.append(f"Deck must contain exactly {REQUIRED_HEROES} hero (found {hero_count})")
    
    # Validate card copy limits (check total counts per card_code)
    for card_code, total_quantity in card_counts.items():
        # Find the card type for this card_code
        card_type = None
        card_name = card_code
        for item in deck_cards:
            if item.get("card_code") == card_code:
                card = item.get("cards", {})
                if card:
                    card_type = card.get("card_type", "").lower()
                    card_name = card.get("name", card_code)
                break
        
        if not card_type:
            continue
        
        # Check copy limits based on card type
        if card_type == "monster":
            if total_quantity > MAX_COPIES_MONSTER:
                errors.append(f"{card_name}: {total_quantity} copies (maximum {MAX_COPIES_MONSTER} for monsters)")
        elif card_type == "spell":
            if total_quantity > MAX_COPIES_SPELL:
                errors.append(f"{card_name}: {total_quantity} copies (maximum {MAX_COPIES_SPELL} for spells)")
        elif card_type == "trap":
            if total_quantity > MAX_COPIES_TRAP:
                errors.append(f"{card_name}: {total_quantity} copies (maximum {MAX_COPIES_TRAP} for traps)")
        elif card_type == "hero":
            if total_quantity > MAX_COPIES_HERO:
                errors.append(f"{card_name}: {total_quantity} copies (maximum {MAX_COPIES_HERO} for heroes)")
    
    return len(errors) == 0, errors

