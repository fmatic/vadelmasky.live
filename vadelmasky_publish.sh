#!/bin/bash
set -e

cd /home/dietpi/vadelmasky

TODAY=$(date -u +%F)

if [ -f .git/index.lock ]; then
  echo "Git index.lock exists, skipping publish"
  exit 0
fi


echo "=== VadelmaSky publish ==="
echo "UTC day: $TODAY"


# ------------------------------------------------------------
# 1. Update repository first
# ------------------------------------------------------------

git pull --rebase --autostash origin main


# ------------------------------------------------------------
# 2. Stage generated data and source files
# ------------------------------------------------------------

git add docs messages acars_collector.py vadelmasky_logger.py

# Publish script itself is version controlled too
git add vadelmasky_publish.sh


# ------------------------------------------------------------
# 3. Commit and push if anything changed
# ------------------------------------------------------------

if git diff --cached --quiet; then

  echo "No changes to publish"

else

  git commit -m "Auto update VadelmaSky $(date -u '+%Y-%m-%d %H:%M UTC')"

  git push

  echo "Publish complete"

fi


# ------------------------------------------------------------
# 4. Remove historical JSON files from Raspberry worktree
#
# IMPORTANT:
# Files remain tracked in Git and available on GitHub Pages.
# Only today's JSON remains physically in docs/data/.
# ------------------------------------------------------------

echo "Cleaning local history..."

for f in docs/data/*.json; do

  [ -e "$f" ] || continue

  filename=$(basename "$f")

  if [ "$filename" = "$TODAY.json" ]; then
    continue
  fi

  # Only remove files already safely tracked by Git
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then

    echo "Archiving locally: $filename"

    git update-index --skip-worktree "$f"

    rm -f "$f"

  else

    echo "WARNING: $filename is not tracked by Git - keeping local copy"

  fi

done


echo "Local data files:"
ls -lh docs/data/

echo "=== Done ==="