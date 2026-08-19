#!/usr/bin/env bash
# BT LEARNING robust build script (used by Render).
#
set -e
cd "$(dirname "$0")"

echo "► BT LEARNING build starting..."
echo "► Installing dependencies from requirements.txt..."

pip install --upgrade pip
pip install -r requirements.txt

echo "► Build complete."
