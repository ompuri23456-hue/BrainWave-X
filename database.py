import os

DATABASE_URL = os.environ.get("DATABASE_URL")  # set on Render
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import pg8000
    import pg8000.native
else:
    import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brainwave.db")


def get_db():
    if USE_PG:
        import urllib.parse
        r = urllib.parse.urlparse(DATABASE_URL)
        conn = pg8000.connect(
            host=r.hostname,
            port=r.port or 5432,
            database=r.path[1:],
            user=r.username,
            password=r.password,
            ssl_context=True
        )
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    if USE_PG:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         SERIAL PRIMARY KEY,
                username   TEXT UNIQUE NOT NULL,
                email      TEXT UNIQUE NOT NULL,
                password   TEXT NOT NULL,
                is_admin   INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                topic      TEXT NOT NULL,
                notes      TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER,
                username   TEXT,
                action     TEXT NOT NULL,
                detail     TEXT,
                ip         TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reset_tokens (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL,
                token      TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used       INTEGER DEFAULT 0
            )""")
    else:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT UNIQUE NOT NULL,
                email      TEXT UNIQUE NOT NULL,
                password   TEXT NOT NULL,
                is_admin   INTEGER DEFAULT 0,
                created_at TEXT DEFAULT '2024-01-01 00:00:00'
            );
            CREATE TABLE IF NOT EXISTS history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                topic      TEXT NOT NULL,
                notes      TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                username   TEXT,
                action     TEXT NOT NULL,
                detail     TEXT,
                ip         TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS reset_tokens (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                token      TEXT NOT NULL,
                expires_at DATETIME NOT NULL,
                used       INTEGER DEFAULT 0
            );
        """)

    conn.commit()
    cur.close()
    conn.close()


def log_activity(user_id, username, action, detail="", ip=""):
    conn = get_db()
    cur  = conn.cursor()
    if USE_PG:
        cur.execute(
            "INSERT INTO activity_log (user_id, username, action, detail, ip) VALUES (%s,%s,%s,%s,%s)",
            (user_id, username, action, detail, ip)
        )
    else:
        cur.execute(
            "INSERT INTO activity_log (user_id, username, action, detail, ip) VALUES (?,?,?,?,?)",
            (user_id, username, action, detail, ip)
        )
    conn.commit()
    cur.close()
    conn.close()
