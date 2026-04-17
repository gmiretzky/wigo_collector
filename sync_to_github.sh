#!/bin/bash

# Exit on error
set -e

# Check for required environment variables
if [ -z "$GIT_USER" ] || [ -z "$GIT_TOKEN" ]; then
    echo "Error: GIT_USER and GIT_TOKEN environment variables must be set."
    echo "Usage: export GIT_USER='your_username' && export GIT_TOKEN='your_token' && ./sync_to_github.sh"
    exit 1
fi

REPO_URL="github.com/gmiretzky/wigo_collector.git"
AUTH_REPO_URL="https://${GIT_USER}:${GIT_TOKEN}@${REPO_URL}"

echo "Initializing local git repository..."
if [ ! -d ".git" ]; then
    git init
fi

echo "Setting remote origin..."
# Remove existing origin if it exists
git remote remove origin 2>/dev/null || true
git remote add origin "$AUTH_REPO_URL"

echo "Configuring main branch..."
git branch -M main

echo "Adding files and committing..."
git add .

COMMIT_MSG="feat(devops): initialize git and sync wigo collector to github

- Initialize local git repository
- Configure remote origin with authentication via environment variables
- Add .gitignore to exclude sensitive configuration and temporary files
- Add data/config.yaml.example for setup guidance
- Prepare project for first push to gmiretzky/wigo_collector"

# Only commit if there are changes
if [ -n "$(git status --porcelain)" ]; then
    git commit -m "$COMMIT_MSG"
else
    echo "Nothing to commit, working tree clean. Proceeding to sync..."
fi

echo "Pulling existing remote changes (README.md) and rebasing..."
# This handles the existing README.md on the remote repo
git pull origin main --rebase --allow-unrelated-histories

echo "Performing first push to GitHub..."
git push -u origin main

echo "Done! Project synced to GitHub."
