-- Migration: Remove foreign key constraint from players.id to users
-- This allows us to use our custom auth system instead of Supabase Auth

-- First, check if the constraint exists and drop it
ALTER TABLE players 
DROP CONSTRAINT IF EXISTS players_id_fkey;

-- Note: If you want to keep players.id as a UUID but not reference users,
-- the column should work fine. If you need to change the column type or
-- add a default, you can do that here as well.

-- Optional: If you want players.id to auto-generate UUIDs, uncomment this:
-- ALTER TABLE players 
-- ALTER COLUMN id SET DEFAULT gen_random_uuid();

