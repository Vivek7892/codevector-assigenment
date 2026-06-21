"""
Seed 200,000 products into the products table (Postgres / Supabase).
Uses batched executemany — no slow per-row loop.
"""

import os
import random
import time
from datetime import datetime, timedelta, timezone

import psycopg2
from dotenv import load_dotenv

load_dotenv()

CATEGORIES = [
    "Electronics", "Clothing", "Books", "Home & Garden", "Sports",
    "Toys", "Automotive", "Health", "Beauty", "Food",
]
ADJECTIVES = ["Premium", "Budget", "Deluxe", "Standard", "Pro", "Lite", "Ultra", "Basic"]
NOUNS      = ["Widget", "Gadget", "Device", "Item", "Product", "Gizmo", "Tool", "Kit"]

TOTAL = 200_000
BATCH = 5_000


def random_dt(start: datetime, end: datetime) -> datetime:
    ms = random.randint(0, int((end - start).total_seconds() * 1000))
    return start + timedelta(milliseconds=ms)


def main() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] > 0:
        print("Already seeded. Skipping.")
        cur.close()
        conn.close()
        return

    end_dt   = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=730)

    sql = """
        INSERT INTO products (name, category, price, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
    """

    inserted = 0
    t0 = time.perf_counter()

    while inserted < TOTAL:
        batch_size = min(BATCH, TOTAL - inserted)
        rows = []
        for _ in range(batch_size):
            dt = random_dt(start_dt, end_dt)
            rows.append((
                f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)} {random.randint(1, 9999)}",
                random.choice(CATEGORIES),
                round(random.uniform(1.0, 999.99), 2),
                dt, dt,
            ))
        cur.executemany(sql, rows)
        conn.commit()
        inserted += batch_size
        print(f"  inserted {inserted:,}/{TOTAL:,} …")

    cur.close()
    conn.close()
    print(f"Done — {TOTAL:,} rows in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
