#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Andes Guide — one-click publish
#
#  Double-click this file in Finder to:
#    1. rebuild the map from locations.csv
#    2. commit the change
#    3. push it live to GitHub Pages
#
#  Your guide refreshes at https://slobbity.github.io/andes-guide/
#  about a minute after this finishes.
# ─────────────────────────────────────────────────────────────

cd "$(dirname "$0")" || exit 1

echo "================================================"
echo "   Publishing the Andes guide"
echo "================================================"
echo
echo "> Rebuilding map from locations.csv ..."
if ! python3 build.py; then
  echo
  echo "x  Build failed — fix the error shown above, then try again."
  echo
  read -n 1 -s -r -p "Press any key to close..."
  echo
  exit 1
fi

echo
echo "> Publishing to GitHub ..."
git add -A
if git diff --cached --quiet; then
  echo "   Nothing changed since last publish — you're already up to date."
else
  git commit -q -m "Update guide content — $(date '+%Y-%m-%d %H:%M')"
  if git push -q origin main; then
    echo "   Done. Your guide will refresh in about a minute at:"
    echo "   https://slobbity.github.io/andes-guide/"
  else
    echo "x  Push failed — check your internet connection and try again."
  fi
fi

echo
read -n 1 -s -r -p "Press any key to close..."
echo
