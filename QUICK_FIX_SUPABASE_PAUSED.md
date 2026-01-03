# Quick Fix: Supabase Project Paused

## What Happened
Your Supabase project was **paused**, which means:
- The database URL doesn't resolve (DNS fails)
- The backend can't connect to your database
- Starting a match fails with `getaddrinfo failed` error

## Solution ✅
**Unpause your project in the Supabase dashboard!**

## After Unpausing

### Option 1: Just Refresh and Retry
1. Refresh your browser (http://localhost:8080)
2. Try "Start Match" again
3. It should work now!

### Option 2: Restart Backend (Recommended)
1. In your backend terminal, press **Ctrl+C** to stop the server
2. Restart it:
   ```cmd
   uvicorn app.main:app --reload --port 8000
   ```
3. Then try "Start Match" in the browser

## Note
- Supabase projects can auto-pause after inactivity (free tier)
- When paused, the database URL becomes unreachable
- Just unpause and you're good to go!

