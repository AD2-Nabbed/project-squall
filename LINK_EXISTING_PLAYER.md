# Link Existing Player to Auth System

Your existing player account needs to be linked to the new auth system.

## Option 1: Using Python Script (Recommended)

Run the helper script:

```bash
# Make sure you're in the project root and have environment variables set
python link_existing_player.py nabbed yourpassword d4ac398c-12a6-4cf3-836e-8ede11835029
```

This will:
1. Verify your player exists
2. Check if the username is available
3. Create an auth account linked to your existing player

## Option 2: Manual SQL (Alternative)

If you prefer SQL, run this in Supabase SQL Editor:

```sql
-- Replace 'nabbed' with your desired username
-- Replace 'yourpassword' with your desired password
-- The password will need to be hashed with bcrypt

-- First, generate a bcrypt hash for your password (use the Python script or online tool)
-- Example hash for password "test": $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyY3xXGKX5rq

INSERT INTO auth (username, password_hash, player_id)
VALUES (
  'nabbed',
  '$2b$12$YOUR_BCRYPT_HASH_HERE',  -- Replace with actual bcrypt hash
  'd4ac398c-12a6-4cf3-836e-8ede11835029'
);
```

**Note**: You'll need to generate a bcrypt hash for your password. The Python script does this automatically.

## After Linking

Once you've linked your account, you can:
1. Login with your new username and password
2. Access all your existing decks and cards
3. Continue using your existing player account

Your player ID, decks, and cards remain unchanged - we're just adding authentication on top!

