"""
Run this once to give yourself admin access:
    py make_admin.py your@email.com
"""
import sys
from database import get_db

if len(sys.argv) < 2:
    print("Usage: py make_admin.py your@email.com")
    sys.exit(1)

email = sys.argv[1]
db = get_db()
result = db.execute("UPDATE users SET is_admin=1 WHERE email=?", (email,))
db.commit()
db.close()

if result.rowcount:
    print(f"✅ {email} is now an admin. Visit /admin")
else:
    print(f"❌ No user found with email: {email}")
