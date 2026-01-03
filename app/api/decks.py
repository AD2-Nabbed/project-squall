"""
Deck management API endpoints.
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.db.supabase_client import supabase
from app.api.auth import get_current_user
from app.api.deck_validation_helper import validate_deck_by_id

router = APIRouter(prefix="/api/decks", tags=["decks"])


class CreateDeckRequest(BaseModel):
    name: str
    is_public: bool = False


class UpdateDeckRequest(BaseModel):
    name: Optional[str] = None
    is_public: Optional[bool] = None


class AddCardRequest(BaseModel):
    card_code: str
    quantity: int = 1


class UpdateCardQuantityRequest(BaseModel):
    quantity: int


@router.get("")
def list_decks(session_token: Optional[str] = Query(None, description="Session token")) -> List[Dict[str, Any]]:
    """List all decks for the current user."""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    player_id = user["player_id"]
    
    resp = (
        supabase.table("decks")
        .select("id, name, is_public, created_at, updated_at")
        .eq("owner_id", player_id)
        .execute()
    )
    
    return resp.data or []


@router.post("")
def create_deck(payload: CreateDeckRequest, session_token: Optional[str] = Query(None, description="Session token")) -> Dict[str, Any]:
    """Create a new deck."""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    player_id = user["player_id"]
    
    resp = (
        supabase.table("decks")
        .insert({
            "owner_id": player_id,
            "name": payload.name,
            "is_public": payload.is_public,
        })
        .execute()
    )
    
    if not resp.data:
        raise HTTPException(status_code=500, detail="Failed to create deck")
    
    return resp.data[0]


@router.get("/{deck_id}")
def get_deck(deck_id: str, session_token: Optional[str] = Query(None, description="Session token")) -> Dict[str, Any]:
    """Get deck details with cards."""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    player_id = user["player_id"]
    
    # Get deck
    deck_resp = (
        supabase.table("decks")
        .select("id, name, is_public, owner_id, created_at, updated_at")
        .eq("id", deck_id)
        .single()
        .execute()
    )
    
    if not deck_resp.data:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    deck = deck_resp.data
    
    # Verify ownership
    if deck["owner_id"] != player_id:
        raise HTTPException(status_code=403, detail="Not your deck")
    
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
    
    deck["cards"] = cards
    
    # Validate deck and include validation status
    is_valid, validation_errors = validate_deck_by_id(deck_id)
    deck["validation"] = {
        "is_valid": is_valid,
        "errors": validation_errors
    }
    
    return deck


@router.put("/{deck_id}")
def update_deck(deck_id: str, payload: UpdateDeckRequest, session_token: Optional[str] = Query(None, description="Session token")) -> Dict[str, Any]:
    """Update deck name or public status."""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    player_id = user["player_id"]
    
    # Verify ownership
    deck_resp = (
        supabase.table("decks")
        .select("owner_id")
        .eq("id", deck_id)
        .single()
        .execute()
    )
    
    if not deck_resp.data:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    if deck_resp.data["owner_id"] != player_id:
        raise HTTPException(status_code=403, detail="Not your deck")
    
    # Update
    update_data = {}
    if payload.name is not None:
        update_data["name"] = payload.name
    if payload.is_public is not None:
        update_data["is_public"] = payload.is_public
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    resp = (
        supabase.table("decks")
        .update(update_data)
        .eq("id", deck_id)
        .execute()
    )
    
    return resp.data[0] if resp.data else {}


@router.delete("/{deck_id}")
def delete_deck(deck_id: str, session_token: Optional[str] = Query(None, description="Session token")) -> Dict[str, str]:
    """Delete a deck."""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    player_id = user["player_id"]
    
    # Verify ownership
    deck_resp = (
        supabase.table("decks")
        .select("owner_id")
        .eq("id", deck_id)
        .single()
        .execute()
    )
    
    if not deck_resp.data:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    if deck_resp.data["owner_id"] != player_id:
        raise HTTPException(status_code=403, detail="Not your deck")
    
    # Delete deck (deck_cards will cascade or need manual deletion)
    supabase.table("deck_cards").delete().eq("deck_id", deck_id).execute()
    supabase.table("decks").delete().eq("id", deck_id).execute()
    
    return {"message": "Deck deleted"}


@router.post("/{deck_id}/cards")
def add_card_to_deck(deck_id: str, payload: AddCardRequest, session_token: Optional[str] = Query(None, description="Session token")) -> Dict[str, Any]:
    """Add a card to a deck."""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    player_id = user["player_id"]
    
    # Verify ownership
    deck_resp = (
        supabase.table("decks")
        .select("owner_id")
        .eq("id", deck_id)
        .single()
        .execute()
    )
    
    if not deck_resp.data:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    if deck_resp.data["owner_id"] != player_id:
        raise HTTPException(status_code=403, detail="Not your deck")
    
    # Check if card already in deck (use execute() without single() since it might not exist)
    existing_resp = (
        supabase.table("deck_cards")
        .select("quantity")
        .eq("deck_id", deck_id)
        .eq("card_code", payload.card_code)
        .execute()
    )
    
    existing_card = existing_resp.data[0] if existing_resp.data else None
    
    if existing_card:
        # Update quantity
        new_quantity = existing_card["quantity"] + payload.quantity
        resp = (
            supabase.table("deck_cards")
            .update({"quantity": new_quantity})
            .eq("deck_id", deck_id)
            .eq("card_code", payload.card_code)
            .execute()
        )
    else:
        # Insert new
        resp = (
            supabase.table("deck_cards")
            .insert({
                "deck_id": deck_id,
                "card_code": payload.card_code,
                "quantity": payload.quantity,
            })
            .execute()
        )
    
    return resp.data[0] if resp.data else {}


@router.put("/{deck_id}/cards/{card_code}")
def update_card_quantity(
    deck_id: str,
    card_code: str,
    payload: UpdateCardQuantityRequest,
    session_token: Optional[str] = Query(None, description="Session token")
) -> Dict[str, Any]:
    """Update card quantity in deck."""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    player_id = user["player_id"]
    
    # Verify ownership
    deck_resp = (
        supabase.table("decks")
        .select("owner_id")
        .eq("id", deck_id)
        .single()
        .execute()
    )
    
    if not deck_resp.data or deck_resp.data["owner_id"] != player_id:
        raise HTTPException(status_code=403, detail="Not your deck")
    
    if payload.quantity <= 0:
        # Remove card
        supabase.table("deck_cards").delete().eq("deck_id", deck_id).eq("card_code", card_code).execute()
        return {"message": "Card removed"}
    
    # Update quantity
    resp = (
        supabase.table("deck_cards")
        .update({"quantity": payload.quantity})
        .eq("deck_id", deck_id)
        .eq("card_code", card_code)
        .execute()
    )
    
    return resp.data[0] if resp.data else {}


@router.delete("/{deck_id}/cards/{card_code}")
def remove_card_from_deck(deck_id: str, card_code: str, session_token: Optional[str] = Query(None, description="Session token")) -> Dict[str, str]:
    """Remove a card from a deck."""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    player_id = user["player_id"]
    
    # Verify ownership
    deck_resp = (
        supabase.table("decks")
        .select("owner_id")
        .eq("id", deck_id)
        .single()
        .execute()
    )
    
    if not deck_resp.data or deck_resp.data["owner_id"] != player_id:
        raise HTTPException(status_code=403, detail="Not your deck")
    
    supabase.table("deck_cards").delete().eq("deck_id", deck_id).eq("card_code", card_code).execute()
    
    return {"message": "Card removed from deck"}

