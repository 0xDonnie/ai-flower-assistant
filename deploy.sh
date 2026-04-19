#!/bin/bash
# Deploy helper — pull latest from git and sync character files into the
# PicoClaw workspace. Run on the Pi.
set -e

REPO_DIR="${REPO_DIR:-$HOME/ai-flower-assistant}"
WORKSPACE="${WORKSPACE:-$HOME/.picoclaw/workspace}"

echo "Pulling latest from git..."
cd "$REPO_DIR"
git pull --ff-only

echo "Syncing character files..."
mkdir -p "$WORKSPACE"
cp "$REPO_DIR/character/SOUL.md"     "$WORKSPACE/SOUL.md"
cp "$REPO_DIR/character/AGENTS.md"   "$WORKSPACE/AGENTS.md"
cp "$REPO_DIR/character/IDENTITY.md" "$WORKSPACE/IDENTITY.md"
[ -f "$REPO_DIR/character/USER.md" ] && cp "$REPO_DIR/character/USER.md" "$WORKSPACE/USER.md"

echo "Done. Restart the voice service to apply changes:"
echo "  sudo systemctl restart flower-voice"
