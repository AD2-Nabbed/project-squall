# Hero Database Structure

## Hero Passive Aura

Add to the hero card's `effect_params` JSON field:

```json
{
  "passive_aura": {
    "atk_increase": 100,
    "hp_increase": 100
  }
}
```

**Examples:**
- **Flamecaller**: `{"passive_aura": {"atk_increase": 100, "hp_increase": 100}}`
- **Frost Warden**: `{"passive_aura": {"atk_increase": 0, "hp_increase": 200}}`

## Hero Active Ability

**Option 1: Using `active_ability` object (Recommended)**

Add to the hero card's `effect_params` JSON field:

```json
{
  "active_ability": {
    "keyword": "HERO_ACTIVE_DAMAGE",
    "amount": 100
  }
}
```

**Option 2: Using existing `effects` array (Backwards compatible)**

Add to the hero card's `effect_params` JSON field:

```json
{
  "effects": [
    {
      "keyword": "HERO_ACTIVE_DAMAGE",
      "amount": 100
    }
  ]
}
```

**Available Keywords:**
- `"HERO_ACTIVE_DAMAGE"` - deals damage to target monster (requires `amount` param)
- `"HERO_ACTIVE_FREEZE"` - freezes target monster (no params needed)

**Examples:**
- **Flamecaller** (Option 1): 
  - `effect_params`: `{"active_ability": {"keyword": "HERO_ACTIVE_DAMAGE", "amount": 100}}`
  
- **Flamecaller** (Option 2):
  - `effect_params`: `{"effects": [{"keyword": "HERO_ACTIVE_DAMAGE", "amount": 100}]}`
  
- **Frost Warden** (Option 1):
  - `effect_params`: `{"active_ability": {"keyword": "HERO_ACTIVE_FREEZE"}}`
  
- **Frost Warden** (Option 2):
  - `effect_params`: `{"effects": [{"keyword": "HERO_ACTIVE_FREEZE"}]}`

## Combined Example (Flamecaller)

```json
{
  "effect_params": {
    "passive_aura": {
      "atk_increase": 100,
      "hp_increase": 100
    },
    "active_ability": {
      "keyword": "HERO_ACTIVE_DAMAGE",
      "amount": 100
    }
  }
}
```

## Combined Example (Frost Warden)

```json
{
  "effect_params": {
    "passive_aura": {
      "atk_increase": 0,
      "hp_increase": 200
    },
    "active_ability": {
      "keyword": "HERO_ACTIVE_FREEZE"
    }
  }
}
```

## Notes

- `effect_tags` is **not required** for hero abilities - the keyword is read from `effect_params.active_ability.keyword` or `effect_params.effects[].keyword`
- The code will automatically use the existing resolver system, so any new `HERO_ACTIVE_*` keywords you add to the resolver will work automatically
- Passive aura is applied automatically when the hero is summoned and when new monsters are summoned
- Active ability requires a target monster to be selected by the player

