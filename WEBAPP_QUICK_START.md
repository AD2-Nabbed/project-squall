# Web App Quick Start Guide

## What's Been Created

A complete deck management web application with:
- ✅ User authentication (register/login)
- ✅ Card catalog (view all cards + owned cards)
- ✅ Deck management (create/edit/delete decks)
- ✅ Deck editor (add/remove cards, set quantities)
- ✅ Game integration (launch matches)

## Setup Steps

### 1. Run Database Migration

**In Supabase SQL Editor**, run:
```sql
CREATE TABLE IF NOT EXISTS auth (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_username ON auth(username);
CREATE INDEX IF NOT EXISTS idx_auth_player_id ON auth(player_id);
```

### 2. Install Dependencies

```bash
pip install bcrypt
```

### 3. Start Backend (Terminal 1)

```bash
cd C:\Users\Nabbed\Documents\GitHub\project-squall
.venv\Scripts\activate.bat
set SUPABASE_URL=https://xvxgkrittqgwqpuzryrf.supabase.co
set SUPABASE_SERVICE_ROLE_KEY=your_key_here
uvicorn app.main:app --reload --port 8000
```

### 4. Start Web App (Terminal 2)

```bash
cd C:\Users\Nabbed\Documents\GitHub\project-squall\webapp
python -m http.server 8080
```

### 5. Open Browser

**http://localhost:8080**

## First Time Use

1. **Register Account**
   - Choose username, password, gamer tag
   - This creates a player account automatically

2. **Add Cards to Collection**
   - Go to Supabase `owned_cards` table
   - Add rows: `owner_id` (your player_id), `card_code`, `quantity`
   - Example:
     ```sql
     INSERT INTO owned_cards (owner_id, card_code, quantity)
     VALUES ('your-player-id', 'CORE-SUMMON-037', 3);
     ```

3. **Create a Deck**
   - Click "My Decks"
   - Click "Create New Deck"
   - Add cards from your collection
   - Save deck

4. **Play Match**
   - Click "Play Match"
   - Select your deck
   - Start playing!

## File Structure

```
webapp/
  ├── index.html      # Main web app (all pages)
  ├── styles.css      # Styling
  ├── app.js          # Frontend logic
  └── README.md       # Documentation

app/api/
  ├── auth.py         # Authentication endpoints
  ├── decks.py        # Deck management endpoints
  └── cards.py        # Card catalog endpoints

app/db/
  └── auth.py         # Auth database operations

migrations/
  └── 001_create_auth_table.sql
```

## Features

- **Login/Register**: Secure authentication with bcrypt password hashing
- **Dashboard**: View player info and quick actions
- **Card Catalog**: Browse all cards, filter by type, search
- **My Decks**: List all your decks, create/edit/delete
- **Deck Editor**: Visual deck builder with owned cards panel
- **Game Integration**: Launch matches with selected deck

## API Endpoints

All endpoints are under `/api/`:
- `POST /api/auth/register` - Create account
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Get current user
- `GET /api/decks` - List decks
- `POST /api/decks` - Create deck
- `GET /api/cards/catalog` - Get all cards
- `GET /api/cards/owned` - Get owned cards

See `DECK_MANAGEMENT_PLAN.md` for full API docs.

