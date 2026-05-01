from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests, hashlib, os, secrets
from datetime import datetime, timedelta
from database import init_db, get_db, log_activity
from db_helper import q, fetchone, fetchall, execute
from dotenv import load_dotenv
import os as _os
USE_PG = bool(_os.environ.get("DATABASE_URL"))
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get("SECRET_KEY", "fallback-dev-key")

limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")

API_KEY = os.environ.get("GROQ_API_KEY")
MODEL   = "llama-3.1-8b-instant"

# ── Content Filter ────────────────────────────────────
BLOCKED_WORDS = {
    # Sexual / adult
    "sex","porn","nude","naked","xxx","erotic","orgasm","penis","vagina",
    "boobs","breast","nipple","masturbat","intercourse","rape","incest",
    "prostitut","escort","onlyfans","nsfw","hentai","adult content",
    # Violence / harmful
    "kill","murder","suicide","bomb","terrorist","drug","cocaine","heroin",
    "hack","crack password","exploit","malware","ransomware",
    # Profanity (common)
    "fuck","shit","bitch","asshole","bastard","cunt","dick","pussy"
}

def is_blocked(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in BLOCKED_WORDS)

def sanitize_for_log(text: str) -> str:
    """Replace blocked words with *** in log entries"""
    t = text
    for w in BLOCKED_WORDS:
        if w in t.lower():
            t = t.lower().replace(w, "*" * len(w))
    return t

SYSTEM_PROMPT = """You are BrainWave AI — an intelligent, adaptive, and memory-driven study assistant.
Your purpose is to help users LEARN, REVISE, and MASTER academic topics using structured, personalized, and efficient responses.

STRICT DOMAIN RULE:
ONLY generate study-related content (school, college, competitive exams, theory, concepts, academic subjects).
If topic is NOT educational respond exactly: "This platform is designed for study-related topics. Please provide an academic concept or subject."

MODE INSTRUCTIONS:
- DEFAULT MODE: Title → Simple Explanation → Key Points → Example → Quick Revision → Practice Questions (3-5)
- EXAM MODE: Concise definitions + key points + exam-focused keywords only
- REVISION MODE: Ultra-short bullets, keywords only, fast recall format
- DEEP LEARNING MODE: Detailed explanation, step-by-step breakdown, deep theory
- VIVA MODE: Question-Answer format, 8-10 Q&As a professor would ask
- QUIZ MODE: Generate 5 MCQs with options A-D, correct answer, and explanation for each

SMART LINKING: At the end always add:
Related Topics: [list 3 related topics]
Next Topic to Study: [suggest 1 logical next topic]

Keep responses clear, structured, and easy to read.
Be a SECOND BRAIN — not just a text generator.
"""

init_db()

# ── Helpers ───────────────────────────────────────────

MAIL_EMAIL    = os.environ.get("MAIL_EMAIL")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
BASE_URL         = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
ADMIN_SETUP_KEY  = os.environ.get("ADMIN_SETUP_KEY", "")

# ── Helpers ───────────────────────────────────────────

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def logged_in():
    return "user_id" in session

def get_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)

