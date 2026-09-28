import psycopg
from dotenv import load_dotenv
from mrms_huc12 import PROJECT_ROOT
from mrms_huc12.queries import (INSERT_HUC12_REGION, INSERT_HUC12_MRMS_2MIN, SELECT_LATEST_OBS_TIME,
                     DELETE_OLDER_THAN_24H)

load_dotenv(PROJECT_ROOT / '.env')

def get_conn():
    return psycopg.connect()

def insert_huc12(conn, rows):
    with conn.cursor() as cur:
        cur.executemany(INSERT_HUC12_REGION, rows)
    conn.commit()

def insert_huc12_mrms_2min(conn, rows):
    with conn.cursor() as cur:
        cur.executemany(INSERT_HUC12_MRMS_2MIN, rows)
    conn.commit()

def get_latest_obs_time(conn):
    with conn.cursor() as cur:
        cur.execute(SELECT_LATEST_OBS_TIME)
        return cur.fetchone()[0]

def delete_older_than_24h(conn):
    with conn.cursor() as cur:
        cur.execute(DELETE_OLDER_THAN_24H)
        deleted = cur.rowcount
    conn.commit()
    return deleted