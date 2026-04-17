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

COMMIT_MSG="feat(collector): implement full-cycle AI analysis and notification refactoring

- Implement 'Full Cycle' AI endpoint (Analyze & Purge) in maintenance router.
- Refactor notification logic into a dedicated 'notifications' module.
- Add AI context extraction endpoint for external processing.
- Implement '---TRIM---' marker parsing in SIEM engine for dynamic Home Assistant triggers.
- Update default Gemini model to gemini-1.5-flash for improved performance/cost.
- Add 'Analyze & Purge' button to the dashboard UI with glassmorphism styling.
- Add 'last-report' endpoint to retrieve latest stored AI analysis."

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