def send_reset_email(to_email, username, reset_link):
    try:
        brevo_key    = os.environ.get("BREVO_API_KEY")
        sender_email = MAIL_EMAIL or "ompuri23456@gmail.com"

        if not brevo_key:
            print("ERROR: BREVO_API_KEY not set")
            return False

        html_body = f"""<div style="font-family:Segoe UI,sans-serif;max-width:480px;margin:auto;">
<div style="background:linear-gradient(135deg,#6c63ff,#a78bfa);padding:2rem;text-align:center;border-radius:16px 16px 0 0;">
<h2 style="margin:0;color:#fff;">BrainWave AI</h2></div>
<div style="background:#1a1a2e;color:#e0e0ff;padding:2rem;border-radius:0 0 16px 16px;">
<p>Hi <strong>{username}</strong>,</p>
<p>Your password reset link:</p>
<div style="text-align:center;margin:2rem 0;">
<a href="{reset_link}" target="_blank" style="display:inline-block;background:#6c63ff;color:#ffffff !important;padding:14px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;letter-spacing:0.5px;">
&#128274; Reset My Password
</a>
</div>
<p style="color:#8888aa;font-size:0.78rem;margin-top:1rem;">Expires in 30 minutes. If you did not request this, ignore this email.</p>
</div></div>"""

        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": brevo_key, "Content-Type": "application/json"},
            json={
                "sender":      {"name": "BrainWave AI", "email": sender_email},
                "to":          [{"email": to_email}],
                "subject":     "BrainWave AI - Password Reset",
                "htmlContent": html_body,
                "textContent": f"Hi {username},\n\nReset your BrainWave AI password by visiting this link:\n\n{reset_link}\n\nThis link expires in 30 minutes.\n\nIf you did not request this, ignore this email."
            }, timeout=10
        )
        print(f"Brevo API: {resp.status_code} — {resp.text}")
        return resp.status_code == 201

    except Exception as e:
        print(f"Email error: {type(e).__name__}: {e}")
        return False

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not logged_in():
            return redirect(url_for('login'))
        db = get_db()
        user = fetchone(db, "SELECT is_admin FROM users WHERE id=?", (session['user_id'],))
        db.close()
        if not user or not user['is_admin']:
            return render_template('404.html'), 404
        return f(*args, **kwargs)
    return decorated

# ── Auth ──────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email    = request.form['email'].strip()
        password = request.form['password']
        if not username or not email or not password:
            return render_template('register.html', error="All fields required.")
        if len(password) < 6:
            return render_template('register.html', error="Password must be at least 6 characters.")
        db = get_db()
        try:
            execute(db, "INSERT INTO users (username,email,password) VALUES (?,?,?)",
                    (username, email, hash_pw(password)))
            log_activity(None, username, "REGISTER", f"New user registered: {email}", get_ip())
        except Exception:
            return render_template('register.html', error="Username or email already exists.")
        finally:
            db.close()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email'].strip()
        password = request.form['password']
        db = get_db()
        user = fetchone(db, "SELECT * FROM users WHERE email=? AND password=?",
                        (email, hash_pw(password)))
        db.close()
        if user:
            session['user_id']  = user['id']
            session['username'] = user['username']
            session['is_admin'] = bool(user['is_admin'])
            log_activity(user['id'], user['username'], "LOGIN", f"Logged in from {get_ip()}", get_ip())
            return redirect(url_for('home'))
        log_activity(None, email, "LOGIN_FAIL", f"Failed login attempt", get_ip())
        return render_template('login.html', error="Invalid email or password.")
    return render_template('login.html')


