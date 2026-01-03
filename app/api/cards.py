"""
Card catalog API endpoints.
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.db.supabase_client import supabase
from app.api.auth import get_current_user

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("/catalog")
def get_card_catalog(
    card_type: Optional[str] = Query(None, description="Filter by card type"),
    element_id: Optional[int] = Query(None, description="Filter by element"),
    search: Optional[str] = Query(None, description="Search by name"),
    session_token: Optional[str] = Query(None, description="Session token"),
) -> List[Dict[str, Any]]:
    """Get all cards in the catalog with optional filters."""
    # Load card types mapping
    type_resp = supabase.table("card_types").select("card_type_id, code").execute()
    type_map = {row["code"]: row["card_type_id"] for row in (type_resp.data or [])}
    
    query = supabase.table("cards").select("*")
    
    if card_type:
        # Map card type code to card_type_id
        card_type_id = type_map.get(card_type)
        if card_type_id:
            query = query.eq("card_type_id", card_type_id)
    
    if element_id:
        query = query.eq("element_id", element_id)
    
    if search:
        query = query.ilike("name", f"%{search}%")
    
    resp = query.execute()
    
    # Map card_type_id back to code for frontend
    cards = resp.data or []
    for card in cards:
        card_type_id = card.get("card_type_id")
        if card_type_id:
            # Find the code for this card_type_id
            for code, cid in type_map.items():
                if cid == card_type_id:
                    card["card_type"] = code
                    break
    
    return cards


@router.get("/owned")
def get_owned_cards(session_token: Optional[str] = Query(None, description="Session token")) -> List[Dict[str, Any]]:
    """Get cards owned by the current user."""
    user = get_current_user(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    player_id = user["player_id"]
    
    # Load card types mapping
    type_resp = supabase.table("card_types").select("card_type_id, code").execute()
    type_map = {row["card_type_id"]: row["code"] for row in (type_resp.data or [])}
    
    # Get owned cards with card details
    resp = (
        supabase.table("owned_cards")
        .select("card_code, quantity, cards(*)")
        .eq("owner_id", player_id)
        .execute()
    )
    
    owned_cards = resp.data or []
    
    # Map card_type_id to code for each card
    for item in owned_cards:
        card = item.get("cards", {})
        if card and "card_type_id" in card:
            card_type_id = card["card_type_id"]
            card["card_type"] = type_map.get(card_type_id, "unknown")
    
    return owned_cards


@router.get("/{card_code}")
def get_card_details(card_code: str) -> Dict[str, Any]:
    """Get detailed information about a specific card."""
    resp = (
        supabase.table("cards")
        .select("*")
        .eq("card_code", card_code)
        .single()
        .execute()
    )
    
    if not resp.data:
        raise HTTPException(status_code=404, detail="Card not found")
    
    return resp.data

