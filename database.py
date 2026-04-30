import sqlite3, os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brainwave.db")

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    UNIQUE NOT NULL,
            email      TEXT    UNIQUE NOT NULL,
            password   TEXT    NOT NULL,
            is_admin   INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            topic      TEXT    NOT NULL,
            notes      TEXT    NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            username   TEXT,
            action     TEXT    NOT NULL,
            detail     TEXT,
            ip         TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            token      TEXT    NOT NULL,
            expires_at DATETIME NOT NULL,
            used       INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()

def log_activity(user_id, username, action, detail="", ip=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO activity_log (user_id, username, action, detail, ip) VALUES (?,?,?,?,?)",
        (user_id, username, action, detail, ip)
    )
    conn.commit()
    conn.close()