@app.route('/logout')
def logout():
    if logged_in():
        log_activity(session.get('user_id'), session.get('username'), "LOGOUT", "", get_ip())
    session.clear()
    return redirect(url_for('login'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()
        db    = get_db()
        user  = fetchone(db, "SELECT * FROM users WHERE email=?", (email,))

        if user:
            token      = secrets.token_hex(16)  # shorter = cleaner URL
            expires_at = datetime.now() + timedelta(minutes=30)
            execute(db, "INSERT INTO reset_tokens (user_id, token, expires_at) VALUES (?,?,?)",
                    (user['id'], token, expires_at))

            reset_link = f"{BASE_URL}/reset-password/{token}"
            sent = send_reset_email(email, user['username'], reset_link)
            log_activity(user['id'], user['username'], "FORGOT_PASSWORD", f"Reset requested", get_ip())
            if not sent:
                print(f"EMAIL SEND FAILED for {email}")

        db.close()
        return render_template('forgot_password.html', success=True)

    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    db   = get_db()
    row  = fetchone(db, """
        SELECT rt.*, u.username, u.email FROM reset_tokens rt
        JOIN users u ON u.id = rt.user_id
        WHERE rt.token=? AND rt.used=0
    """, (token,))

    if not row:
        db.close()
        return render_template('reset_password.html', error="Invalid or expired link.")

    # Handle both string (SQLite) and datetime object (PostgreSQL)
    expires_at = row['expires_at']
    if isinstance(expires_at, str):
        expires_at = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')

    if datetime.now() > expires_at:
        db.close()
        return render_template('reset_password.html', error="This link has expired. Please request a new one.")

    if request.method == 'POST':
        password = request.form['password']
        confirm  = request.form['confirm']

        if len(password) < 6:
            db.close()
            return render_template('reset_password.html', token=token,
                                   error="Password must be at least 6 characters.")
        if password != confirm:
            db.close()
            return render_template('reset_password.html', token=token,
                                   error="Passwords do not match.")

        execute(db, "UPDATE users SET password=? WHERE id=?",
                (hash_pw(password), row['user_id']))
        execute(db, "UPDATE reset_tokens SET used=1 WHERE token=?", (token,))
        db.close()
        log_activity(row['user_id'], row['username'], "PASSWORD_RESET", "Password changed successfully", get_ip())
        return render_template('reset_password.html', success=True)

    db.close()
    return render_template('reset_password.html', token=token, username=row['username'])


# ── Pages ─────────────────────────────────────────────

@app.route('/')
def home():
    if not logged_in():
        return redirect(url_for('login'))
    log_activity(session['user_id'], session['username'], "VISIT", "Home page", get_ip())
    return render_template('index.html', username=session['username'])


# ── Notes ─────────────────────────────────────────────

@app.route('/get_notes', methods=['POST'])
@limiter.limit("10 per minute")
def get_notes():
    if not logged_in():
        return jsonify({"error": "Unauthorized"}), 401

    topic = request.json.get('topic', '').strip()
    mode  = request.json.get('mode', 'default').strip().lower()
    force = mode.startswith('force_')
    if force:
        mode = mode.replace('force_', '')
    if not topic:
        return jsonify({"notes": "Please provide a topic."})

    # Content filter
    if is_blocked(topic):
        log_activity(session['user_id'], session['username'], "BLOCKED",
                     f"Blocked topic: {sanitize_for_log(topic)}", get_ip())
        return jsonify({"notes": "⚠️ This platform is designed for study-related topics only. Please enter an academic subject.", "duplicate": False})

    # Deduplication check
    db = get_db()
    existing = fetchone(db,
        "SELECT id, topic FROM history WHERE user_id=? AND LOWER(topic)=LOWER(?) LIMIT 1",
        (session['user_id'], topic)
    )
    db.close()

    if existing and mode == 'default' and not force:
        return jsonify({
            "notes": None,
            "duplicate": True,
            "message": f"You already studied '{topic}'. Would you like to improve or review it?",
            "existing_id": existing['id']
        })

    log_activity(session['user_id'], session['username'], "SEARCH",
                 f"[{mode.upper()}] {sanitize_for_log(topic)}", get_ip())

    mode_instructions = {
        "default":      "Use the DEFAULT MODE format: Title → Simple Explanation → Key Points → Example → Quick Revision → Practice Questions (3-5)",
        "exam":         "Use EXAM MODE: concise definitions, key points, exam-focused keywords only. Be brief and exam-ready.",
        "revision":     "Use REVISION MODE: ultra-short bullets, keywords only, fast recall. Maximum 15 lines.",
        "deep":         "Use DEEP LEARNING MODE: detailed explanation, step-by-step breakdown, deep theory, examples.",
        "viva":         "Use VIVA MODE: generate 8-10 Q&A pairs a professor would ask in a viva/oral exam.",
        "quiz":         "Use QUIZ MODE: generate exactly 5 MCQs with options A-D, mark correct answer, give brief explanation for each."
    }

    instruction = mode_instructions.get(mode, mode_instructions["default"])
    url = "https://api.groq.com/openai/v1/chat/completions"

    try:
        response = requests.post(url,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL,
                  "messages": [
                      {"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": f"{instruction}\n\nTopic: {topic}"}
                  ]})
        response.raise_for_status()
        notes = response.json()['choices'][0]['message']['content']

        db = get_db()
        execute(db, "INSERT INTO history (user_id,topic,notes) VALUES (?,?,?)",
                (session['user_id'], f"[{mode.upper()}] {topic}" if mode != 'default' else topic, notes))
        db.close()
    except Exception as e:
        notes = "Error: " + str(e)

    return jsonify({"notes": notes, "duplicate": False})


# ── History ───────────────────────────────────────────

@app.route('/history')
def history():
    if not logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    rows = fetchall(db,
        "SELECT id, topic, notes, created_at FROM history WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (session['user_id'],))
    db.close()
    return jsonify({"history": [dict(r) for r in rows]})


@app.route('/history/<int:hid>', methods=['DELETE'])
def delete_history(hid):
    if not logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    execute(db, "DELETE FROM history WHERE id=? AND user_id=?", (hid, session['user_id']))
    db.close()
    return jsonify({"ok": True})


# ── B.Tech Notes ──────────────────────────────────────

@app.route('/btech')
def btech():
    if not logged_in():
        return redirect(url_for('login'))
    log_activity(session['user_id'], session['username'], "VISIT", "B.Tech page", get_ip())
    return render_template('btech.html', username=session['username'])


@app.route('/get_btech_notes', methods=['POST'])
@limiter.limit("10 per minute")
def get_btech_notes():
    if not logged_in():
        return jsonify({"error": "Unauthorized"}), 401

    data    = request.json
    branch  = data.get('branch', '').strip()
    subject = data.get('subject', '').strip()
    topic   = data.get('topic', '').strip()

    label = f"[B.Tech {branch}] {subject}" + (f" — {topic}" if topic else "")
    log_activity(session['user_id'], session['username'], "SEARCH", label, get_ip())

    focus  = f"specifically on the topic: {topic}" if topic else "covering the complete syllabus overview"
    prompt = f"""You are an expert professor and academic content writer for B.Tech {branch} students in India (following AICTE/university syllabus).

Generate comprehensive, detailed, exam-ready notes for the subject: "{subject}" ({focus}).

Structure the notes exactly as follows:

## Subject Overview
Brief introduction to the subject and its importance in {branch}.

## Key Concepts & Theory
Explain all major concepts with clear definitions, formulas (where applicable), and theory.

## Important Topics Breakdown
Cover each important topic with:
- Definition
- Working principle or explanation
- Formula / equation (if any)
- Real-world application

## Solved Examples
Provide 2-3 worked examples or case studies relevant to the topic.

## Common Exam Questions
List 5 important questions that frequently appear in university exams.

## Quick Revision Summary
Bullet-point summary of everything covered — ideal for last-minute revision.

Make the notes detailed, accurate, and easy to understand for a B.Tech student. Use standard Indian university syllabus as reference."""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL,
                  "messages": [
                      {"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}
                  ],
                  "max_tokens": 2048}
        )
        response.raise_for_status()
        notes = response.json()['choices'][0]['message']['content']

        db = get_db()
        execute(db, "INSERT INTO history (user_id,topic,notes) VALUES (?,?,?)",
                (session['user_id'], label, notes))
        db.close()
    except Exception as e:
        notes = "Error: " + str(e)

    return jsonify({"notes": notes})


# ── Chat ──────────────────────────────────────────────

@app.route('/chat', methods=['POST'])
@limiter.limit("20 per minute")
def chat():
    if not logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    msg = request.json.get('message', '').strip()
    if not msg:
        return jsonify({"reply": "Please say something."})

    # Content filter
    if is_blocked(msg):
        log_activity(session['user_id'], session['username'], "BLOCKED",
                     f"Blocked chat: {sanitize_for_log(msg)}", get_ip())
        return jsonify({"reply": "⚠️ This platform is for academic topics only. Please ask a study-related question."})

    log_activity(session['user_id'], session['username'], "CHAT", msg[:100], get_ip())

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL,
                  "messages": [
                      {"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": msg}
                  ]})
        response.raise_for_status()
        reply = response.json()['choices'][0]['message']['content']
    except Exception as e:
        reply = "Error: " + str(e)
    return jsonify({"reply": reply})


