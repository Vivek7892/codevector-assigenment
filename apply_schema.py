import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()

with open("schema.sql") as f:
    cur.execute(f.read())

cur.close()
conn.close()
print("Schema applied.")
