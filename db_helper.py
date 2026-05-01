"""
Helper to make queries work with both SQLite (?) and PostgreSQL (%s)
"""
import os
USE_PG = bool(os.environ.get("DATABASE_URL"))

def q(sql):
    """Convert SQLite ? placeholders to %s for PostgreSQL"""
    if USE_PG:
        return sql.replace("?", "%s")
    return sql

def fetchone(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    row = cur.fetchone()
    cur.close()
    if row is None:
        return None
    if USE_PG:
        # convert to dict-like
        cols = [d[0] for d in cur.description] if cur.description else []
        return dict(zip(cols, row)) if cols else row
    return row

def fetchall(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    rows = cur.fetchall()
    cur.close()
    if USE_PG:
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, r)) for r in rows]
    return rows

def execute(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    conn.commit()
    rowcount = cur.rowcount
    cur.close()
    return rowcount
