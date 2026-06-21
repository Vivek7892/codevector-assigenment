"""Apply schema.sql then seed 200k products."""
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 3306)),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    autocommit=True,
)

with open("schema.sql") as f:
    for statement in f.read().split(";"):
        s = statement.strip()
        if s:
            conn.cursor().execute(s)

conn.close()
print("Schema applied.")
