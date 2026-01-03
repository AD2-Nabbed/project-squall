# Testing Hero Abilities - Step by Step Guide

## Prerequisites
✅ Backend server running on http://127.0.0.1:8000  
✅ Frontend server running on http://localhost:8080  
✅ Game loaded in browser

---

## How to Test Hero Active Abilities

### Step 1: Start a Match

1. Open browser: http://localhost:8080
2. Enter your Player ID: `d4ac398c-12a6-4cf3-836e-8ede11835029`
3. Enter your Deck ID: `909b20ce-a5a9-4cd5-8c00-7869ef23635b`
4. Click **"Start Match"**

### Step 2: Summon Your Hero

To use a hero ability, you first need to summon your hero:

1. **Play 2 monsters** from your hand (any monsters will work)
   - Click a monster card in your hand
   - Click **"Play Monster"** button
   - Select an empty monster zone
   - Repeat with a second monster

2. **Summon the Hero:**
   - Look for your hero card in your hand (it's the 6-star card)
   - Click the hero card
   - Click **"Play Monster"** button
   - You'll be prompted to select 2 tribute monsters
   - Select the 2 monsters you just played
   - Confirm the tributes
   - The hero will be placed in the Hero Zone

### Step 3: Use Hero Active Ability

Once your hero is on the field:

1. **Click the "Hero Ability" button** (in the action panel)
2. **Select a target** (if the ability requires one):
   - For damage abilities: Select an enemy monster
   - For freeze abilities: Select an enemy monster
   - The UI will show available targets
3. **Confirm the ability use**

### Step 4: Verify the Ability Worked

Check the game log and game board:

**For Flamecaller (damage ability):**
- Enemy monster's HP should decrease by 100
- Game log should show "ACTIVATE_HERO_ABILITY" event
- Log should show damage was dealt

**For Frost Warden (freeze ability):**
- Target monster should be frozen (cannot attack)
- Game log should show "ACTIVATE_HERO_ABILITY" event
- Log should show freeze status was applied

### Step 5: Verify Per-Turn Limit

1. Try to use the hero ability again in the same turn
2. **Expected:** Button should be disabled or show an error
3. **After ending turn and starting new turn:** Ability should be available again

---

## Expected Behaviors

✅ Hero ability button appears when hero is on field  
✅ Ability executes when clicked (with valid target if needed)  
✅ Ability effects apply correctly (damage/freeze/etc.)  
✅ Ability can only be used once per turn  
✅ Game log shows ability activation  
✅ Ability button refreshes next turn  

---

## Troubleshooting

### Hero Ability Button Doesn't Appear
- **Check:** Is your hero actually on the field? (Check Hero Zone)
- **Fix:** Make sure you successfully summoned the hero with 2 tributes

### Ability Doesn't Execute
- **Check browser console (F12):** Look for JavaScript errors
- **Check backend terminal:** Look for Python errors
- **Verify:** Make sure you selected a valid target (if required)

### Ability Executes But Nothing Happens
- **Check game log:** See if effects are being logged
- **Check target:** For damage abilities, verify target monster's HP changed
- **Check backend logs:** Look for "ACTIVATE_HERO_ABILITY" log entries

### Ability Can Be Used Multiple Times Per Turn
- **Bug:** This shouldn't happen after our fixes
- **Check:** Backend terminal for any errors
- **Report:** If this occurs, there may be a turn state tracking issue

---

## Testing Checklist

- [ ] Can summon hero with 2 tributes
- [ ] Hero Ability button appears when hero is on field
- [ ] Can click Hero Ability button
- [ ] Can select target (if required)
- [ ] Ability executes successfully
- [ ] Effects apply correctly (damage/freeze/etc.)
- [ ] Game log shows ability activation
- [ ] Ability button is disabled after use (same turn)
- [ ] Ability button is enabled again next turn
- [ ] No errors in browser console
- [ ] No errors in backend terminal

---

## Reporting Issues

If hero abilities don't work:

1. **Check browser console (F12 → Console tab)**
   - Copy any error messages

2. **Check backend terminal**
   - Copy any error tracebacks

3. **Check game state:**
   - Open browser console
   - Type: `currentGameState`
   - Check if hero exists: `currentGameState.players["1"].hero`

4. **Report:**
   - What hero you're using
   - What ability you're trying to use
   - Error messages (if any)
   - Screenshot of game state (if possible)

