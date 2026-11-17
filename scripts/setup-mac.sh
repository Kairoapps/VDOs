#!/usr/bin/env bash
# One-time Mac setup for VDOs. Run from the repo root: ./scripts/setup-mac.sh
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"

command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list git-lfs >/dev/null 2>&1 || brew install git-lfs
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
brew list --cask tailscale >/dev/null 2>&1 || brew install --cask tailscale

git lfs install
git lfs pull || true

PY="$(brew --prefix python@3.12)/bin/python3.12"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e .

[ -f .env ] || cp .env.example .env
mkdir -p data work reports media/raw/_retired media/music media/edited

# LaunchAgents: the video server (always on) and the worker (every 15 min:
# ingest, transcribe, render, cleanup, git push)
for name in serve worker; do
  PLIST="$HOME/Library/LaunchAgents/com.kairoapps.vdos.$name.plist"
  sed -e "s#__REPO__#$REPO#g" "scripts/com.kairoapps.vdos.$name.plist" > "$PLIST"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
done

cat <<EOF

Done. Remaining manual steps:
  1. Open Tailscale, sign in, then:   tailscale funnel --bg 8787
  2. Run:  tailscale funnel status   and put the https://...ts.net URL in .env as PUBLIC_BASE_URL
  3. Test: curl -sI \$PUBLIC_BASE_URL/does-not-exist   -> should return 404 from "vdos"
  4. Drop clips into media/raw/ and music into media/music/<mood>/
  5. Keep the Mac awake during posting windows (System Settings > Battery > prevent sleep on power adapter).
EOF
