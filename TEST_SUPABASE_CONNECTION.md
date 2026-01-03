# Troubleshooting Supabase Connection

## Error You're Seeing

```
getaddrinfo failed
Non-existent domain
```

This means your computer **cannot resolve the DNS name** for your Supabase database.

## Quick Checks

### 1. Check Your Internet Connection
```cmd
ping 8.8.8.8
```
If this fails, you have a network connectivity issue.

### 2. Check if Supabase URL is Correct
- Go to your Supabase dashboard: https://supabase.com/dashboard
- Check your project settings
- Verify the project URL matches: `xvxgkrittqgwqpuzryrf.supabase.co`

### 3. Try Different DNS Server
Sometimes your router's DNS fails. Try using Google DNS:

**Windows DNS Settings:**
1. Open Network Settings
2. Change adapter options
3. Right-click your connection → Properties
4. Select "Internet Protocol Version 4 (TCP/IPv4)" → Properties
5. Use these DNS servers:
   - Preferred: 8.8.8.8
   - Alternate: 8.8.4.4

### 4. Check if Supabase Project is Active
- Log into https://supabase.com/dashboard
- Verify the project exists and is not paused/deleted
- Check if the project URL has changed

## Alternative: Use IP Address (Temporary Workaround)

If DNS is the issue, you could temporarily use the IP address, but Supabase uses SSL certificates tied to the domain name, so this won't work for HTTPS connections.

## Most Likely Cause

Based on the error, either:
1. **Your internet/DNS is having issues** (most common)
2. **The Supabase project URL has changed** (check your dashboard)
3. **The Supabase project was deleted/paused** (check your dashboard)

