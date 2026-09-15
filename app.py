import os
import json
import re
import secrets
import time
from functools import wraps
from datetime import datetime

from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash

import email_utils

app = Flask(__name__)

# ===== SECRET KEY =====
# Never hardcode this. Set FLASK_SECRET_KEY in your environment before running.
# For local dev only, we fall back to a random key (sessions won't survive a restart).
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)

# Cookie hardening
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Turn this on once you're serving over HTTPS:
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
)

# All data files live next to this script, regardless of the process's
# current working directory (important under WSGI hosts like PythonAnywhere,
# where the cwd usually isn't the project folder).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _path(filename):
    return os.path.join(BASE_DIR, filename)


# ===== FILES =====
DATA_FILES = ["chat.json", "dm.json", "lyrics.json", "events.json"]
USERS_FILE = "users.json"


def load(file):
    path = _path(file)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(file, data):
    with open(_path(file), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_users():
    path = _path(USERS_FILE)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_user(username):
    if not username:
        return None
    for u in load_users():
        if u["username"] == username:
            return u
    return None


def find_user_by_email(email):
    if not email:
        return None
    email = email.strip().lower()
    for u in load_users():
        if u.get("email", "").strip().lower() == email:
            return u
    return None


def save_users(users):
    with open(_path(USERS_FILE), "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)


# ===== PASSWORD RESET TOKENS =====
RESETS_FILE = "password_resets.json"
RESET_TOKEN_TTL_SECONDS = 30 * 60  # 30 minutes


def load_resets():
    path = _path(RESETS_FILE)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_resets(resets):
    with open(_path(RESETS_FILE), "w", encoding="utf-8") as f:
        json.dump(resets, f, indent=4, ensure_ascii=False)


def create_reset_token(username):
    resets = load_resets()
    # Invalidate any older tokens for this user first
    resets = {t: r for t, r in resets.items() if r["username"] != username}
    token = secrets.token_urlsafe(32)
    resets[token] = {"username": username, "expires": time.time() + RESET_TOKEN_TTL_SECONDS}
    save_resets(resets)
    return token


def consume_reset_token(token):
    """Returns the username for a valid, unexpired token, and deletes it. None otherwise."""
    resets = load_resets()
    entry = resets.get(token)
    if not entry:
        return None
    if time.time() > entry["expires"]:
        del resets[token]
        save_resets(resets)
        return None
    del resets[token]
    save_resets(resets)
    return entry["username"]


# ===== AUTH HELPERS =====
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("login"))
        if not session.get("is_admin"):
            return "Access Denied", 403
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = find_user(username)
        if not user or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid username or password.")

        session.clear()
        session["username"] = user["username"]
        session["is_admin"] = bool(user.get("is_admin"))
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if not username or not email:
            return render_template("register.html", error="Name and email are required.", username=username, email=email)
        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters.", username=username, email=email)
        if password != confirm:
            return render_template("register.html", error="Passwords don't match.", username=username, email=email)

        if find_user(username):
            return render_template("register.html", error="That name is already taken.", username=username, email=email)
        if find_user_by_email(email):
            return render_template("register.html", error="An account with that email already exists.", username=username, email=email)

        users = load_users()
        users.append({
            "username": username,
            "email": email,
            "is_admin": False,
            "password_hash": generate_password_hash(password),
        })
        save_users(users)

        session.clear()
        session["username"] = username
        session["is_admin"] = False
        return redirect(url_for("home"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        identifier = (request.form.get("username_or_email") or "").strip()
        user = find_user(identifier) or find_user_by_email(identifier)

        # Always show the same message whether or not the account exists,
        # so this endpoint can't be used to check who has an account.
        generic_message = "If that account exists, we've sent a reset link to its email address."

        if user and user.get("email"):
            token = create_reset_token(user["username"])
            reset_link = url_for("reset_password", token=token, _external=True)
            body = (
                f"Hi {user['username']},\n\n"
                f"Someone requested a password reset for your Body of Christ app account.\n"
                f"Click the link below to set a new password. This link expires in 30 minutes:\n\n"
                f"{reset_link}\n\n"
                f"If you didn't request this, you can ignore this email."
            )
            try:
                email_utils.send_email(user["email"], "Reset your password", body)
            except RuntimeError:
                # Email isn't configured on this server yet.
                return render_template(
                    "forgot_password.html",
                    error="Email isn't configured on this server yet. Ask an admin to set up SMTP_HOST/SMTP_USER/SMTP_PASSWORD.",
                )

        return render_template("forgot_password.html", message=generic_message)

    return render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "POST":
        new_password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if len(new_password) < 8:
            return render_template("reset_password.html", token=token, error="Password must be at least 8 characters.")
        if new_password != confirm:
            return render_template("reset_password.html", token=token, error="Passwords don't match.")

        username = consume_reset_token(token)
        if not username:
            return render_template("reset_password.html", token=token, error="This reset link is invalid or has expired. Request a new one.", expired=True)

        users = load_users()
        for u in users:
            if u["username"] == username:
                u["password_hash"] = generate_password_hash(new_password)
        save_users(users)

        return redirect(url_for("login"))

    # GET: just verify the token looks valid-ish before showing the form
    resets = load_resets()
    entry = resets.get(token)
    if not entry or time.time() > entry["expires"]:
        return render_template("reset_password.html", token=token, error="This reset link is invalid or has expired. Request a new one.", expired=True)

    return render_template("reset_password.html", token=token)


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new_password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        user = find_user(session["username"])
        if not user or not check_password_hash(user["password_hash"], current):
            return render_template("change_password.html", error="Current password is incorrect.")
        if len(new_password) < 8:
            return render_template("change_password.html", error="New password must be at least 8 characters.")
        if new_password != confirm:
            return render_template("change_password.html", error="New passwords don't match.")

        users = load_users()
        for u in users:
            if u["username"] == session["username"]:
                u["password_hash"] = generate_password_hash(new_password)
        save_users(users)

        return render_template("change_password.html", message="Password updated.")

    return render_template("change_password.html")


@app.route("/")
@login_required
def home():
    return render_template("home.html", is_admin=session.get("is_admin", False))


# --- LYRICS ---
def normalize_lyrics_key(t):
    t = re.sub(r"[^\w\s]", "", (t or "").lower())
    return re.sub(r"\s+", " ", t).strip()[:200]


@app.route("/lyrics", methods=["GET", "POST"])
@login_required
def manage_lyrics():
    data = load("lyrics.json")

    if request.method == "POST":
        if not session.get("is_admin"):
            return jsonify({"success": False, "message": "Admins only"}), 403

        new_song = request.get_json(silent=True) or {}
        title = (new_song.get("title") or "").strip()
        text = new_song.get("text") or ""

        if not title:
            return jsonify({"success": False, "message": "Title is required"}), 400

        if any(song["title"].lower() == title.lower() for song in data):
            return jsonify({"success": False, "message": "Song already exists"}), 409

        new_key = normalize_lyrics_key(text)
        if new_key and any(normalize_lyrics_key(song.get("text", "")) == new_key for song in data):
            return jsonify({"success": False, "message": "This song's lyrics already exist under another title"}), 409

        data.append({"title": title, "text": text, "favorite": False})
        save("lyrics.json", data)
        return jsonify({"success": True})

    return jsonify(data)


@app.route("/lyrics/edit", methods=["POST"])
@admin_required
def edit_lyric():
    payload = request.get_json(silent=True) or {}
    original_title = (payload.get("original_title") or "").strip()
    new_title = (payload.get("title") or "").strip()
    new_text = payload.get("text") or ""

    if not original_title or not new_title:
        return jsonify({"success": False, "message": "Title is required"}), 400

    data = load("lyrics.json")
    target = next((s for s in data if s["title"] == original_title), None)
    if not target:
        return jsonify({"success": False, "message": "Song not found"}), 404

    # If the title is changing, make sure it doesn't collide with a different song
    if new_title.lower() != original_title.lower():
        if any(s["title"].lower() == new_title.lower() for s in data if s is not target):
            return jsonify({"success": False, "message": "Another song already has that title"}), 409

    # Same check for lyric body, excluding the song being edited
    new_key = normalize_lyrics_key(new_text)
    if new_key and any(normalize_lyrics_key(s.get("text", "")) == new_key for s in data if s is not target):
        return jsonify({"success": False, "message": "This song's lyrics already exist under another title"}), 409

    target["title"] = new_title
    target["text"] = new_text
    save("lyrics.json", data)
    return jsonify({"success": True})


@app.route("/lyrics/delete", methods=["POST"])
@admin_required
def delete_lyric():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()

    data = load("lyrics.json")
    remaining = [s for s in data if s["title"] != title]
    if len(remaining) == len(data):
        return jsonify({"success": False, "message": "Song not found"}), 404

    save("lyrics.json", remaining)
    return jsonify({"success": True})


@app.route("/admin/sync_lyrics", methods=["POST"])
@admin_required
def admin_sync_lyrics():
    import sync_lyrics

    log_lines = []
    try:
        result = sync_lyrics.fetch_and_integrate(log=log_lines.append)
    except RuntimeError as e:
        # e.g. GEMINI_API_KEY not set
        return jsonify({"success": False, "message": str(e), "log": log_lines}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Unexpected error: {e}", "log": log_lines}), 500

    if not result["ok"]:
        return jsonify({"success": False, "message": result["error"] or "Sync failed", "log": log_lines}), 502

    return jsonify({
        "success": True,
        "added": result["added"],
        "added_titles": result["added_titles"],
        "skipped_titles": result["skipped_titles"],
        "log": log_lines,
    })


@app.route("/favorite", methods=["POST"])
@login_required
def toggle_favorite():
    payload = request.get_json(silent=True) or {}
    title = payload.get("title")
    data = load("lyrics.json")

    for song in data:
        if song["title"] == title:
            song["favorite"] = not song.get("favorite", False)
            save("lyrics.json", data)
            return jsonify({"success": True, "favorite": song["favorite"]})

    return jsonify({"success": False, "message": "Song not found"}), 404


@app.route("/songbook")
@login_required
def songbook():
    return render_template("songbook.html")


@app.route("/song/<path:title>")
@login_required
def song_detail(title):
    songs = load("lyrics.json")
    song = next((s for s in songs if s["title"] == title), None)
    if not song:
        return "Song not found", 404
    return render_template("song_detail.html", song=song)


# --- EVENTS ---
@app.route("/events", methods=["GET", "POST"])
@login_required
def manage_events():
    events = load("events.json")

    if request.method == "POST":
        if not session.get("is_admin"):
            return jsonify({"success": False, "message": "Admins only"}), 403

        payload = request.get_json(silent=True) or {}
        title = (payload.get("title") or "").strip()
        date = payload.get("date") or ""
        time = payload.get("time") or ""

        if not title or not date or not time:
            return jsonify({"success": False, "message": "Title, date and time are required"}), 400

        events.append({"title": title, "date": date, "time": time})
        save("events.json", events)
        return jsonify({"success": True})

    return jsonify(events)


@app.route("/events/delete", methods=["POST"])
@admin_required
def delete_event():
    payload = request.get_json(silent=True) or {}
    title = payload.get("title")
    events = load("events.json")
    remaining = [e for e in events if e["title"] != title]
    save("events.json", remaining)
    return jsonify({"success": True, "deleted": len(events) - len(remaining)})


@app.route("/calendar")
@login_required
def calendar_page():
    return render_template("calendar.html", is_admin=session.get("is_admin", False))


@app.route("/admin")
@admin_required
def admin_page():
    return render_template("admin.html")


# --- GLOBAL CHAT ---
@app.route("/chat", methods=["GET", "POST"])
@login_required
def global_chat():
    messages = load("chat.json")

    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        if not text:
            return jsonify({"success": False, "message": "Message can't be empty"}), 400

        messages.append({
            "user": session["username"],
            "text": text,
            "ts": datetime.utcnow().isoformat(),
        })
        save("chat.json", messages)
        return jsonify({"success": True})

    return jsonify(messages)


@app.route("/chat_page")
@login_required
def chat_page():
    return render_template("chat.html")


# --- DIRECT MESSAGES ---
@app.route("/users_page")
@login_required
def users_page():
    return render_template("users.html")


@app.route("/users")
@login_required
def get_users():
    return jsonify([u["username"] for u in load_users()])


@app.route("/chat/<username>")
@login_required
def chat_with(username):
    return render_template("chat_room.html", user=username)


@app.route("/messages/<username>")
@login_required
def get_messages(username):
    me = session.get("username")
    chat = [
        m for m in load("dm.json")
        if (m["from"] == me and m["to"] == username) or (m["from"] == username and m["to"] == me)
    ]
    return jsonify(chat)


@app.route("/send_dm", methods=["POST"])
@login_required
def send_dm():
    data = request.get_json(silent=True) or {}
    to = data.get("to")
    text = (data.get("text") or "").strip()

    if not to or not text:
        return jsonify({"success": False, "message": "Recipient and text are required"}), 400

    msgs = load("dm.json")
    msgs.append({"from": session["username"], "to": to, "text": text, "ts": datetime.utcnow().isoformat()})
    save("dm.json", msgs)
    return jsonify({"success": True})


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_ENV") != "production"
    app.run(debug=debug_mode)
