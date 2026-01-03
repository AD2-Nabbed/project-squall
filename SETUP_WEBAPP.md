# Setting Up the Web Application

## Step 1: Create Auth Table in Supabase

1. Go to your Supabase dashboard
2. Open the SQL Editor
3. Run the migration script from `migrations/001_create_auth_table.sql`

This creates the `auth` table for user accounts.

## Step 2: Install Python Dependencies

```bash
pip install bcrypt
```

Or reinstall all requirements:
```bash
pip install -r requirements.txt
```

## Step 3: Start Backend Server

```bash
# In project root
.venv\Scripts\activate.bat
set SUPABASE_URL=https://xvxgkrittqgwqpuzryrf.supabase.co
set SUPABASE_SERVICE_ROLE_KEY=your_key_here
uvicorn app.main:app --reload --port 8000
```

## Step 4: Start Web App Server

**New terminal:**
```bash
cd webapp
python -m http.server 8080
```

## Step 5: Open Web App

Navigate to: **http://localhost:8080**

## First Time Setup

1. **Register an account**:
   - Username: Choose a username
   - Password: Choose a password
   - Gamer Tag: Your display name

2. **Add cards to your collection**:
   - You'll need to manually add cards to the `owned_cards` table in Supabase
   - Format: `owner_id` (your player_id), `card_code`, `quantity`

3. **Create your first deck**:
   - Go to "My Decks"
   - Click "Create New Deck"
   - Add cards from your collection
   - Save the deck

4. **Play a match**:
   - Go to "Play Match"
   - Select your deck
   - Start playing!

## Database Structure

### Auth Table (New)
- `username` - Unique username
- `password_hash` - Bcrypt hashed password
- `player_id` - Links to `players` table

### Owned Cards
You need to populate `owned_cards` table manually for now:
```sql
INSERT INTO owned_cards (owner_id, card_code, quantity)
VALUES 
  ('your-player-id', 'CORE-SUMMON-037', 3),
  ('your-player-id', 'CORE-SPELL-001', 2);
```

## Next Steps

- Add card opening/pack system
- Add card trading
- Add deck validation (min/max cards, hero requirement)
- Add deck sharing (public decks)
- Improve UI/UX

