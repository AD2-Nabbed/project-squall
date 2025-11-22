# app/services/matches.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional
from uuid import UUID


Mode = Literal["PVE", "PVP"]


@dataclass
class MatchRecord:
    id: UUID
    mode: Mode
    player1_id: Optional[UUID]
    player2_id: Optional[UUID]
    npc_id: Optional[UUID]
    player1_deck_id: Optional[UUID]
    player2_deck_id: Optional[UUID]
    serialized_game_state: Dict[str, Any]
    status: str


class MatchModeError(ValueError):
    """Raised when an invalid combination of mode / ids is provided."""
    pass


def _validate_mode_combo(
    mode: Mode,
    player1_id: Optional[UUID],
    player2_id: Optional[UUID],
    npc_id: Optional[UUID],
) -> None:
    """
    Ensure the PVE / PVP id combinations are correct before we hit the DB.
    Mirrors the CHECK constraint on the matches table.
    """
    if mode == "PVE":
        if player1_id is None:
            raise MatchModeError("PVE: player1_id must not be None")
        if npc_id is None:
            raise MatchModeError("PVE: npc_id must not be None")
        if player2_id is not None:
            raise MatchModeError("PVE: player2_id must be None")
    elif mode == "PVP":
        if player1_id is None:
            raise MatchModeError("PVP: player1_id must not be None")
        if player2_id is None:
            raise MatchModeError("PVP: player2_id must not be None")
        if npc_id is not None:
            raise MatchModeError("PVP: npc_id must be None")
    else:
        raise MatchModeError(f"Invalid mode: {mode}")


def create_match_record(
    supabase_client: Any,
    *,
    mode: Mode,
    player1_id: UUID,
    player1_deck_id: UUID,
    serialized_game_state: Dict[str, Any],
    npc_id: Optional[UUID] = None,
    player2_id: Optional[UUID] = None,
    player2_deck_id: Optional[UUID] = None,
    status: str = "in_progress",
) -> MatchRecord:
    """
    Insert a new row into public.matches with the correct mode semantics.

    This is the function you should call from /battle/start.

    Example PVE call:
        create_match_record(
            supabase_client,
            mode="PVE",
            player1_id=player.id,
            player1_deck_id=player_deck.id,
            npc_id=npc.id,
            serialized_game_state=game_state_dict,
        )

    Example PVP call:
        create_match_record(
            supabase_client,
            mode="PVP",
            player1_id=player1.id,
            player1_deck_id=player1_deck.id,
            player2_id=player2.id,
            player2_deck_id=player2_deck.id,
            serialized_game_state=game_state_dict,
        )
    """
    _validate_mode_combo(mode, player1_id, player2_id, npc_id)

    row = {
        "mode": mode,
        "status": status,
        "player1_id": str(player1_id) if player1_id is not None else None,
        "player1_deck_id": str(player1_deck_id) if player1_deck_id is not None else None,
        "player2_id": str(player2_id) if player2_id is not None else None,
        "player2_deck_id": str(player2_deck_id) if player2_deck_id is not None else None,
        "npc_id": str(npc_id) if npc_id is not None else None,
        "serialized_game_state": serialized_game_state,
        "result": None,
    }

    # supabase-py style call; adjust if your client differs
    result = (
        supabase_client
        .table("matches")
        .insert(row)
        .execute()
    )

    data = result.data[0]

    return MatchRecord(
        id=UUID(data["id"]),
        mode=data["mode"],
        player1_id=UUID(data["player1_id"]) if data.get("player1_id") else None,
        player2_id=UUID(data["player2_id"]) if data.get("player2_id") else None,
        npc_id=UUID(data["npc_id"]) if data.get("npc_id") else None,
        player1_deck_id=UUID(data["player1_deck_id"]) if data.get("player1_deck_id") else None,
        player2_deck_id=UUID(data["player2_deck_id"]) if data.get("player2_deck_id") else None,
        serialized_game_state=data["serialized_game_state"],
        status=data["status"],
    )


def update_match_state(
    supabase_client: Any,
    *,
    match_id: UUID,
    serialized_game_state: Dict[str, Any],
    status: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
) -> MatchRecord:
    """
    Update serialized_game_state (and optionally status/result) for a match.

    This is what you should call from /battle/action after applying an action.
    """
    update_payload: Dict[str, Any] = {
        "serialized_game_state": serialized_game_state,
    }
    if status is not None:
        update_payload["status"] = status
    if result is not None:
        update_payload["result"] = result

    result_obj = (
        supabase_client
        .table("matches")
        .update(update_payload)
        .eq("id", str(match_id))
        .single()
        .execute()
    )

    data = result_obj.data

    return MatchRecord(
        id=UUID(data["id"]),
        mode=data["mode"],
        player1_id=UUID(data["player1_id"]) if data.get("player1_id") else None,
        player2_id=UUID(data["player2_id"]) if data.get("player2_id") else None,
        npc_id=UUID(data["npc_id"]) if data.get("npc_id") else None,
        player1_deck_id=UUID(data["player1_deck_id"]) if data.get("player1_deck_id") else None,
        player2_deck_id=UUID(data["player2_deck_id"]) if data.get("player2_deck_id") else None,
        serialized_game_state=data["serialized_game_state"],
        status=data["status"],
    )
