# Project Squall - Web Application

Full-featured deck management and game interface.

## Setup

### 1. Create Auth Table

Run the migration in your Supabase SQL editor:
```sql
-- See migrations/001_create_auth_table.sql
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Backend

```bash
# Set environment variables
set SUPABASE_URL=https://xvxgkrittqgwqpuzryrf.supabase.co
set SUPABASE_SERVICE_ROLE_KEY=your_key_here

# Start server
uvicorn app.main:app --reload --port 8000
```

### 4. Start Web App

```bash
cd webapp
python -m http.server 8080
```

### 5. Open Browser

Navigate to: **http://localhost:8080**

## Features

- **Authentication**: Register/Login system
- **Card Catalog**: View all cards and your owned cards
- **Deck Management**: Create, edit, and delete decks
- **Deck Editor**: Add/remove cards, set quantities
- **Game Integration**: Launch matches with your decks

## Usage

1. **Register/Login**: Create an account or login
2. **Card Catalog**: Browse cards and see what you own
3. **My Decks**: Create and manage your decks
4. **Play Match**: Select a deck and start a game

## API Endpoints

All API endpoints are under `/api/`:
- `/api/auth/*` - Authentication
- `/api/decks/*` - Deck management
- `/api/cards/*` - Card catalog

See `DECK_MANAGEMENT_PLAN.md` for full API documentation.

