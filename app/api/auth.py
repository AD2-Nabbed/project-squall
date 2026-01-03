"""
Authentication API endpoints.
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from app.db.auth import create_auth_account, verify_login, get_player_by_auth_id

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str
    gamer_tag: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    auth_id: str
    player_id: str
    gamer_tag: str


# Simple session storage (in production, use Redis or database)
sessions: Dict[str, Dict[str, Any]] = {}


def get_current_user(session_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get current user from session token."""
    if not session_token:
        return None
    return sessions.get(session_token)


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> Dict[str, Any]:
    """Register a new account."""
    try:
        result = create_auth_account(
            username=payload.username,
            password=payload.password,
            gamer_tag=payload.gamer_tag,
        )
        
        # Create session
        import uuid
        session_token = str(uuid.uuid4())
        sessions[session_token] = {
            "auth_id": result["auth_id"],
            "player_id": result["player_id"],
            "gamer_tag": result["gamer_tag"],
        }
        
        return {
            **result,
            "session_token": session_token,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=Dict[str, Any])
def login(payload: LoginRequest) -> Dict[str, Any]:
    """Login and get session token."""
    result = verify_login(payload.username, payload.password)
    
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Create session
    import uuid
    session_token = str(uuid.uuid4())
    sessions[session_token] = result
    
    return {
        **result,
        "session_token": session_token,
    }


@router.get("/me")
def get_me(session_token: Optional[str] = None) -> Dict[str, Any]:
    """Get current user info."""
    user = get_current_user(session_token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return user


@router.post("/logout")
def logout(session_token: Optional[str] = None) -> Dict[str, str]:
    """Logout and invalidate session."""
    if session_token and session_token in sessions:
        del sessions[session_token]
    
    return {"message": "Logged out"}


# Helper function to get session token from query or header
def get_session_token_from_request(session_token: Optional[str] = None) -> Optional[str]:
    """Extract session token from query param or request."""
    return session_token

