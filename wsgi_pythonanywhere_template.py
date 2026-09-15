"""
PythonAnywhere WSGI configuration template.

Do NOT rename or move this file into your project — PythonAnywhere already
creates its own WSGI config file per web app (Web tab -> "WSGI configuration
file" link, something like /var/www/yourusername_pythonanywhere_com_wsgi.py).

Open that existing file on PythonAnywhere and replace its contents with
what's below, adjusting the two paths/values marked CHANGE ME.
"""

import sys
import os

# CHANGE ME: the path to the folder you uploaded/cloned this project into.
project_home = '/home/yourusername/Church_project_fixed'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# ===== Environment variables =====
# PythonAnywhere's free tier doesn't have a separate "environment variables"
# UI, so we set them here instead. Paid accounts can also set these in the
# Web tab's "Environment variables" section, which is more secure since this
# file is otherwise readable by anyone with access to your PythonAnywhere
# account file listing.

# CHANGE ME: generate a real one, e.g. locally run:
#   python3 -c "import secrets; print(secrets.token_hex(32))"
os.environ['FLASK_SECRET_KEY'] = 'CHANGE-ME-to-a-random-64-char-hex-string'

os.environ['FLASK_ENV'] = 'production'

# CHANGE ME: only needed if you want "forgot password" emails to send.
# Leave these three unset (or delete the lines) if you're not using email yet.
os.environ['SMTP_HOST'] = 'smtp.gmail.com'
os.environ['SMTP_PORT'] = '587'
os.environ['SMTP_USER'] = 'your-address@gmail.com'
os.environ['SMTP_PASSWORD'] = 'your-16-char-app-password'
os.environ['SMTP_FROM'] = 'your-address@gmail.com'

# CHANGE ME: only needed if you run sync_lyrics.py from a scheduled task.
# os.environ['GEMINI_API_KEY'] = 'your-gemini-key'

from app import app as application  # noqa: E402
