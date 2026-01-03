-- Migration: Create auth table for user authentication
-- Run this in your Supabase SQL editor

CREATE TABLE IF NOT EXISTS auth (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast username lookups
CREATE INDEX IF NOT EXISTS idx_auth_username ON auth(username);

-- Index for player_id lookups
CREATE INDEX IF NOT EXISTS idx_auth_player_id ON auth(player_id);

-- Add comment
COMMENT ON TABLE auth IS 'User authentication table linking usernames to players';

