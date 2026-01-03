# Deck Building Rules

Based on `app/Rules.md`, here are the deck building rules:

## Current Rules (From Rules.md)

1. **Hero Requirement: Exactly 1 Hero**
   - Must be exactly 1 Hero card (always 6-star)
   - Heroes are the only 6-star cards

2. **Deck Contents:**
   - Monsters (Stars 1–5)
   - Spells
   - Traps
   - Exactly 1 Hero (always 6-star)

## Not Specified in Rules

The following rules are **NOT** specified in the current rules document:
- ❓ Minimum deck size
- ❓ Maximum deck size  
- ❓ Card copy limits (how many copies of each card)

## Current Implementation Status

**⚠️ NO VALIDATION IMPLEMENTED**

Currently, the codebase does NOT validate decks when:
- Creating decks
- Editing decks
- Starting matches

The system will accept any deck configuration, including:
- Decks with 0 heroes
- Decks with 2+ heroes
- Decks with any number of cards
- Decks with unlimited copies of any card

## Recommended Deck Validation Rules

If you want to add validation, here are common card game conventions:

### Suggested Rules:
1. **Minimum Deck Size:** 30-40 cards (typical for card games)
2. **Maximum Deck Size:** 60 cards (common limit)
3. **Card Copy Limits:** 
   - 3 copies per card (common limit)
   - Heroes: 1 copy (already required)
4. **Hero Requirement:** Exactly 1 hero (from rules)

Would you like me to implement deck validation with these rules?

