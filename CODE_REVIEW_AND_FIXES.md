# Code Review & Fixes for Project Squall

## Critical Issues Found

### 1. **Hero Active Ability Syntax Errors** ⚠️ CRITICAL - **FIXED**
**Location:** `app/main.py` lines 1494, 1578, 934-951, 2035, 2050

**Issues Found:**
- Line 1494: Incorrect indentation - `if not found:` was indented 4 spaces too far
- Line 1578: `else:` block incorrectly placed inside the `if ability_keyword:` block
- Line 934-951: Incorrect indentation in PLAY_MONSTER handler
- Lines 2035, 2050: Missing indentation in else blocks for combat logic

**Status:** ✅ All syntax errors fixed - file now compiles successfully
**Impact:** These errors prevented hero abilities from working and would cause runtime crashes

### 2. **Overly Complex effect_params Parsing**
**Location:** `app/main.py` lines 1518-1540

**Issues:**
- Repeated JSON parsing logic (appears in multiple places)
- Complex nested conditionals for handling different data structures
- Hard to maintain and test

**Recommendation:** Extract to helper function `_parse_effect_params(card_dict: Dict) -> Dict`

### 3. **Hero Ability Logic Complexity**
**Location:** `app/main.py` lines 1542-1601

**Issues:**
- 60+ lines of nested conditionals for parsing hero ability
- Multiple fallback paths make it hard to follow
- Logic for building hero_ability_card is convoluted

**Recommendation:** Extract to helper function `_build_hero_ability_card(hero: Dict, effect_params: Dict) -> Dict`

### 4. **Large main.py File**
**Issue:** `app/main.py` is 3,108 lines - too large for maintainability

**Recommendations:**
- Extract action handlers to separate modules (like `action_handlers.py` for spells/traps)
- Move hero ability logic to `app/engine/action_handlers.py`
- Consider splitting battle actions into separate router files

## Code Simplification Opportunities

### 5. **Repeated Pattern: JSON Parsing**
**Pattern seen in:** Multiple locations
```python
if isinstance(effect_params, str):
    try:
        import json
        effect_params = json.loads(effect_params)
    except:
        effect_params = {}
```

**Recommendation:** Create utility function:
```python
def _safe_json_parse(value: Any, default: Any = {}) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return default
    return value
```

### 6. **Repeated Pattern: Player Index Conversion**
**Pattern:** `str(player_index)` appears many times

**Recommendation:** Use a helper or consistent key access pattern

### 7. **Complex Target Building Logic**
**Location:** `app/main.py` lines 1485-1516

**Issue:** Auto-targeting logic is embedded in the handler

**Recommendation:** Extract to `_build_ability_targets(game_state, payload, opponent_idx) -> Dict`

## Future-Proofing Recommendations

### 8. **Action Handler Extraction**
**Current:** All actions in one massive function
**Recommended:** Extract each action type to `app/engine/action_handlers.py`

Already have:
- `handle_play_spell`
- `handle_activate_trap`

Should add:
- `handle_activate_hero_ability`
- `handle_play_monster`
- `handle_attack_monster`
- etc.

### 9. **Effect Params Helper Module**
Create `app/engine/effect_helpers.py` with:
- `parse_effect_params(card: Dict) -> Dict`
- `safe_json_parse(value: Any) -> Any`
- `normalize_effect_params(effect_params: Any) -> Dict`

### 10. **Type Hints**
Add more type hints to improve IDE support and catch errors early

## Implementation Priority

1. **HIGH:** Fix syntax errors (hero abilities broken)
2. **HIGH:** Extract hero ability handler function
3. **MEDIUM:** Extract effect_params parsing helpers
4. **MEDIUM:** Extract JSON parsing utility
5. **LOW:** Refactor large functions (can be done incrementally)

