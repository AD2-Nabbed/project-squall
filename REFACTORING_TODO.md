# Refactoring TODO - Recommended Improvements

**Status:** All recommendations saved for future implementation
**Date Created:** After fixing hero ability syntax errors

---

## High Priority Refactorings

### 1. Extract Hero Ability Handler
**Location:** `app/main.py` lines 1467-1633
**Action:** Create `handle_activate_hero_ability()` in `app/engine/action_handlers.py`
**Benefits:**
- Reduce main.py size
- Improve testability
- Match existing pattern (spells/traps already extracted)

### 2. Create Effect Params Helper Function
**Location:** Multiple places in `app/main.py`
**Action:** Create `app/engine/effect_helpers.py` with:
- `parse_effect_params(card_dict: Dict) -> Dict`
- Handles JSON string parsing, nested effect_params, hero_data fallback
**Benefits:**
- DRY principle (Don't Repeat Yourself)
- Consistent parsing logic
- Easier to test and maintain

### 3. Create JSON Parsing Utility
**Location:** Multiple places (effect_params, hero_data, etc.)
**Action:** Create `_safe_json_parse(value: Any, default: Any = {}) -> Any` helper
**Benefits:**
- Remove repeated try/except blocks
- Consistent error handling
- Cleaner code

---

## Medium Priority Refactorings

### 4. Extract Other Action Handlers
**Actions to extract from `app/main.py`:**
- `handle_play_monster()` - Lines ~820-1020
- `handle_attack_monster()` - Lines ~1638-2100
- `handle_attack_player()` - Lines ~2100-2200
- `handle_play_trap()` - Lines ~1300-1400

**Target:** `app/engine/action_handlers.py`
**Benefits:**
- Reduce main.py from 3,108 lines to ~1,500 lines
- Better organization
- Easier to test individual actions

### 5. Extract Target Building Logic
**Location:** Hero ability handler, spell handlers
**Action:** Create `_build_ability_targets(game_state, payload, opponent_idx) -> Dict`
**Benefits:**
- Reusable targeting logic
- Consistent auto-targeting behavior
- Easier to modify targeting rules

### 6. Create Helper Module for Game State Updates
**Action:** Create `app/engine/game_state_helpers.py` (already exists, but extend it)
**Functions to add:**
- `update_player_state(game_state, player_index, updates)`
- `sync_game_state_to_db(match_id, game_state)`
**Benefits:**
- Reduce boilerplate
- Ensure consistent state updates
- Centralize database sync logic

---

## Low Priority / Future Improvements

### 7. Split main.py into Router Modules
**Structure:**
- `app/api/battle.py` - Battle endpoints
- `app/api/health.py` - Health/test endpoints
- `app/main.py` - App initialization and router registration
**Benefits:**
- Better organization for larger codebase
- Easier to find specific endpoints
- Supports feature growth

### 8. Add Comprehensive Type Hints
**Location:** All action handlers, helpers
**Benefits:**
- Better IDE support
- Catch type errors early
- Self-documenting code
- Enable mypy type checking

### 9. Extract Turn State Management
**Location:** Scattered throughout action handlers
**Action:** Create `TurnStateManager` class or helper functions
**Benefits:**
- Centralized turn limit tracking
- Easier to modify turn rules
- Reduce duplication

### 10. Create Constants Module
**Action:** Create `app/engine/constants.py`
**Contents:**
- Player HP (1500)
- Zone counts (4 monster zones, 4 spell/trap zones)
- Turn limits (1 summon, 1 spell/trap, etc.)
**Benefits:**
- Single source of truth
- Easy to balance game
- Clear configuration

---

## Implementation Order

1. ✅ **DONE:** Fix syntax errors (hero abilities)
2. **NEXT:** Test hero abilities in game
3. **THEN:** Extract hero ability handler (#1)
4. **THEN:** Create effect_params helper (#2)
5. **THEN:** Create JSON parsing utility (#3)
6. **THEN:** Extract other action handlers (#4)
7. **THEN:** Remaining improvements as needed

---

## Notes

- All refactorings should maintain backward compatibility
- Test after each refactoring step
- Keep existing API contracts unchanged
- Document any breaking changes (none expected)

