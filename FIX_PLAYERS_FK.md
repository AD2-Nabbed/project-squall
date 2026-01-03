# Fix Players Table Foreign Key Issue

## Problem

The `players` table has a foreign key constraint `players_id_fkey` that references `users.id`. This constraint prevents us from creating players directly because we're using a custom auth system instead of Supabase Auth.

## Solution

Run the migration script to remove the foreign key constraint:

**In Supabase SQL Editor**, run:
```sql
ALTER TABLE players 
DROP CONSTRAINT IF EXISTS players_id_fkey;
```

This will remove the constraint and allow us to create players directly.

## Alternative: Use Supabase Auth

If you prefer to use Supabase's built-in authentication system instead of our custom auth, we would need to:
1. Use Supabase Auth for user registration/login
2. Keep the foreign key constraint
3. Create users through Supabase Auth API

But since you wanted a custom auth system, removing the constraint is the right approach.

## After Running Migration

Once you've run the migration, try registering again. The registration should work correctly.

