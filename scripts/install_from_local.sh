#!/usr/bin/env bash
# =============================================================================
# install_from_local — run on the Pi AFTER you've scp'd the project from your
# PC. Assumes flower_firstboot.sh already configured I2S/ALSA/system deps.
#
# Run from the Pi, with the repo at ~/ai-flower-assistant:
#   cd ~/ai-flower-assistant && bash scripts/install_from_local.sh
#
# What it does:
#   1. Verify we're on a Pi with system dependencies
#   2. Create Python venv under voice-assistant/.venv
#   3. pip install runtime dependencies
#   4. Download and install PicoClaw
#   5. Copy character files into PicoClaw workspace
#   6. Install and enable the systemd services
#   7. Final health check + ready message
# =============================================================================

set -euo pipefail

if [ ! -f /home/pi/.flower-firstboot-done ]; then
  echo "WARNING: /home/pi/.flower-firstboot-done not found."
  echo "Either flower_firstboot.sh hasn't run yet, or you're not on the Pi."
  read -r -p "Continue anyway? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || exit 1
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
echo "Installing from: $REPO"

# ----------------------------------------------------------------------------
# Python venv + requirements
# ----------------------------------------------------------------------------
echo "[1/6] Creating Python venv..."
python3 -m venv voice-assistant/.venv
# shellcheck source=/dev/null
source voice-assistant/.venv/bin/activate
pip install --upgrade pip wheel

echo "[2/6] Installing Python runtime deps..."
pip install \
  numpy \
  requests \
  python-dotenv \
  sounddevice \
  gpiozero \
  lgpio

# ----------------------------------------------------------------------------
# PicoClaw
# ----------------------------------------------------------------------------
echo "[3/6] Installing PicoClaw..."
if ! command -v picoclaw &>/dev/null; then
  curl -fsSL https://raw.githubusercontent.com/sipeed/picoclaw/main/install.sh | bash || {
    echo "WARNING: PicoClaw install script failed."
    echo "You can install it manually later from https://github.com/sipeed/picoclaw"
  }
fi

# ----------------------------------------------------------------------------
# Character files -> PicoClaw workspace
# ----------------------------------------------------------------------------
echo "[4/6] Copying character files to PicoClaw workspace..."
WORKSPACE="$HOME/.picoclaw/workspace"
mkdir -p "$WORKSPACE"
cp -v character/SOUL.md "$WORKSPACE/"
cp -v character/IDENTITY.md "$WORKSPACE/"
cp -v character/AGENTS.md "$WORKSPACE/"
if [ ! -f "$WORKSPACE/USER.md" ]; then
  cp -v character/USER.md.example "$WORKSPACE/USER.md"
  echo "  created $WORKSPACE/USER.md — EDIT IT with your name/city/preferences"
fi

# ----------------------------------------------------------------------------
# systemd services (flower-voice + picoclaw-gateway)
# ----------------------------------------------------------------------------
echo "[5/6] Installing systemd services..."
if [ -f systemd/flower-voice.service ]; then
  sudo cp systemd/flower-voice.service /etc/systemd/system/
fi
if [ -f systemd/flower-silence.service ]; then
  sudo cp systemd/flower-silence.service /etc/systemd/system/
fi
if [ -f systemd/picoclaw-gateway.service ]; then
  sudo cp systemd/picoclaw-gateway.service /etc/systemd/system/
fi
sudo systemctl daemon-reload
sudo systemctl enable flower-voice.service || true
sudo systemctl enable flower-silence.service || true
sudo systemctl enable picoclaw-gateway.service || true

# ----------------------------------------------------------------------------
# Health check
# ----------------------------------------------------------------------------
echo "[6/6] Health check..."
echo
aplay -l || true
echo
arecord -l || true
echo
echo "Audio cards should show:"
echo "  USB Audio (C-Media)    — capture (your mic)"
echo "  MAX98357A              — playback (your speaker)"
echo

WAV_COUNT=$(find voice-assistant/sounds -name "*.wav" 2>/dev/null | wc -l)
echo "WAV assets on disk: $WAV_COUNT"
if [ "$WAV_COUNT" -lt 1 ]; then
  echo "NOTE: no WAVs found under voice-assistant/sounds/. That's fine — the app"
  echo "      degrades gracefully; gestures just play silence until you drop"
  echo "      WAV files into sounds/{quips,morning,bedtime,startup,smalltalk,"
  echo "      special,hourly,status,music,indicators}/."
fi

if [ ! -f voice-assistant/.env ]; then
  echo "WARNING: voice-assistant/.env is missing!"
  echo "  Copy the template and fill in your API keys:"
  echo "    cp voice-assistant/.env.example voice-assistant/.env"
  echo "    nano voice-assistant/.env"
fi

echo
echo "================================================================="
echo "  Install complete."
echo
echo "  To start manually (test):"
echo "    cd ~/ai-flower-assistant/voice-assistant"
echo "    source .venv/bin/activate"
echo "    python voice_assistant.py"
echo
echo "  To start as a service (runs on boot):"
echo "    sudo systemctl start picoclaw-gateway"
echo "    sudo systemctl start flower-voice"
echo "================================================================="
