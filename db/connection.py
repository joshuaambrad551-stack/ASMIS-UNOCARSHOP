import psycopg2
import os
from contextlib import contextmanager

DB_CONFIG = {
    "host": os.environ.get("ASMIS_DB_HOST", "localhost"),
    "database": os.environ.get("ASMIS_DB_NAME", "unocarshop"),
    "user": os.environ.get("ASMIS_DB_USER", "postgres"),
    "password": os.environ.get("ASMIS_DB_PASS", "admin123"),
    "port": os.environ.get("ASMIS_DB_PORT", "5432"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


@contextmanager
def db_cursor(commit=False):
    """
    Central database cursor helper.
    Use commit=True for writes so rollback/close behavior stays consistent.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def fetch_all(query, params=None):
    with db_cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchall()


def fetch_one(query, params=None):
    with db_cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchone()


def execute_write(query, params=None):
    with db_cursor(commit=True) as cur:
        cur.execute(query, params or ())


if __name__ == "__main__":
    try:
        conn = get_connection()
        print("✅ Connected to unocarshop database!")
        conn.close()
    except Exception as e:
        print(f"❌ Connection failed: {e}")
