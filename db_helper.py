"""
Helper to make queries work with both SQLite (?) and PostgreSQL (%s)
"""
import os
USE_PG = bool(os.environ.get("DATABASE_URL"))

def q(sql):
    if USE_PG:
        return sql.replace("?", "%s")
    return sql

def _row_to_dict(cur, row):
    if row is None:
        return None
    if USE_PG:
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    return row  # sqlite3.Row already supports dict-like access

def fetchone(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    row = cur.fetchone()
    result = _row_to_dict(cur, row)
    cur.close()
    return result

def fetchall(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    rows = cur.fetchall()
    if USE_PG:
        cols = [d[0] for d in cur.description]
        result = [dict(zip(cols, r)) for r in rows]
    else:
        result = [dict(r) for r in rows]
    cur.close()
    return result

def execute(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(q(sql), params)
    conn.commit()
    rowcount = cur.rowcount
    cur.close()
    return rowcount
