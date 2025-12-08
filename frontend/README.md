# Project Squall - Frontend

A simple, mobile-friendly web UI for testing the Project Squall card battle engine.

## Quick Start

### Option 1: Simple HTTP Server (Python)

```bash
cd frontend
python -m http.server 8080
```

Then open: http://localhost:8080

### Option 2: Simple HTTP Server (Node.js)

```bash
cd frontend
npx http-server -p 8080
```

Then open: http://localhost:8080

### Option 3: Direct File Open

Simply open `index.html` in your browser (note: CORS may block API calls if opened as `file://`)

## Usage

1. **Start the backend server** (in the project root):
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. **Start the frontend** (in the `frontend` directory):
   ```bash
   python -m http.server 8080
   ```

3. **Open in browser**: http://localhost:8080

4. **Enter your Player ID and Deck ID** in the setup panel

5. **Click "Start Match"** to begin

## Features

- **Mobile-friendly responsive design** - Works on phones and tablets
- **Real-time game board** - Shows both players' zones, hand, and hero
- **Action buttons** - Play monsters, spells, traps, attack, use hero ability
- **Trap trigger prompts** - Modal popup when traps can be activated
- **Game log** - View recent game events
- **Clean API contract** - Easy to port to Unity/Godot later

## API Integration

The frontend communicates with the backend via REST API:

- `POST /battle/start` - Start a new match
- `POST /battle/action` - Send game actions (play card, attack, end turn, etc.)
- `POST /battle/trigger-trap` - Activate a trap trigger

All API calls are made to `http://127.0.0.1:8000` by default (configurable in `game.js`).

## Future Unity/Godot Integration

This frontend serves as a reference implementation. The API contract is designed to be easily consumed by Unity/Godot:

- All game state is returned in a consistent JSON format
- Actions are sent as simple POST requests with clear payloads
- Trap triggers use a two-step flow (prompt → activate)
- No client-side game logic - all calculations happen on the server

## Mobile Considerations

- Touch-friendly buttons and card selection
- Responsive grid layouts that adapt to screen size
- Scrollable hand and log areas
- Modal dialogs for actions and prompts
- Optimized for portrait orientation (can be extended for landscape)

