# TriaNXT UI — FastAPI API mode

## Configuration

Vite reads the backend URL from `VITE_API_URL`. Development is preconfigured as:

```env
VITE_API_URL=http://localhost:8000
```

Change that value in the appropriate Vite `.env*` file when the backend moves. Do not hard-code the backend host in feature services.

## Run

```powershell
npm install
npm run dev
```

The UI uses port 3000. The FastAPI Engine must be running on port 8000.

## Authentication

Login is now a real API call:

`POST /api/accounts/login/`

The Engine returns an HttpOnly `sessionid` cookie. The shared API client sends `credentials: include` on subsequent requests.

## CORS

The Engine must allow the UI origin, for example:

```env
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_CREDENTIALS=true
```

## Important architecture note

The current Engine does not expose every CTMS feature as an API. Modules that have no corresponding backend endpoint cannot be made API-backed by changing the frontend URL alone; those services must be migrated together with their FastAPI routers.
