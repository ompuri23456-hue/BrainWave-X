"""
Run once to migrate existing database:
    py migrate.py
"""
from database import get_db

db = get_db()

migrations = [
    # Add is_admin to users if missing
    "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0",
    # Add created_at to users if missing
    "ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT '2024-01-01 00:00:00'",
    # Create activity_log if not exists
    """CREATE TABLE IF NOT EXISTS activity_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        username   TEXT,
        action     TEXT    NOT NULL,
        detail     TEXT,
        ip         TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",
]

for sql in migrations:
    try:
        db.execute(sql)
        print(f"✅ OK: {sql[:60]}...")
    except Exception as e:
        print(f"⚠️  Skipped (already exists): {e}")

db.commit()
db.close()
print("\nMigration complete. Now run: py make_admin.py your@email.com")
