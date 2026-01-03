# Fixed: Hero Data Support for Active Abilities

## Issue Found
The code was looking for `active_ability` in `effect_params`, but your database structure stores:
- `effect_params` → contains `passive_aura`
- `hero_data` → contains `active_ability`

## Changes Made

### 1. Updated `app/db/decks.py`
- Added `hero_data` to the database SELECT query
- Added `hero_data` to the card definition dictionary
- Now hero cards will have their `hero_data` field loaded from the database

### 2. Updated `app/main.py` (Hero Ability Handler)
- Changed logic to check `hero_data` first for `active_ability`
- Falls back to `effect_params.active_ability` for backwards compatibility
- Properly parses JSON if `hero_data` is stored as a string

## Database Structure (Confirmed)

Your heroes should have:

**effect_params:**
```json
{
  "passive_aura": {
    "hp_increase": 100,
    "atk_increase": 100
  }
}
```

**hero_data:**
```json
{
  "active_ability": {
    "amount": 100,
    "keyword": "HERO_ACTIVE_DAMAGE"
  }
}
```

## Testing

1. **Restart your backend server** (to load the updated code)
2. **Start a new match** (to load cards with hero_data)
3. **Use hero ability** - the fallback message should be gone!

## Result

✅ Hero abilities will now read from `hero_data.active_ability`  
✅ No more "HERO_ACTIVE_FALLBACK_APPLIED" messages  
✅ Backwards compatible (still checks effect_params if hero_data not found)