# ── Admin ─────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html', username=session['username'])


@app.route('/admin/stats')
@admin_required
def admin_stats():
    db = get_db()

    total_users    = fetchone(db, "SELECT COUNT(*) as c FROM users")['c']
    total_searches = fetchone(db, "SELECT COUNT(*) as c FROM activity_log WHERE action='SEARCH'")['c']
    total_logins   = fetchone(db, "SELECT COUNT(*) as c FROM activity_log WHERE action='LOGIN'")['c']
    total_notes    = fetchone(db, "SELECT COUNT(*) as c FROM history")['c']
    total_chats    = fetchone(db, "SELECT COUNT(*) as c FROM activity_log WHERE action='CHAT'")['c']
    total_fails    = fetchone(db, "SELECT COUNT(*) as c FROM activity_log WHERE action='LOGIN_FAIL'")['c']

    # recent activity (last 100)
    logs = fetchall(db, """
        SELECT username, action, detail, ip, created_at
        FROM activity_log ORDER BY created_at DESC LIMIT 100
    """)

    # all users
    users = fetchall(db, """
        SELECT u.id, u.username, u.email, u.is_admin,
               u.created_at,
               COUNT(h.id) as note_count,
               MAX(a.created_at) as last_login
        FROM users u
        LEFT JOIN history h ON h.user_id = u.id
        LEFT JOIN activity_log a ON a.user_id = u.id AND a.action = 'LOGIN'
        GROUP BY u.id, u.username, u.email, u.is_admin, u.created_at
        ORDER BY u.id DESC
    """)

    # top searches
    top_searches = fetchall(db, """
        SELECT detail, COUNT(*) as cnt FROM activity_log
        WHERE action='SEARCH'
        GROUP BY detail ORDER BY cnt DESC LIMIT 10
    """)

    # daily activity last 7 days
    if USE_PG:
        daily = fetchall(db, """
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM activity_log
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(created_at) ORDER BY day
        """)
        new_users = fetchall(db, """
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM users
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(created_at) ORDER BY day
        """)
    else:
        daily = fetchall(db, """
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM activity_log
            WHERE created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at) ORDER BY day
        """)
        new_users = fetchall(db, """
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM users
            WHERE created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at) ORDER BY day
        """)

    # mode usage breakdown
    mode_usage = fetchone(db, """
        SELECT
          SUM(CASE WHEN detail LIKE '[EXAM]%' THEN 1 ELSE 0 END) as exam,
          SUM(CASE WHEN detail LIKE '[REVISION]%' THEN 1 ELSE 0 END) as revision,
          SUM(CASE WHEN detail LIKE '[DEEP]%' THEN 1 ELSE 0 END) as deep,
          SUM(CASE WHEN detail LIKE '[VIVA]%' THEN 1 ELSE 0 END) as viva,
          SUM(CASE WHEN detail LIKE '[QUIZ]%' THEN 1 ELSE 0 END) as quiz,
          SUM(CASE WHEN detail NOT LIKE '[%]%' THEN 1 ELSE 0 END) as default_mode
        FROM activity_log WHERE action='SEARCH'
    """)

    # action breakdown for pie chart
    action_counts = fetchall(db, """
        SELECT action, COUNT(*) as cnt FROM activity_log
        GROUP BY action ORDER BY cnt DESC
    """)

    db.close()

    return jsonify({
        "stats": {
            "total_users":    total_users,
            "total_searches": total_searches,
            "total_logins":   total_logins,
            "total_notes":    total_notes,
            "total_chats":    total_chats,
            "total_fails":    total_fails
        },
        "logs":         [dict(r) for r in logs],
        "users":        [dict(r) for r in users],
        "top_searches": [dict(r) for r in top_searches],
        "daily":        [dict(r) for r in daily],
        "mode_usage":   dict(mode_usage) if mode_usage else {},
        "action_counts":[dict(r) for r in action_counts],
        "new_users":    [dict(r) for r in new_users]
    })


@app.route('/admin/make_admin/<int:uid>', methods=['POST'])
@admin_required
def make_admin(uid):
    db = get_db()
    execute(db, "UPDATE users SET is_admin=1 WHERE id=?", (uid,))
    db.close()
    return jsonify({"ok": True})


# ── One-time admin setup ──────────────────────────────
@app.route('/setup-admin/<key>/<email>')
def setup_admin(key, email):
    if not ADMIN_SETUP_KEY or key != ADMIN_SETUP_KEY:
        return "Invalid key", 403
    db = get_db()
    result = execute(db, "UPDATE users SET is_admin=1 WHERE email=?", (email,))
    db.close()
    if result:
        return f"✅ {email} is now admin."
    return f"❌ No user found: {email}", 404


# ── Errors ────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "Too many requests. Please wait a moment."}), 429

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True)
