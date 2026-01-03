# Fixed: Hero Data Complete Support

## Issue
`hero_data` wasn't being preserved when cards were created and serialized because:
1. `CardInstance` dataclass didn't have a `hero_data` field
2. `new_from_definition()` wasn't copying `hero_data`
3. `card_instance_to_dict()` wasn't including `hero_data`

## Changes Made

### 1. `app/engine/models.py`
- Added `hero_data: Optional[dict] = None` field to `CardInstance` dataclass
- Updated `new_from_definition()` to copy `hero_data` from `card_def`

### 2. `app/main.py`
- Updated `card_instance_to_dict()` to include `hero_data` in the serialized dict

### 3. `app/db/decks.py` (already done)
- Added `hero_data` to database SELECT query
- Added `hero_data` to card definition dict

### 4. `app/main.py` hero ability handler (already done)
- Updated to check `hero_data.active_ability` first

## Next Steps

1. **Restart backend server** (to load updated code)
2. **Start a NEW match** (to load cards with hero_data from database)
3. **Test hero ability** - fallback message should be gone!

## Result

✅ `hero_data` is now preserved through the entire card lifecycle:
- Loaded from database → Included in card_def
- Copied to CardInstance → Stored in dataclass
- Serialized to dict → Included in game state
- Available in hero ability handler → Can read active_ability

The fallback message should disappear once you restart and start a new match!

