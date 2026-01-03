#!/usr/bin/env python3
"""
Helper script to link an existing player to the auth system.

Usage:
    python link_existing_player.py <username> <password> <player_id>

Example:
    python link_existing_player.py nabbed mypassword d4ac398c-12a6-4cf3-836e-8ede11835029
"""
import sys
import os
import bcrypt
import uuid

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.supabase_client import supabase


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def link_existing_player(username: str, password: str, player_id: str):
    """Link an existing player to an auth account."""
    
    # 1. Verify player exists
    player_resp = (
        supabase.table("players")
        .select("id, gamer_tag")
        .eq("id", player_id)
        .single()
        .execute()
    )
    
    if not player_resp.data:
        print(f"Error: Player with ID {player_id} not found!")
        return False
    
    player = player_resp.data
    print(f"Found player: {player['gamer_tag']} (ID: {player['id']})")
    
    # 2. Check if username already exists
    existing_auth = (
        supabase.table("auth")
        .select("id, username")
        .eq("username", username)
        .execute()
    )
    
    if existing_auth.data:
        print(f"Error: Username '{username}' already exists!")
        return False
    
    # 3. Check if player already has an auth account
    existing_player_auth = (
        supabase.table("auth")
        .select("id, username")
        .eq("player_id", player_id)
        .execute()
    )
    
    if existing_player_auth.data:
        print(f"Warning: Player already has an auth account: {existing_player_auth.data[0]['username']}")
        response = input("Do you want to create another? (y/N): ")
        if response.lower() != 'y':
            return False
    
    # 4. Create auth account
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
        print("Error: Failed to create auth account!")
        return False
    
    print(f"\n✅ Success! Created auth account:")
    print(f"   Username: {username}")
    print(f"   Player: {player['gamer_tag']}")
    print(f"   Player ID: {player_id}")
    print(f"\nYou can now login with username: {username}")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python link_existing_player.py <username> <password> <player_id>")
        print("\nExample:")
        print("  python link_existing_player.py nabbed mypassword d4ac398c-12a6-4cf3-836e-8ede11835029")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    player_id = sys.argv[3]
    
    # Check environment variables
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set!")
        sys.exit(1)
    
    success = link_existing_player(username, password, player_id)
    sys.exit(0 if success else 1)

