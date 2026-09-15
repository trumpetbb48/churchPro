# Body of Christ — Church App

## Setup

```bash
pip install -r requirements.txt

# Required: a real secret key for signing session cookies
export FLASK_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"

# Only needed if you run sync_lyrics.py
export GEMINI_API_KEY="your-gemini-key"

# In production (real deployment, behind HTTPS), also set:
export FLASK_ENV=production

# Required for "forgot password" emails to actually send:
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-sending-address@gmail.com"
export SMTP_PASSWORD="your-app-password"
export SMTP_FROM="your-sending-address@gmail.com"   # optional, defaults to SMTP_USER

python3 app.py
```

### Setting up email sending

The "forgot password" flow needs a real SMTP account to send from. A few options:

- **Gmail**: create an [App Password](https://myaccount.google.com/apppasswords) on the sending Google account (regular Gmail passwords won't work for SMTP), then use `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`.
- **A transactional email service** (SendGrid, Mailgun, Postmark, etc.): they each give you an SMTP host/username/password — use those instead. These tend to be more reliable for automated app emails than a personal Gmail account.

Until `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD` are set, the "Forgot password" page will tell the user email isn't configured yet, rather than failing silently.

**Also update `users.json`**: each account currently has a placeholder email like `enock@example.com` — replace these with real addresses before relying on the reset flow, or reset links will go nowhere.

## First login

Accounts live in `users.json` with hashed passwords — there's no shared
"admin password" anymore. Initial accounts and their one-time passwords are
in `INITIAL_CREDENTIALS.txt`.

**Do this before deploying anywhere real:**
1. Distribute the credentials in `INITIAL_CREDENTIALS.txt` securely (in
   person, or an encrypted channel) — not over plain email/SMS.
2. Delete `INITIAL_CREDENTIALS.txt` afterwards. It's plaintext.
3. There's no self-service password change UI yet — add one, or rotate
   `users.json` passwords manually with `werkzeug.security.generate_password_hash`
   when someone needs a new password.

## What changed from the original version

- **Removed the hardcoded, live Gemini API key** from `sync_lyrics.py`.
  If you're reusing this codebase, treat that old key as leaked — revoke it.
- **Removed the hardcoded Flask `secret_key`** and single shared admin
  password (`"admin123"`) — replaced with per-user accounts and hashed
  passwords in `users.json`.
- **Added "Forgot password" (emailed reset link) and "Change password"**
  pages. Reset links are single-use, random tokens that expire after 30
  minutes (`password_resets.json`), and the forgot-password page always
  shows the same message whether or not the account exists, so it can't be
  used to check who has an account.
- **Every route now requires login**, and admin-only actions (adding
  songs/events, deleting events, the `/admin` page) require `is_admin`.
  Previously almost all of these were open to anyone who could reach the
  server.
- **Fixed a stored XSS**: song titles and chat messages were inserted with
  `innerHTML`, so a malicious title/message could run JavaScript for every
  visitor. Now built with `textContent`/DOM methods.
- **Filled in routes the templates already called but that didn't exist**:
  `/logout`, `/users_page`, `/chat/<username>`, `/chat` (GET/POST), and
  `/favorite`. The calendar's delete button also had no matching
  `deleteEvent()` function or backend route — both added.
- **`debug=True` is now off by default** and only enabled when
  `FLASK_ENV` isn't `production`. Debug mode's interactive console is a
  remote-code-execution risk if the app is ever reachable from outside your
  machine.
- Session cookies are now `HttpOnly` + `SameSite=Lax`, and `Secure` once
  `FLASK_ENV=production` is set.
- `/song/<id>` and lyric/event submissions now validate input instead of
  crashing with a 500 or silently accepting empty data.
- Removed unrelated leftover files (`composer-setup.php`, empty `composer`/
  `npm` placeholder files, an empty `package-lock.json`) that didn't belong
  in this Python project.
- **Cleaned up `lyrics.json`**: removed one blank/empty entry, merged a
  true duplicate ("Blessed Assurance" existed twice — kept the fuller
  version and dropped the truncated one), fixed one OCR-style typo
  (`parraīt` → `paraît`), and normalized straight `'` apostrophes to proper
  typographic `’` throughout for consistency across the English, French,
  and Creole lyrics.
- **All JSON file reads/writes now use explicit UTF-8 encoding** and
  `ensure_ascii=False`. Previously, saving through the app (adding a song,
  sending a chat message, etc.) would re-serialize the whole file with
  non-ASCII characters escaped as `\uXXXX` sequences — harmless for the app
  itself, but it turns accented French/Creole text into an unreadable mess
  if you ever open the file directly. This is now consistent everywhere.
- **Adding a song now also rejects duplicate lyrics under a different
  title**, not just an exact duplicate title — same check added to
  `sync_lyrics.py` so future scrapes won't reintroduce duplicates like the
  one that got cleaned up above.
- No audio features exist in this version — the app is text lyrics only
  (song titles + lyric text), no audio playback or file uploads.
- **Self-service account creation**: a "Create one" link on the login page
  now leads to `/register`, where anyone can make their own account (name,
  email, password) instead of needing an admin to hand-edit `users.json`.
  New accounts are never admins by default — you'd still flip `is_admin`
  to `true` for someone in `users.json` yourself if they need admin access.
  Duplicate usernames/emails and short passwords are rejected with a clear
  message.
- **Admin page now has song management**: an "Edit" and "Delete" button next
  to every song, and a "🔄 Sync New Songs" button that runs the same
  scraping/merging logic as `sync_lyrics.py` directly from the browser (no
  Bash console needed). It uses the same duplicate-title/duplicate-lyrics
  checks as everywhere else, and fails with a clear on-page message instead
  of crashing if `GEMINI_API_KEY` isn't set or the source site is
  unreachable — useful since PythonAnywhere's free tier has no scheduled
  tasks, so this is how you'll pull in new songs going forward.
- **Fixed the actual "duplicate lyrics" bug**: it wasn't the data — two
  things in the code caused it. First, `/song/<id>` used to identify a song
  by its *position* in the list (1st, 2nd, 3rd...), but the songbook page
  linked to songs using their position in whatever was currently on
  screen — which is different from their real position once you filter to
  Favorites. That mismatch could open the wrong song entirely. Song pages
  are now looked up by title, so this can't happen regardless of filtering
  or reordering. Second, `song_detail.html` had a leftover section that
  rendered the lyrics a second time inside an unused audio player — so a
  single song's page could visibly show its own lyrics twice. Both are
  removed.

## Pushing to GitHub, then pulling on PythonAnywhere

1. **Before your first commit**, double check `.gitignore` is in place (it is,
   in this zip) — it keeps `INITIAL_CREDENTIALS.txt` and `password_resets.json`
   out of git, since both hold sensitive data and shouldn't end up in a
   public repo.
2. From this folder:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/your-repo.git
   git push -u origin main
   ```
3. **On PythonAnywhere**, open a Bash console and clone it:
   ```bash
   git clone https://github.com/yourusername/your-repo.git Church_project_fixed
   cd Church_project_fixed
   mkvirtualenv --python=python3.10 church-env
   pip install -r requirements.txt
   ```
4. Continue from step 3 in the "Deploying to PythonAnywhere" section below
   (creating the web app, WSGI file, etc.).
5. **After that first clone**, whenever you push new commits to GitHub, just
   run `git pull` in the same PythonAnywhere Bash console folder, then hit
   **Reload** on the Web tab. Note: if `lyrics.json`/`events.json`/etc. have
   been edited live on the server (e.g. someone added a song through the
   admin page), `git pull` can conflict with those changes — `git stash`
   before pulling, then `git stash pop` after, if that happens.

## Deploying to PythonAnywhere

1. **Upload the project.** Easiest way: zip this folder, then on PythonAnywhere go to the **Files** tab, upload the zip, and unzip it from a **Bash console** (`unzip Church_project_fixed.zip`). Or push it to GitHub and `git clone` it from a Bash console instead.

2. **Create a virtualenv and install dependencies** (in a PythonAnywhere Bash console):
   ```bash
   cd ~/Church_project_fixed
   mkvirtualenv --python=python3.10 church-env
   pip install -r requirements.txt
   ```

3. **Create a new web app**: Web tab -> "Add a new web app" -> choose **Manual configuration** (not the Flask template) -> pick the same Python version as your virtualenv.

4. **Point it at your virtualenv**: on the Web tab, under "Virtualenv", enter the path shown after `mkvirtualenv` (usually `/home/yourusername/.virtualenvs/church-env`).

5. **Set up the WSGI file**: click the "WSGI configuration file" link on the Web tab. Open `wsgi_pythonanywhere_template.py` from this project, copy its contents in, and replace the two `CHANGE ME` sections with your actual project path and a real secret key. Save.

6. **Static files (optional but recommended)**: on the Web tab's "Static files" section, add a mapping URL `/static/` -> `/home/yourusername/Church_project_fixed/static/` so PythonAnywhere serves images/CSS/JS directly instead of through Flask.

7. Hit the green **Reload** button on the Web tab, then open your `yourusername.pythonanywhere.com` URL.

8. Log in with an account from `INITIAL_CREDENTIALS.txt`, then delete that file from the server (Files tab, or `rm INITIAL_CREDENTIALS.txt` in a Bash console) — it's plaintext passwords.

**Free-tier notes:**
- Free PythonAnywhere accounts can only make outbound requests to a limited allowlist of sites — Gmail's SMTP servers currently work, but double-check if you use a different email provider and reset emails aren't arriving.
- Free accounts also only run one worker and go to sleep after a few months of inactivity; that's fine for this app's traffic level.

## Still worth doing next

- JSON-file storage has no locking — fine for a handful of concurrent users,
  but a real database (SQLite is an easy first step) avoids write races as
  usage grows.
- Rate-limit `/login` and `/forgot_password` to slow down password guessing
  and email-spam abuse.
- Let an admin add/remove users and set/see email addresses from the
  `/admin` page instead of hand-editing `users.json`.
