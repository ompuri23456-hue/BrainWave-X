from database import get_db
db = get_db()

print("=== TABLES ===")
tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print(" -", t[0])

print("\n=== USERS ===")
users = db.execute("SELECT id, username, email, is_admin FROM users").fetchall()
for u in users:
    print(f"  id={u[0]} username={u[1]} email={u[2]} is_admin={u[3]}")

print("\n=== ACTIVITY LOG (last 10) ===")
try:
    logs = db.execute("SELECT username, action, detail, created_at FROM activity_log ORDER BY created_at DESC LIMIT 10").fetchall()
    if logs:
        for l in logs:
            print(f"  [{l[3]}] {l[1]} — {l[0]} — {l[2]}")
    else:
        print("  (empty)")
except Exception as e:
    print("  ERROR:", e)

db.close()
