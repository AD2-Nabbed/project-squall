# Debugging API Issues

## "Failed to fetch" Error

This error typically means:
1. **Backend server is not running** - Check if uvicorn is running on port 8000
2. **CORS issue** - Check browser console for CORS errors
3. **Network connectivity** - Check if you can access http://127.0.0.1:8000

## How to Debug

1. **Check if backend is running:**
   ```bash
   netstat -ano | findstr :8000
   ```
   Or open: http://127.0.0.1:8000/docs (FastAPI docs)

2. **Check browser console:**
   - Open Developer Tools (F12)
   - Go to Console tab
   - Look for errors when clicking "Add to Deck"

3. **Check Network tab:**
   - Open Developer Tools (F12)
   - Go to Network tab
   - Try adding a card
   - Check the request:
     - Status code
     - Request URL
     - Response body

4. **Check backend logs:**
   - Look at the terminal where uvicorn is running
   - Check for error messages

## Common Issues

- **Backend not running**: Start with `uvicorn app.main:app --reload --port 8000`
- **Wrong port**: Make sure API_BASE in webapp/app.js matches backend port
- **CORS**: Backend should have CORS middleware enabled (it does)
- **Session token**: Make sure you're logged in

