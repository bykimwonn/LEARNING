#!/usr/bin/env bash
# BT LEARNING local launcher (development / preview)
#   ./run.sh              -> SQLite database, port 8000
#   ./run.sh 5000         -> custom port
#   DATABASE_URL=... ./run.sh  -> use a PostgreSQL database instead
#   ADMIN_EMAIL=... ADMIN_PASSWORD=... ./run.sh -> create initial admin account
set -e
cd "$(dirname "$0")"

PORT="${1:-8000}"

echo "► Installing/checking dependencies..."
pip install -q flask sqlalchemy gunicorn
pip install -q psycopg2-binary pypdf || echo "  (note: psycopg2/pypdf optional for local run)"

echo "► Initializing database schema ..."
python3 -c "import db; db.init_db()"

echo "► Starting BT LEARNING on http://localhost:$PORT"
echo "  (Ctrl+C to stop)"
export FLASK_DEBUG=1
PORT="$PORT" python3 app.py
