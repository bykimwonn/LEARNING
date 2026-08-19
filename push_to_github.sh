#!/usr/bin/env bash
# BT LEARNING — push the whole project to GitHub, correctly.
# This pushes the ACTUAL files via git (no copy/paste, so nothing gets corrupted).
#
# Usage:
#   ./push_to_github.sh                    # if origin is already set
#   ./push_to_github.sh <repo-url>         # e.g. https://github.com/bykimwonn/BT-LEARNING.git
set -e
cd "$(dirname "$0")"

echo "=========================================="
echo " BT LEARNING - push to GitHub"
echo "=========================================="

# 1. Safety check: make sure build.sh is really a shell script (not README text)
echo ""
echo "► Checking build.sh is correct..."
head -1 build.sh | grep -q "#!/usr/bin/env bash" \
  && echo "  ✓ build.sh is a real shell script" \
  || { echo "  ✗ build.sh does NOT look like a shell script. Aborting."; exit 1; }

# 2. Safety check: requirements.txt resolves cleanly
echo "► Checking requirements.txt..."
if python3 -m pip install --dry-run -r requirements.txt >/dev/null; then
  echo "  ✓ requirements.txt is clean"
else
  echo "  ✗ requirements.txt has invalid lines. Aborting."
  exit 1
fi

# 3. Fresh git repo (removes any prior git history to avoid mixing)
echo "► Setting up a clean git repo..."
rm -rf .git
git init -q
git add -A
git commit -q -m "BT LEARNING - full project (clean push)"

# 4. Show what's about to be pushed (top-level)
echo "► Files being pushed:"
git ls-files | grep -v '^static/\|^templates/\|^__pycache__' | head -20
echo "  ... ($(git ls-files | wc -l) files total)"

# 5. Set the remote and push
REPO_URL="${1:-}"
if [ -n "$REPO_URL" ]; then
  git remote add origin "$REPO_URL"
else
  if ! git remote get-url origin >/dev/null 2>&1; then
    echo ""
    echo "✗ No git remote set. Pass the repo URL as the first argument:"
    echo "  ./push_to_github.sh https://github.com/bykimwonn/BT-LEARNING.git"
    exit 1
  fi
fi

git branch -M main
echo ""
echo "► Pushing to GitHub..."
git push -u origin main --force

echo ""
echo "✓ Done! Now in Render, go to your service → Manual Deploy → Deploy latest commit."
