import base64
import json
import os
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    yield
    await pool.close()


app = FastAPI(title="Product Browser", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


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


async def db_fetch(query: str, args: list) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
    return [dict(r) for r in rows]


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
