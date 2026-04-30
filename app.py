from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests, hashlib, os, secrets, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from database import init_db, get_db, log_activity
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get("SECRET_KEY", "fallback-dev-key")

limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")

API_KEY = os.environ.get("GROQ_API_KEY")
MODEL   = "llama-3.1-8b-instant"

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
        msg = MIMEMultipart("alternative")
        msg['Subject'] = "BrainWave AI — Password Reset"
        msg['From']    = f"BrainWave AI <{MAIL_EMAIL}>"
        msg['To']      = to_email

        html = f"""
        <div style="font-family:Segoe UI,sans-serif;max-width:480px;margin:auto;background:#1a1a2e;color:#e0e0ff;border-radius:16px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#6c63ff,#a78bfa);padding:2rem;text-align:center;">
            <h2 style="margin:0;color:#fff;">⚡ BrainWave AI</h2>
            <p style="margin:0.5rem 0 0;color:rgba(255,255,255,0.85);font-size:0.9rem;">Password Reset Request</p>
          </div>
          <div style="padding:2rem;">
            <p>Hi <strong>{username}</strong>,</p>
            <p>We received a request to reset your password. Click the button below to set a new password:</p>
            <div style="text-align:center;margin:2rem 0;">
              <a href="{reset_link}"
                 style="background:linear-gradient(135deg,#6c63ff,#a78bfa);color:#fff;padding:0.8rem 2rem;
                        border-radius:10px;text-decoration:none;font-weight:700;display:inline-block;">
                Reset Password
              </a>
            </div>
            <p style="color:#8888aa;font-size:0.85rem;">This link expires in <strong>30 minutes</strong>. If you didn't request this, ignore this email.</p>
            <hr style="border-color:#2a2a4a;margin:1.5rem 0;">
            <p style="color:#8888aa;font-size:0.8rem;text-align:center;">BrainWave AI · Your AI Study Partner</p>
          </div>
        </div>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(MAIL_EMAIL, MAIL_PASSWORD)
            server.sendmail(MAIL_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print("Email error:", e)
        return False


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not logged_in():
            return redirect(url_for('login'))
        db = get_db()
        user = db.execute("SELECT is_admin FROM users WHERE id=?", (session['user_id'],)).fetchone()
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
            db.execute("INSERT INTO users (username,email,password) VALUES (?,?,?)",
                       (username, email, hash_pw(password)))
            db.commit()
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
        user = db.execute("SELECT * FROM users WHERE email=? AND password=?",
                          (email, hash_pw(password))).fetchone()
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
        user  = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if user:
            token      = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(minutes=30)
            db.execute("INSERT INTO reset_tokens (user_id, token, expires_at) VALUES (?,?,?)",
                       (user['id'], token, expires_at.strftime('%Y-%m-%d %H:%M:%S')))
            db.commit()

            reset_link = f"{BASE_URL}/reset-password/{token}"
            sent = send_reset_email(email, user['username'], reset_link)
            log_activity(user['id'], user['username'], "FORGOT_PASSWORD", f"Reset requested from {get_ip()}", get_ip())

        db.close()
        # Always show success (don't reveal if email exists)
        return render_template('forgot_password.html', success=True)

    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    db   = get_db()
    row  = db.execute("""
        SELECT rt.*, u.username, u.email FROM reset_tokens rt
        JOIN users u ON u.id = rt.user_id
        WHERE rt.token=? AND rt.used=0
    """, (token,)).fetchone()

    if not row:
        db.close()
        return render_template('reset_password.html', error="Invalid or expired link.")

    if datetime.now() > datetime.strptime(row['expires_at'], '%Y-%m-%d %H:%M:%S'):
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

        db.execute("UPDATE users SET password=? WHERE id=?",
                   (hash_pw(password), row['user_id']))
        db.execute("UPDATE reset_tokens SET used=1 WHERE token=?", (token,))
        db.commit()
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
    if not topic:
        return jsonify({"notes": "Please provide a topic."})

    log_activity(session['user_id'], session['username'], "SEARCH", f"Free notes: {topic}", get_ip())

    url    = "https://api.groq.com/openai/v1/chat/completions"
    prompt = f"Generate structured notes for {topic}:\nDefinition\nKey Points\nExample\nSummary"

    try:
        response = requests.post(url,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL,
                  "messages": [{"role": "user", "content": prompt}]})
        response.raise_for_status()
        notes = response.json()['choices'][0]['message']['content']

        db = get_db()
        db.execute("INSERT INTO history (user_id,topic,notes) VALUES (?,?,?)",
                   (session['user_id'], topic, notes))
        db.commit()
        db.close()
    except Exception as e:
        notes = "Error: " + str(e)

    return jsonify({"notes": notes})


# ── History ───────────────────────────────────────────

@app.route('/history')
def history():
    if not logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    rows = db.execute(
        "SELECT id, topic, notes, created_at FROM history WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (session['user_id'],)).fetchall()
    db.close()
    return jsonify({"history": [dict(r) for r in rows]})


@app.route('/history/<int:hid>', methods=['DELETE'])
def delete_history(hid):
    if not logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    db.execute("DELETE FROM history WHERE id=? AND user_id=?", (hid, session['user_id']))
    db.commit()
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
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 2048}
        )
        response.raise_for_status()
        notes = response.json()['choices'][0]['message']['content']

        db = get_db()
        db.execute("INSERT INTO history (user_id,topic,notes) VALUES (?,?,?)",
                   (session['user_id'], label, notes))
        db.commit()
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

    log_activity(session['user_id'], session['username'], "CHAT", msg[:100], get_ip())

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL,
                  "messages": [{"role": "user", "content": msg}]})
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

    total_users    = db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
    total_searches = db.execute("SELECT COUNT(*) as c FROM activity_log WHERE action='SEARCH'").fetchone()['c']
    total_logins   = db.execute("SELECT COUNT(*) as c FROM activity_log WHERE action='LOGIN'").fetchone()['c']
    total_notes    = db.execute("SELECT COUNT(*) as c FROM history").fetchone()['c']

    # recent activity (last 100)
    logs = db.execute("""
        SELECT username, action, detail, ip, created_at
        FROM activity_log
        ORDER BY created_at DESC
        LIMIT 100
    """).fetchall()

    # all users
    users = db.execute("""
        SELECT u.id, u.username, u.email, u.is_admin,
               COALESCE(u.created_at, 'N/A') as created_at,
               COUNT(h.id) as note_count,
               (SELECT created_at FROM activity_log
                WHERE user_id=u.id AND action='LOGIN'
                ORDER BY created_at DESC LIMIT 1) as last_login
        FROM users u
        LEFT JOIN history h ON h.user_id = u.id
        GROUP BY u.id
        ORDER BY u.id DESC
    """).fetchall()

    # top searches
    top_searches = db.execute("""
        SELECT detail, COUNT(*) as cnt
        FROM activity_log
        WHERE action='SEARCH'
        GROUP BY detail
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchall()

    db.close()

    return jsonify({
        "stats": {
            "total_users":    total_users,
            "total_searches": total_searches,
            "total_logins":   total_logins,
            "total_notes":    total_notes
        },
        "logs":        [dict(r) for r in logs],
        "users":       [dict(r) for r in users],
        "top_searches":[dict(r) for r in top_searches]
    })


@app.route('/admin/make_admin/<int:uid>', methods=['POST'])
@admin_required
def make_admin(uid):
    db = get_db()
    db.execute("UPDATE users SET is_admin=1 WHERE id=?", (uid,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


# ── One-time admin setup ──────────────────────────────
@app.route('/setup-admin/<key>/<email>')
def setup_admin(key, email):
    if not ADMIN_SETUP_KEY or key != ADMIN_SETUP_KEY:
        return "Invalid key", 403
    db = get_db()
    result = db.execute("UPDATE users SET is_admin=1 WHERE email=?", (email,))
    db.commit()
    db.close()
    if result.rowcount:
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
