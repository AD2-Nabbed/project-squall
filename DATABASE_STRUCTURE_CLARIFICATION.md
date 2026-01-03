# Database Structure Clarification

## Card Types and Their Field Usage

### Heroes

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

---

### Spells

**effect_tags:**
```json
[
  "SPELL_DAMAGE_MONSTER"
]
```

**effect_params:**
```json
{
  "effects": [
    {
      "amount": 150,
      "target": "ENEMY_MONSTER",
      "keyword": "SPELL_DAMAGE_MONSTER",
      "overflow_to_player": true
    }
  ]
}
```

**Notes:**
- `effect_tags` is an array of keyword strings (for quick filtering/searching)
- `effect_params.effects` is an array of effect objects with full details
- The `keyword` in `effect_params.effects[]` should match the tags in `effect_tags`
- The resolver uses `effect_params.effects[]` to execute the effects

---

### Traps

Similar structure to spells:
- `effect_tags`: Array of keyword strings
- `effect_params.effects`: Array of effect objects with full details

---

### Monsters

- `effect_tags`: Array of keyword strings (for abilities)
- `effect_params`: Contains monster-specific effect data
- Effects are resolved using the keyword system

---

## Summary

| Card Type | effect_params | effect_tags | hero_data |
|-----------|---------------|-------------|-----------|
| **Hero** | passive_aura | Not used for abilities | active_ability |
| **Spell** | effects array | Keyword array | N/A |
| **Trap** | effects array | Keyword array | N/A |
| **Monster** | Effect data | Keyword array | N/A |

## Key Points

1. **Heroes are special**: They use `hero_data` for active abilities, `effect_params` for passive auras
2. **Spells/Traps/Monsters**: Use `effect_tags` for keywords and `effect_params.effects[]` for detailed effect data
3. **effect_tags**: Used for filtering/searching (which cards have which abilities)
4. **effect_params.effects[]**: Used by the resolver to actually execute effects
5. **Keywords should match**: The keyword in `effect_params.effects[].keyword` should match a tag in `effect_tags`

