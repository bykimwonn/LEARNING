#!/usr/bin/env bash
# BT LEARNING robust build script (used by Render).
#
# This script installs the app's dependencies EXPLICITLY and NEVER reads
# requirements.txt. That way, no matter what ends up in requirements.txt
# (stray Python like "import db, io, app as appmod", shell like "set -e",
# or anything else), the build ALWAYS succeeds.
#
# Why: the same corrupt-file bug has recurred several times on Render. The
# only way to guarantee a successful build is to not depend on that file at all.
set -e
cd "$(dirname "$0")"

echo "► BT LEARNING build starting..."
echo "► requirements.txt is IGNORED on purpose. Installing core deps explicitly..."

pip install --upgrade pip

pip install \
  "flask>=3.0" \
  "sqlalchemy>=2.0" \
  "psycopg2-binary>=2.9" \
  "gunicorn>=21.0" \
  "pypdf>=4.0" \
  "groq>=1.0"

echo "► Build complete."
