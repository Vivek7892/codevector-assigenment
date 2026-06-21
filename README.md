# Product Browser

Browse ~200,000 products (newest first) with category filtering and stable cursor-based pagination.

## Why keyset / cursor pagination?

Standard `OFFSET` pagination is **unstable**: if 50 rows are inserted while a user is on page 3, every subsequent page shifts by 50, causing duplicates or skipped items.

Keyset pagination uses the last-seen `(created_at, id)` pair as a bookmark. The query is:

```sql
WHERE (created_at < $1 OR (created_at = $1 AND id < $2))
ORDER BY created_at DESC, id DESC
LIMIT $3
```

This is also **fast** — it hits the `(created_at DESC, id DESC, category)` composite index instead of scanning and discarding rows like OFFSET does.

## Stack

| Layer    | Tech                        |
|----------|-----------------------------|
| Database | Supabase (Postgres)         |
| API      | FastAPI + asyncpg           |
| Frontend | Vanilla HTML/JS (static)    |
| Deploy   | Render (API + static site)  |

## Local setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure env
cp .env.example .env
# Edit .env — set DATABASE_URL to your Supabase connection string

# 3. Create schema  (run in Supabase SQL Editor or psql)
psql $DATABASE_URL < schema.sql

# 4. Seed 200,000 products (~30s)
python seed.py

# 5. Start the API
uvicorn main:app --reload

# 6. Open the UI
open frontend/index.html
```

## Deploy to Render + Supabase

### 1. Supabase — create the database

1. Create a free project at https://supabase.com
2. Go to **SQL Editor** and run `schema.sql`
3. Run `seed.py` locally pointed at the Supabase `DATABASE_URL`  
   (Project Settings → Database → URI connection string, **Session mode, port 5432**)

### 2. Render — deploy the API

1. Push this repo to GitHub
2. Go to https://render.com → **New → Blueprint** → connect your repo  
   Render will detect `render.yaml` and create both services automatically
3. In the `product-browser-api` service, set these environment variables:
   - `DATABASE_URL` — your Supabase connection string
   - `FRONTEND_URL` — the Render static site URL (e.g. `https://product-browser-ui.onrender.com`)

### 3. Point the frontend at the API

In `frontend/index.html` the API URL is read from `window.API_URL`.  
Set it by adding a `config.js` to the static site, or simply hardcode the Render API URL
in the `const API = ...` line before deploying:

```js
const API = "https://product-browser-api.onrender.com";
```

## API

| Endpoint | Description |
|---|---|
| `GET /products?limit=20&category=Books&cursor=<token>` | Paginated product list |
| `GET /categories` | All distinct categories |

`next_cursor` in the response is an opaque base64 token. Pass it as `cursor` on the next request. Omit it for the first page.

## Project structure

```
schema.sql          — DDL (Postgres table + index)
seed.py             — bulk-seeds 200k products
main.py             — FastAPI app (keyset pagination, asyncpg)
apply_schema.py     — helper to apply schema without psql on PATH
requirements.txt
.env.example
render.yaml         — Render Blueprint (API + static site)
frontend/
  index.html        — single-file UI (dark mode, skeletons, category pills)
```
