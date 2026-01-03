# Quick Launch Guide - Testing Hero Abilities

## Step 1: Install Dependencies (if not already done)

Make sure you're in the project root and have dependencies installed:
```powershell
pip install -r requirements.txt
```

## Step 2: Set Environment Variables

**In PowerShell:**
```powershell
$env:SUPABASE_URL = "https://xvxgkrittqgwqpuzryrf.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2eGdrcml0dHFnd3FwdXpyeXJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ3NTYxNCwiZXhwIjoyMDc5MDUxNjE0fQ.J8fhQeCzOoSZ3qNCR3hGxCNCWoaegmeVfUuju3lqO7k"
```

## Step 3: Start Backend Server

**Terminal 1 (PowerShell):**
```powershell
cd C:\Users\Nabbed\Documents\GitHub\project-squall
uvicorn app.main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

**Keep this terminal open!**

## Step 4: Start Frontend Server

**Terminal 2 (New PowerShell window):**
```powershell
cd C:\Users\Nabbed\Documents\GitHub\project-squall\frontend
python -m http.server 8080
```

You should see:
```
Serving HTTP on :: port 8080
```

## Step 5: Open Game in Browser

Navigate to: **http://localhost:8080**

## Step 6: Start a Match

1. Player ID: `d4ac398c-12a6-4cf3-836e-8ede11835029`
2. Deck ID: `909b20ce-a5a9-4cd5-8c00-7869ef23635b`
3. Click "Start Match"

## Step 7: Test Hero Abilities

### To Test Hero Active Ability:

1. **Summon Your Hero:**
   - Play 2 monsters (any monsters from your hand)
   - Tribute both monsters to summon your hero (6-star card)
   - Hero appears in the Hero Zone

2. **Use Hero Ability:**
   - Click the **"Hero Ability"** button
   - If the ability requires a target, select a target monster
   - The ability should execute

### Expected Behavior:

- **Flamecaller Hero**: Should deal 100 damage to target monster
- **Frost Warden Hero**: Should freeze target monster (prevents attack)
- Ability should only work once per turn
- Ability button should be disabled after use

### Troubleshooting:

- **Ability button disabled?** Make sure you have a hero on the field
- **Nothing happens?** Check browser console (F12) for errors
- **Backend errors?** Check Terminal 1 for error messages

