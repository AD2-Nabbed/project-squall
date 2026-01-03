# Quick Start - Command Prompt (CMD)

You're using **CMD**, not PowerShell. Use these commands:

## Option 1: Use the Batch Files (Easiest!)

**Terminal 1 - Backend:**
Just double-click: `START_BACKEND_CMD.bat`

**Terminal 2 - Frontend:**
Just double-click: `START_FRONTEND_CMD.bat`

---

## Option 2: Manual Commands

### Terminal 1 - Start Backend:

```cmd
cd C:\Users\Nabbed\Documents\GitHub\project-squall
.venv\Scripts\activate.bat
set SUPABASE_URL=https://xvxgkrittqgwqpuzryrf.supabase.co
set SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2eGdrcml0dHFnd3FwdXpyeXJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ3NTYxNCwiZXhwIjoyMDc5MDUxNjE0fQ.J8fhQeCzOoSZ3qNCR3hGxCNCWoaegmeVfUuju3lqO7k
uvicorn app.main:app --reload --port 8000
```

### Terminal 2 - Start Frontend:

```cmd
cd C:\Users\Nabbed\Documents\GitHub\project-squall\frontend
python -m http.server 8080
```

### Then Open Browser:
http://localhost:8080

---

## Important Notes:

- **You were in the wrong directory!** You need to be in `C:\Users\Nabbed\Documents\GitHub\project-squall`
- **CMD uses `set` not `$env:`** (that's PowerShell syntax)
- **CMD uses `activate.bat` not `Activate.ps1`** (that's PowerShell)
- The `.bat` files I created will do everything automatically!

