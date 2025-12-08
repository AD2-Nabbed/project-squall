# Project Squall – AI Instructions

- This is a card-battle engine that lives inside a future RPG.
- All card definitions (monsters, spells, traps, heroes) live in Supabase:
  - `cards`, `keywords`, `card_keywords`, `decks`, `deck_cards`, `npcs`, `matches`.
- DO NOT hardcode card effects per card name. Use `effect_tags` + `effect_params` 
  and keyword-based resolvers.
- Python backend is FastAPI in `app/main.py`, battle engine in `app/engine/*`.
- Battles must be future-proof:
  - New spells/traps/keywords should be addable by inserting rows in the DB,
    not rewriting the engine.
- Current focus:
  - Implement spell + trap resolution using keyword resolver.
  - Keep PVE/PVP-compatible: use `matches` table, `serialized_game_state` jsonb.

Always:
- Prefer small, incremental changes.
- Show full-file updates when refactoring a file.
- Keep compatibility with existing Supabase schema unless explicitly changing it.
