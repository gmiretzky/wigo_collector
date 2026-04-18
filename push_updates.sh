#!/bin/bash

# Exit on error
set -e

# Check for required environment variables
if [ -z "$GIT_USER" ] || [ -z "$GIT_TOKEN" ]; then
    echo "Error: GIT_USER and GIT_TOKEN environment variables must be set."
    echo "Usage: export GIT_USER='your_username' && export GIT_TOKEN='your_token' && ./push_updates.sh"
    exit 1
fi

REPO_URL="github.com/gmiretzky/wigo_collector.git"
AUTH_REPO_URL="https://${GIT_USER}:${GIT_TOKEN}@${REPO_URL}"

echo "Adding changes..."
git add .

COMMIT_MSG="feat(collector): implement log deduplication, health digests, and maintenance upgrades

- Implement log deduplication logic with 'count' tracking in LogEntry.
- Add routine log filtering (e.g., auth sessions) to optimize AI token usage.
- Upgrade maintenance endpoints:
  - 'purge' now supports targeted days (0 for full wipe).
  - 'context' now supports machine/IP filtering and syslog mapping integration.
- Implement 'Health Digest' concept: ranking logs and aggregating metrics for AI.
- Add optional AI analysis forwarding to an external webhook.
- Update README.md with comprehensive project documentation and API guide."

echo "Committing..."
if [ -n "$(git status --porcelain)" ]; then
    git commit -m "$COMMIT_MSG"
else
    echo "Nothing new to commit."
fi

echo "Pushing updates to GitHub..."
# Ensure the remote URL is updated with latest token
git remote set-url origin "$AUTH_REPO_URL"
git push origin main

echo "Done! Updates pushed to GitHub."
