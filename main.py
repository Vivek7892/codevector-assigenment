"""
Product browsing API — keyset (cursor) pagination.

Supports both MySQL (local dev, aiomysql) and Postgres (Supabase, asyncpg).
Set DATABASE_URL to either:
  mysql://user:pass@host:port/dbname
  postgresql://user:pass@host:port/dbname
"""

import base64
import json
import os
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse

import aiomysql
import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

# ---------------------------------------------------------------------------
# Detect driver from DATABASE_URL (or fall back to MySQL env vars)
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "")
_scheme = urlparse(DATABASE_URL).scheme if DATABASE_URL else "mysql"
USE_POSTGRES = _scheme in ("postgresql", "postgres")

pool = None  # aiomysql.Pool or asyncpg.Pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    if USE_POSTGRES:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    else:
        # parse mysql://user:pass@host:port/db  OR fall back to DB_* vars
        if DATABASE_URL:
            p = urlparse(DATABASE_URL)
            host, port, user, password, db = (
                p.hostname, p.port or 3306, p.username, p.password, p.path.lstrip("/")
            )
        else:
            host     = os.getenv("DB_HOST", "localhost")
            port     = int(os.getenv("DB_PORT", 3306))
            user     = os.getenv("DB_USER", "root")
            password = os.getenv("DB_PASSWORD", "")
            db       = os.getenv("DB_NAME", "products_db")

        pool = await aiomysql.create_pool(
            host=host, port=port, user=user, password=password,
            db=db, autocommit=True, minsize=2, maxsize=10,
        )
    yield
    if USE_POSTGRES:
        await pool.close()
    else:
        pool.close()
        await pool.wait_closed()


app = FastAPI(title="Product Browser", lifespan=lifespan)

frontend_url = os.getenv("FRONTEND_URL", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url] if frontend_url != "*" else ["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------

def encode_cursor(created_at: str, row_id: int) -> str:
    return base64.urlsafe_b64encode(
        json.dumps({"ca": created_at, "id": row_id}, separators=(",", ":")).encode()
    ).decode()


def decode_cursor(token: str) -> tuple[str, int]:
    try:
        p = json.loads(base64.urlsafe_b64decode(token.encode()))
        return p["ca"], int(p["id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")


# ---------------------------------------------------------------------------
# DB helpers (abstract over the two drivers)
# ---------------------------------------------------------------------------

async def db_fetch(query: str, args: list) -> list[dict]:
    if USE_POSTGRES:
        # asyncpg uses $1,$2,... placeholders
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]
    else:
        # aiomysql uses %s placeholders
        pg_query = _pg_to_mysql(query)
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(pg_query, args)
                return await cur.fetchall()


def _pg_to_mysql(query: str) -> str:
    """Replace $1, $2, … with %s for aiomysql."""
    import re
    return re.sub(r"\$\d+", "%s", query)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/products")
async def list_products(
    category: Optional[str] = Query(None),
    cursor:   Optional[str] = Query(None),
    limit:    int           = Query(20, ge=1, le=100),
):
    args: list = []
    conditions: list[str] = []

    if category:
        args.append(category)
        conditions.append(f"category = ${len(args)}")

    if cursor:
        ca, rid = decode_cursor(cursor)
        args += [ca, ca, rid]
        n = len(args)
        conditions.append(f"(created_at < ${n-2} OR (created_at = ${n-1} AND id < ${n}))")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    args.append(limit)

    query = f"""
        SELECT id, name, category, price, created_at, updated_at
        FROM   products
        {where}
        ORDER  BY created_at DESC, id DESC
        LIMIT  ${len(args)}
    """

    rows = await db_fetch(query, args)

    items = [
        {
            "id":         r["id"],
            "name":       r["name"],
            "category":   r["category"],
            "price":      float(r["price"]),
            "created_at": r["created_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
        }
        for r in rows
    ]

    next_cursor = (
        encode_cursor(items[-1]["created_at"], items[-1]["id"])
        if len(items) == limit else None
    )
    return {"items": items, "next_cursor": next_cursor}


@app.get("/categories")
async def list_categories():
    rows = await db_fetch(
        "SELECT DISTINCT category FROM products ORDER BY category", []
    )
    return [r["category"] for r in rows]


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
