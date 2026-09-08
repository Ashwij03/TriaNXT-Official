# TriaNXT API source-of-truth mode

The UI uses `VITE_API_URL` for the backend host. Set:

```env
VITE_API_URL=http://localhost:8000
```

After FastAPI login succeeds, the UI enables the API storage bridge. Business `localStorage` keys are treated as a browser cache/compatibility layer:

1. `GET /api/client-storage/` hydrates the browser cache from PostgreSQL.
2. Existing local business data missing on the server is bootstrapped once with `PUT /api/client-storage/{key}`.
3. Future `localStorage.setItem()` calls for business keys are mirrored to `PUT /api/client-storage/{key}`.
4. `localStorage.removeItem()` calls are mirrored to `DELETE /api/client-storage/{key}`.
5. Auth/session keys are excluded from the business-data bridge.

The durable source of truth is therefore the FastAPI `ctms_ui_storage` table, scoped by authenticated user.

## Engine

The Engine contains the `/api/client-storage/` router and creates the table automatically at startup. The explicit PostgreSQL migration is also available at:

`sql/11_ui_storage.sql`

CORS must allow the Vite origin, for example:

```env
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_CREDENTIALS=true
```

## Run

Start Engine:

```powershell
python -m uvicorn tria_engine.main:app --reload
```

Start UI:

```powershell
npm install
npm run dev
```

Open the browser Network tab and log in. You should see `/api/accounts/login/` followed by `/api/client-storage/` and subsequent API storage PUT/DELETE calls as the UI changes data.
