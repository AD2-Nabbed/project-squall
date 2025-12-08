# Quick Start Guide - Play Your First Match

## Prerequisites

- Python 3.8+ installed
- Supabase credentials set up
- Your Player ID and Deck ID ready

## Step-by-Step Setup

### Step 1: Install Dependencies

Open a terminal (CMD or PowerShell) in the project root:

**For CMD (Command Prompt):**
```cmd
cd C:\Users\Nabbed\Documents\GitHub\project-squall
.\.venv\Scripts\activate.bat
pip install -r requirements.txt
```

**For PowerShell:**
```powershell
cd C:\Users\Nabbed\Documents\GitHub\project-squall
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 2: Set Environment Variables

**For CMD (Command Prompt):**
```cmd
set SUPABASE_URL=https://xvxgkrittqgwqpuzryrf.supabase.co
set SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2eGdrcml0dHFnd3FwdXpyeXJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ3NTYxNCwiZXhwIjoyMDc5MDUxNjE0fQ.J8fhQeCzOoSZ3qNCR3hGxCNCWoaegmeVfUuju3lqO7k
```

**For PowerShell:**
```powershell
$env:SUPABASE_URL = "https://xvxgkrittqgwqpuzryrf.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2eGdrcml0dHFnd3FwdXpyeXJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ3NTYxNCwiZXhwIjoyMDc5MDUxNjE0fQ.J8fhQeCzOoSZ3qNCR3hGxCNCWoaegmeVfUuju3lqO7k"
```

**Note**: These only last for the current terminal session. If you close the terminal, you'll need to set them again.

### Step 3: Start the Backend Server

In the same terminal (with venv activated and env vars set):

```cmd
uvicorn app.main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Keep this terminal open!** The server needs to keep running.

### Step 4: Start the Frontend Server

Open a **NEW terminal window** (keep the backend running):

```cmd
cd C:\Users\Nabbed\Documents\GitHub\project-squall\frontend
python -m http.server 8080
```

You should see:
```
Serving HTTP on :: port 8080
```

### Step 5: Open the Game in Your Browser

Open your web browser and go to:

```
http://localhost:8080
```

You should see the Project Squall game interface.

### Step 6: Start a Match

1. In the setup panel, you should see your Player ID and Deck ID pre-filled:
   - Player ID: `d4ac398c-12a6-4cf3-836e-8ede11835029`
   - Deck ID: `909b20ce-a5a9-4cd5-8c00-7869ef23635b`

2. Click the **"Start Match"** button

3. The game board should appear showing:
   - Opponent area (top)
   - Your zones (middle)
   - Your hand (bottom)
   - Action buttons

### Step 7: Play Your First Turn

#### A. Play a Monster

1. Look at your hand - you should see cards like "Shade Hound", "Sprite of the Woods", etc.
2. Click **"Play Monster"** button
3. A modal will show available monsters from your hand
4. Click on a monster (e.g., "Shade Hound")
5. The monster will be placed face-down on the field (1-3 star monsters enter face-down)

#### B. Set a Trap (Optional)

1. If you have a trap in hand, click **"Set Trap"**
2. Select a trap from the modal
3. Click on an empty spell/trap zone (0-3)
4. The trap will be set face-down

#### C. End Your Turn

1. Click **"End Turn"** button
2. This will:
   - Draw 2 cards
   - Flip your face-down monsters face-up
   - Refresh attack permissions
   - Switch to opponent's turn

### Step 8: Continue Playing

- **Play more monsters** - Build your board
- **Play spells** - Use spell effects
- **Attack** - Once you have face-up monsters, use "Attack" to battle
- **Summon Hero** - When you have 2 monsters on field, you can tribute them to summon your hero (6-star)

## Troubleshooting

### Backend won't start
- Make sure you're in the project root directory
- Check that venv is activated (you should see `(.venv)` in your prompt)
- Verify environment variables are set: `echo $env:SUPABASE_URL`

### Frontend won't load
- Make sure you're in the `frontend` directory when running the HTTP server
- Try a different port: `python -m http.server 8081`
- Check that backend is running on port 8000

### "Internal Server Error" when starting match
- Check the backend terminal for error messages
- Verify your Player ID and Deck ID are correct
- Make sure Supabase credentials are set in the backend terminal

### Cards not showing
- This is normal - we're using text-based cards for now
- Cards will show as text with name, type, and stats

### Can't see opponent actions
- The opponent is an NPC that acts automatically
- Watch the game log for opponent actions
- Opponent will play cards and attack on their turn

## Quick Reference

**Your Info:**
- Player ID: `d4ac398c-12a6-4cf3-836e-8ede11835029`
- Deck ID: `909b20ce-a5a9-4cd5-8c00-7869ef23635b`

**URLs:**
- Backend API: `http://127.0.0.1:8000`
- Frontend UI: `http://localhost:8080`
- API Docs: `http://127.0.0.1:8000/docs`

**Terminal Commands (CMD):**
```cmd
REM Backend (Terminal 1)
cd C:\Users\Nabbed\Documents\GitHub\project-squall
.\.venv\Scripts\activate.bat
set SUPABASE_URL=https://xvxgkrittqgwqpuzryrf.supabase.co
set SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2eGdrcml0dHFnd3FwdXpyeXJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ3NTYxNCwiZXhwIjoyMDc5MDUxNjE0fQ.J8fhQeCzOoSZ3qNCR3hGxCNCWoaegmeVfUuju3lqO7k
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

REM Frontend (Terminal 2)
cd C:\Users\Nabbed\Documents\GitHub\project-squall\frontend
python -m http.server 8080
```

**Terminal Commands (PowerShell):**
```powershell
# Backend (Terminal 1)
cd C:\Users\Nabbed\Documents\GitHub\project-squall
.\.venv\Scripts\Activate.ps1
$env:SUPABASE_URL = "https://xvxgkrittqgwqpuzryrf.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2eGdrcml0dHFnd3FwdXpyeXJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzQ3NTYxNCwiZXhwIjoyMDc5MDUxNjE0fQ.J8fhQeCzOoSZ3qNCR3hGxCNCWoaegmeVfUuju3lqO7k"
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (Terminal 2)
cd C:\Users\Nabbed\Documents\GitHub\project-squall\frontend
python -m http.server 8080
```

## Next Steps

Once you're comfortable with the basic flow:
- Try different card combinations
- Test trap triggers (set a counter trap, opponent plays spell)
- Summon your hero and see element transformation
- Test hero abilities
- Experiment with different deck builds

Enjoy playing! 🎮

