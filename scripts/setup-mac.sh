#!/usr/bin/env bash
# One-time Mac setup for VDOs. The Mac only names new raw clips and uploads them to GitHub;
# editing, rendering and posting run in Claude's cloud. Run from the repo root: ./scripts/setup-mac.sh
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"

command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg      # ffprobe reads the recording date
brew list git-lfs >/dev/null 2>&1 || brew install git-lfs
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
git lfs install

PY="$(brew --prefix python@3.12)/bin/python3.12"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e .
mkdir -p media/raw

# Remove the old video-server agent if an earlier setup installed it
OLD="$HOME/Library/LaunchAgents/com.kairoapps.vdos.serve.plist"
[ -f "$OLD" ] && { launchctl unload "$OLD" 2>/dev/null || true; rm -f "$OLD"; }

# Uploader: every 15 min, name new clips in media/raw and push them (Git LFS)
PLIST="$HOME/Library/LaunchAgents/com.kairoapps.vdos.worker.plist"
sed -e "s#__REPO__#$REPO#g" scripts/com.kairoapps.vdos.worker.plist > "$PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "Done. Drop clips into media/raw/ (optional topic prefix: walk__anything.mov); they upload within 15 minutes."
