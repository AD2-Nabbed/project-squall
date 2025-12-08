# AI Control and PVP Mode Implementation

## Summary

Added AI control for NPCs in PVE matches and PVP mode support for player vs player matches.

## Features Added

### 1. AI Controller (`app/engine/ai_controller.py`)
- Simple rule-based AI that makes decisions for NPC turns
- Priority order:
  1. Summon hero if possible (2 tributes available)
  2. Summon highest-star monster (with tribute if needed)
  3. Play spell if available
  4. Set trap if available
  5. Attack with strongest monster
  6. End turn

### 2. Match Mode Toggle
- **PVE Mode**: Player vs AI-controlled NPC
  - AI automatically takes turns
  - Frontend processes AI turns automatically
- **PVP Mode**: Player vs Player
  - Both players control their own actions
  - Action buttons disabled when not your turn
  - Requires Player 2 ID and Deck ID

### 3. Backend Changes

**`/battle/start` endpoint:**
- Added `mode` parameter: `"PVE"` or `"PVP"`
- Added `player2_id` and `player2_deck_id` for PVP mode
- Validates both players and decks for PVP

**`/battle/action` endpoint:**
- Returns `ai_turn: true` when turn switches to AI in PVE mode
- Frontend automatically processes AI turn

**`/battle/ai-turn` endpoint:**
- Processes a full AI turn (up to 10 actions)
- Automatically makes decisions and executes actions
- Returns updated game state

### 4. Frontend Changes

**Setup Panel:**
- Match mode dropdown (PVE/PVP)
- Player 2 fields shown only in PVP mode
- Toggle function to show/hide PVP fields

**Game Board:**
- Turn indicator shows "(Your Turn)" or "(Opponent's Turn)"
- Action buttons disabled in PVP when not your turn
- Automatic AI turn processing in PVE mode
- Visual feedback for whose turn it is

## Usage

### PVE Mode (Default)
1. Select "PVE (vs AI)" from dropdown
2. Enter Player 1 ID and Deck ID
3. Click "Start Match"
4. AI automatically takes turns when it's opponent's turn

### PVP Mode
1. Select "PVP (vs Player)" from dropdown
2. Enter Player 1 ID and Deck ID
3. Enter Player 2 ID and Deck ID
4. Click "Start Match"
5. Both players take turns manually
6. Action buttons are disabled when not your turn

## AI Behavior

The AI follows a simple priority system:
- Always tries to summon hero first if possible
- Summons strongest monsters available
- Plays spells and sets traps when possible
- Attacks with strongest monsters
- Ends turn when no more actions available

## Future Improvements

- More sophisticated AI decision making
- AI difficulty levels (easy/medium/hard)
- AI personality traits (aggressive/defensive/balanced)
- Better targeting logic for spells and attacks
- AI trap activation logic

