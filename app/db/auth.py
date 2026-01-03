"""
Authentication database operations.
"""
from typing import Optional, Dict, Any
import bcrypt
import uuid
from app.db.supabase_client import supabase


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def create_auth_account(username: str, password: str, gamer_tag: str) -> Dict[str, Any]:
    """
    Create a new auth account and player.
    
    Returns:
        {
            "auth_id": str,
            "player_id": str,
            "gamer_tag": str
        }
    """
    # 1. Create player first (generate UUID for id)
    player_id = str(uuid.uuid4())
    player_resp = (
        supabase.table("players")
        .insert({
            "id": player_id,
            "gamer_tag": gamer_tag,
        })
        .execute()
    )
    
    if not player_resp.data:
        raise RuntimeError("Failed to create player")
    
    # 2. Create auth account
    password_hash = hash_password(password)
    auth_resp = (
        supabase.table("auth")
        .insert({
            "username": username,
            "password_hash": password_hash,
            "player_id": player_id,
        })
        .execute()
    )
    
    if not auth_resp.data:
        # Rollback: delete player if auth creation failed
        supabase.table("players").delete().eq("id", player_id).execute()
        raise RuntimeError("Failed to create auth account")
    
    return {
        "auth_id": auth_resp.data[0]["id"],
        "player_id": player_id,
        "gamer_tag": gamer_tag,
    }


def verify_login(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Verify login credentials.
    
    Returns:
        {
            "auth_id": str,
            "player_id": str,
            "gamer_tag": str
        } or None if invalid
    """
    # Get auth record
    auth_resp = (
        supabase.table("auth")
        .select("id, password_hash, player_id, players(gamer_tag)")
        .eq("username", username)
        .single()
        .execute()
    )
    
    if not auth_resp.data:
        return None
    
    auth_data = auth_resp.data
    password_hash = auth_data["password_hash"]
    
    # Verify password
    if not verify_password(password, password_hash):
        return None
    
    # Get player info
    player_data = auth_data.get("players", {})
    
    return {
        "auth_id": auth_data["id"],
        "player_id": auth_data["player_id"],
        "gamer_tag": player_data.get("gamer_tag", ""),
    }


def get_player_by_auth_id(auth_id: str) -> Optional[Dict[str, Any]]:
    """Get player info by auth_id."""
    auth_resp = (
        supabase.table("auth")
        .select("player_id, players(id, gamer_tag)")
        .eq("id", auth_id)
        .single()
        .execute()
    )
    
    if not auth_resp.data:
        return None
    
    player_data = auth_resp.data.get("players", {})
    return {
        "player_id": player_data.get("id"),
        "gamer_tag": player_data.get("gamer_tag"),
    }

