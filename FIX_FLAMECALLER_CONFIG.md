# Fix Flamecaller Hero Configuration

## Current Issue
Your Flamecaller hero is using the fallback because the `active_ability` isn't configured in the database.

## How to Fix

1. **Go to your Supabase Dashboard**
   - Navigate to: https://supabase.com/dashboard
   - Select your project
   - Go to the Table Editor
   - Open the `cards` table

2. **Find the Flamecaller Hero Card**
   - Filter by `name = "Flamecaller"` or search for it
   - Or filter by `card_type = "hero"` and find Flamecaller

3. **Update the `effect_params` field**
   
   **Current value (probably empty or incomplete):**
   ```json
   {}
   ```
   
   **Should be:**
   ```json
   {
     "passive_aura": {
       "atk_increase": 100,
       "hp_increase": 100
     },
     "active_ability": {
       "keyword": "HERO_ACTIVE_DAMAGE",
       "amount": 100
     }
   }
   ```

4. **Save the changes**

5. **Start a new match**
   - The fallback message should disappear
   - Logs will show proper ability activation

## Verification

After updating, when you use the hero ability, you should see:
- ✅ No "HERO_ACTIVE_FALLBACK_APPLIED" message
- ✅ Clean activation log
- ✅ Ability still works exactly the same (but now properly configured)

## Note
The ability is already working - this just removes the fallback warning and ensures it uses the database configuration instead of the code fallback.

