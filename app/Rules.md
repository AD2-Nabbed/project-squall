1. Match Structure

A match is 1v1. Each player has:

1500 HP

Deck

Hand

4 Monster Zones

4 Spell/Trap Zones

1 Hero Zone

Graveyard

Exile

Draw 5 cards at the start

Deck contains:

Monsters (Stars 1–5)

Spells

Traps

Exactly 1 Hero (always 6-star)

2. Hero Rules

Heroes are the only 6-star cards.

Must be drawn from deck.

Requires 2 tributes to play.

Enters its own Hero Zone, not a monster zone.

Enters face-up immediately.

Cannot attack.

Provides a passive aura that modifies gameplay.

Provides an activated ability usable once per turn during Main Phase.

Heroes fundamentally change the theme and effects of the player’s board and spells/traps.

3. Turn Structure
Start of Turn

Draw 2 cards.

All face-up monsters refresh (can_attack = True).

Resolve duration-based statuses.

Flip any monsters that were summoned last turn from face-down → face-up.

Phase becomes "main".

Main Phase Actions

These actions follow per-turn limits:

Action	Limit
Summon a monster (1–5 star)	1 per turn
Play a spell OR a trap	1 per turn (total)
Activate hero ability	1 per turn
Attack with monsters	Each monster once per turn
Direct attack	Only if opponent has no monsters
End turn	Ends player’s turn

Effects may increase these limits.

4. Summoning Rules
Stars 1–3

No tribute.

Enters face-down.

Cannot attack this turn.

Stars 4–5

Require 1 tribute.

Enters face-up.

Can attack immediately.

Tribute monster is sent to graveyard.

Hero (6-star)

Requires 2 tributes.

Enters face-up.

Activates passive immediately.

Tribute Restrictions

You cannot summon a monster and then use that monster as a tribute in the same turn unless an effect allows extra summons.

5. Face-Down Rules

Monsters summoned this turn are face-down unless tribute-summoned (4–5 star) or created face-up by effects.

Face-down means:

Cannot attack

Stats hidden from opponent

A face-down monster flips:

Automatically at the start of its controller’s next turn, or

When it is attacked

Once flipped face-up, it stays face-up permanently until it leaves the field.

Effects that prevent a monster from attacking do not flip it face-down; they simply mark it visually (e.g., “X” state).

6. Combat Rules
Simultaneous Damage

When a monster attacks another monster:

Both monsters deal their ATK to the other monster’s HP at the same time.

Death

Monsters reduced to 0 HP are destroyed and go to the graveyard.

Once Per Turn Attacks

Each monster may declare one attack per turn if:

face_up == True

can_attack == True

hp > 0

Attacking Face-Down Monsters

Allowed.
The defender flips face-up immediately, then combat resolves.

Overflow Damage

No overflow damage applies unless an effect specifically grants it.

7. Direct Attacks

A monster may attack the opposing player directly only if the opponent controls no monsters.

Damage dealt = monster’s ATK.

8. Spell Rules

Played from hand into graveyard after resolving.

Only one spell OR trap may be played per turn unless modified.

All spell effects are driven by database keywords and parameters.

Many spells require specific targets (monster or player).

9. Trap Rules

Played face-down into a spell/trap zone.

They do not activate when played.

They activate only when their trigger condition occurs.

Traps generally trigger on opponent actions:

Opponent plays a spell

Opponent summons a monster

Opponent attacks

A status is applied to your monster, etc.

After resolving, traps go to the graveyard.

10. Status System

Monsters may have multiple statuses, such as FROZEN, BURNING, HASTE, etc.

Statuses modify gameplay:

Disable attacking

Apply damage over time

Modify ATK/HP

Alter targeting

Modify turn timing

Statuses expire based on the duration system stored in their effect parameters.

11. Deck Reshuffling

When a player needs to draw but their deck is empty:

Shuffle their graveyard.

Graveyard becomes the new deck.

Graveyard becomes empty.

Drawing continues.

If both the deck and graveyard are empty:

Player simply does not draw, but does not lose the game.

12. Win Conditions

A player wins if:

Opponent HP ≤ 0

A card effect declares a win (future design)

If both players reach HP ≤ 0 from the same source → draw.

13. Action Limits Summary
Action	Limit
Monster Summon	1 per turn
Spell/Trap Play	1 per turn combined
Hero Ability	1 per turn
Monster Attacks	One per monster per turn
Direct Attacks	Only if opponent controls no monsters
End Turn	1 per turn
14. Monster Field Behavior

Face-down for 1 turn (1–3 star)

Immediately face-up on summon (4–5 star & hero)

Monsters do not revert to face-down once flipped

Effects that disable attacking simply set can_attack = False for the turn