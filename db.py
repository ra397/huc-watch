import psycopg
from dotenv import load_dotenv
from queries import INSERT_HUC12_REGION, INSERT_HUC12_MRMS_2MIN

load_dotenv()

conn = psycopg.connect()

def insert_huc12(rows):
    with conn.cursor() as cur:
        cur.executemany(INSERT_HUC12_REGION, rows)
    conn.commit()

def insert_huc12_mrms_2min(rows):
    with conn.cursor() as cur:
        cur.executemany(INSERT_HUC12_MRMS_2MIN, rows)
    conn.commit()
