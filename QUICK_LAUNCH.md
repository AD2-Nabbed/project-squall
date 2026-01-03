# Quick Launch - Test Hero Abilities

## Summary
Your Supabase database is in the cloud - you just need the Python client library to connect (already installed ✅).

## Step 1: Start Backend Server

**Open Terminal 1 (PowerShell):**
```powershell
cd C:\Users\Nabbed\Documents\GitHub\project-squall
.\.venv\Scripts\Activate.ps1
$env:SUPABASE_URL = "https://xvxgkrittqgwqpuzryrf.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2eGdrcml0dHFnd3FwdXpyeXJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ3NTYxNCwiZXhwIjoyMDc5MDUxNjE0fQ.J8fhQeCzOoSZ3qNCR3hGxCNCWoaegmeVfUuju3lqO7k"
uvicorn app.main:app --reload --port 8000
```

Wait until you see: `INFO:     Uvicorn running on http://127.0.0.1:8000`

## Step 2: Start Frontend Server

**Open Terminal 2 (New PowerShell window):**
```powershell
cd C:\Users\Nabbed\Documents\GitHub\project-squall\frontend
python -m http.server 8080
```

Wait until you see: `Serving HTTP on :: port 8080`

## Step 3: Open Game

Open browser: **http://localhost:8080**

## Step 4: Start Match & Test Hero Ability

1. Player ID: `d4ac398c-12a6-4cf3-836e-8ede11835029`
2. Deck ID: `909b20ce-a5a9-4cd5-8c00-7869ef23635b`
3. Click "Start Match"
4. Play 2 monsters, then tribute them to summon your hero
5. Click "Hero Ability" button to test!

---

**Note:** The `supabase` Python package is just a client library - your actual database lives in the cloud at Supabase. The package lets your code talk to it.

