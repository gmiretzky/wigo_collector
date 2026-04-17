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

COMMIT_MSG="refactor(agents): update collector URL logic and timestamp generation

- Split COLLECTOR_URL into COLLECTOR_HOST and COLLECTOR_PORT for better configuration in Proxmox and Ubuntu agents.
- Replace deprecated datetime.utcnow() with datetime.now(timezone.utc) for better Python compatibility.
- Standardize timestamp formatting to ISO 8601 UTC."

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
