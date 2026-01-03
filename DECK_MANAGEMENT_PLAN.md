# Deck Management System - Implementation Plan

## Database Schema

### New Table: `auth`
```sql
CREATE TABLE auth (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,  -- bcrypt hash
  player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Existing Tables (Confirmed)
- `players` - id, gamer_tag, created_at, updated_at
- `cards` - card_code, name, card_type_id, stars, atk, hp, effect_tags, effect_params, hero_data, etc.
- `decks` - id, owner_id, name, is_public, created_at, updated_at
- `deck_cards` - deck_id, card_code, quantity
- `owned_cards` - owner_id, card_code, quantity

## API Endpoints Needed

### Authentication
- `POST /auth/register` - Create account (username, password, gamer_tag)
- `POST /auth/login` - Login (username, password) → returns session token
- `GET /auth/me` - Get current user info (requires auth)
- `POST /auth/logout` - Logout

### Card Catalog
- `GET /cards/catalog` - Get all cards (with filters)
- `GET /cards/owned` - Get owned cards for current user
- `GET /cards/{card_code}` - Get card details

### Deck Management
- `GET /decks` - List user's decks
- `POST /decks` - Create new deck
- `GET /decks/{deck_id}` - Get deck details with cards
- `PUT /decks/{deck_id}` - Update deck name/public
- `DELETE /decks/{deck_id}` - Delete deck
- `POST /decks/{deck_id}/cards` - Add card to deck
- `PUT /decks/{deck_id}/cards/{card_code}` - Update card quantity
- `DELETE /decks/{deck_id}/cards/{card_code}` - Remove card from deck

## Frontend Pages

1. **Login/Register Page** (`/login.html`)
   - Login form
   - Register form
   - Redirect to dashboard after login

2. **Dashboard** (`/dashboard.html`)
   - Player info display
   - Navigation: Play Match | Card Catalog | My Decks

3. **Card Catalog** (`/catalog.html`)
   - Display owned cards
   - Filter/search cards
   - Card details modal
   - "Add to Deck" functionality

4. **Deck Editor** (`/deck-editor.html`)
   - Create/Edit deck
   - Add/remove cards
   - Set quantities
   - Save deck

5. **Game** (`/game.html` or integrate into dashboard)
   - Existing game interface
   - Deck selection dropdown
   - Start match button

## Authentication Strategy

- Use JWT tokens or session cookies
- Store session in backend (simple dict for now, or use Supabase auth later)
- Protect API endpoints with auth middleware

## Implementation Order

1. Create auth table migration
2. Create auth API endpoints
3. Create deck management API endpoints
4. Create card catalog API endpoints
5. Create frontend pages
6. Integrate game into website
7. Add navigation/routing

