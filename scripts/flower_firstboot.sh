#!/usr/bin/env bash
# =============================================================================
# Flower first-boot setup
#
# This script runs automatically on the Pi's FIRST BOOT after you drop it into
# the BOOT partition of the microSD card and wire it up via cloud-init.
#
# What it does:
#   1. apt update + install system packages (python, alsa-utils, mpg123, ffmpeg)
#   2. Configure /boot/firmware/config.txt with I2S + MAX98357A overlay
#   3. Write /home/pi/.asoundrc (dmixer + softvol taming for the Pi Zero 2 W
#      over-amplification bug)
#   4. Set USB mic capture volume and AGC (C-Media CM108 specific numids)
#   5. Install a background silence streamer service so the amp never pops
#   6. Disable itself from systemd so it doesn't run again
#
# What it does NOT do:
#   - Install PicoClaw (requires GitHub auth; do it from install_from_local.sh)
#   - Copy user-supplied WAV assets (scp them manually)
#   - Start the voice-assistant service (needs the repo copied first)
#
# After this script finishes, you still need to:
#   1. scp the ai-flower-assistant folder from your PC to the Pi
#   2. Run install_from_local.sh on the Pi to do the app-level setup
#
# Triggered by:
#   /boot/firmware/firstrun.sh (legacy) or a cloud-init write_files + runcmd
#   block on newer Pi Imager releases. See docs/sd_card_setup.md for the
#   exact snippet to add.
# =============================================================================

set -uo pipefail
LOG=/var/log/flower-firstboot.log
exec > >(tee -a "$LOG") 2>&1
echo "=== flower-firstboot starting at $(date) ==="

# Wait for networking to come up (Pi Imager configures wpa_supplicant but
# doesn't necessarily block until connected)
echo "[1/8] Waiting for network..."
for i in {1..60}; do
  if ping -c1 -W2 8.8.8.8 &>/dev/null; then
    echo "  network up after ${i}s"
    break
  fi
  sleep 1
done

# ----------------------------------------------------------------------------
# 2. System packages
# ----------------------------------------------------------------------------
echo "[2/8] apt update + install..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 python3-pip python3-venv python3-dev libpython3-dev \
  alsa-utils mpg123 ffmpeg sox libportaudio2 \
  git curl unzip swig \
  libatlas-base-dev libffi-dev liblgpio-dev \
  build-essential

# ----------------------------------------------------------------------------
# 3. I2S + MAX98357A overlay
# ----------------------------------------------------------------------------
echo "[3/8] Enabling I2S + MAX98357A in /boot/firmware/config.txt..."
CONFIG=/boot/firmware/config.txt
if ! grep -q "^dtparam=i2s=on" "$CONFIG"; then
  echo "dtparam=i2s=on" >> "$CONFIG"
fi
if ! grep -q "^dtoverlay=max98357a" "$CONFIG"; then
  echo "dtoverlay=max98357a" >> "$CONFIG"
fi
# Disable the built-in BCM audio to avoid it claiming card 0
sed -i 's/^dtparam=audio=on/#dtparam=audio=on/' "$CONFIG" || true

# ----------------------------------------------------------------------------
# 4. ALSA config: dmixer (shared PCM) + softvol (tame the Pi Zero 2 W over-amp)
# ----------------------------------------------------------------------------
echo "[4/8] Writing /home/pi/.asoundrc..."
cat > /home/pi/.asoundrc <<'ASOUND'
pcm.dmixer {
    type dmix
    ipc_key 1024
    slave {
        pcm "hw:CARD=MAX98357A,DEV=0"
        period_size 2048
        buffer_size 16384
        rate 48000
        channels 1
        format S32_LE
    }
}

pcm.softvol {
    type softvol
    slave.pcm "dmixer"
    control { name "SoftMaster"; card MAX98357A }
    min_dB -20.0
    max_dB 0.0
}

pcm.speaker {
    type plug
    slave.pcm "softvol"
}

pcm.!default {
    type asym
    playback.pcm "speaker"
    capture.pcm "plughw:CARD=Device,DEV=0"
}
ASOUND
chown pi:pi /home/pi/.asoundrc

# ----------------------------------------------------------------------------
# 5. USB mic (C-Media CM108): max capture volume + AGC
#    Cards numbered at boot — we wrap in a oneshot that retries.
# ----------------------------------------------------------------------------
echo "[5/8] Installing USB mic gain systemd service..."
cat > /etc/systemd/system/flower-mic-gain.service <<'MICSERVICE'
[Unit]
Description=Flower USB mic capture gain (C-Media)
After=sound.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'for i in 1 2 3 4 5; do if amixer -c 0 cset numid=8 35 >/dev/null 2>&1; then amixer -c 0 cset numid=9 1 >/dev/null 2>&1; alsactl store; exit 0; fi; sleep 2; done; exit 0'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
MICSERVICE
systemctl enable flower-mic-gain.service

# ----------------------------------------------------------------------------
# 6. Silence streamer — keeps the I2S clock running so the MAX98357A amp
#    never powers down (which causes a loud pop when it powers back up).
# ----------------------------------------------------------------------------
echo "[6/8] Installing silence streamer service..."
cat > /etc/systemd/system/flower-silence.service <<'SILSERVICE'
[Unit]
Description=Flower I2S silence streamer (prevents amp power-down pop)
After=sound.target

[Service]
User=pi
ExecStart=/usr/bin/aplay -D speaker -f S16_LE -r 48000 -c 1 /dev/zero
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SILSERVICE
systemctl enable flower-silence.service

# Disable WiFi power-save so SSH stays reachable after idle periods.
# The Pi Zero 2 W's Cypress chip aggressively sleeps the radio inbound side,
# leaving the Pi reachable for outbound (API calls) but dropping inbound
# (SSH, ping) after a few minutes.
echo "[6.5/8] Installing WiFi power-save disable service..."
cat > /etc/systemd/system/wifi-powersave-off.service <<'WIFIPSSERVICE'
[Unit]
Description=Disable WiFi power-save on wlan0
After=sys-subsystem-net-devices-wlan0.device

[Service]
Type=oneshot
ExecStart=/usr/sbin/iw dev wlan0 set power_save off
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
WIFIPSSERVICE
systemctl enable wifi-powersave-off.service

# Allow pi user to run shutdown without password (used by the GUI remote).
echo "[6.7/8] Allowing passwordless shutdown for pi..."
echo "pi ALL=(ALL) NOPASSWD: /sbin/shutdown, /usr/sbin/shutdown" | sudo tee /etc/sudoers.d/flower-shutdown > /dev/null
sudo chmod 0440 /etc/sudoers.d/flower-shutdown

# ----------------------------------------------------------------------------
# 7. Mark setup as done + leave a READY marker
# ----------------------------------------------------------------------------
echo "[7/8] Marking first-boot complete..."
touch /home/pi/.flower-firstboot-done
chown pi:pi /home/pi/.flower-firstboot-done

# ----------------------------------------------------------------------------
# 8. Disable self so we never run again
# ----------------------------------------------------------------------------
echo "[8/8] Disabling flower-firstboot.service..."
systemctl disable flower-firstboot.service || true
rm -f /etc/systemd/system/flower-firstboot.service || true

echo "=== flower-firstboot finished at $(date) ==="
echo
echo "Next steps (from your PC):"
echo "  1. Reboot the Pi so the I2S overlay takes effect:"
echo "     ssh pi@your-flower.local 'sudo reboot'"
echo "  2. Verify the audio card shows up (should see MAX98357A):"
echo "     ssh pi@your-flower.local 'aplay -l'"
echo "  3. Copy the ai-flower-assistant folder from your PC to the Pi:"
echo "     scp -r /path/to/ai-flower-assistant pi@your-flower.local:~/"
echo "  4. Run the app-level install on the Pi:"
echo "     ssh pi@your-flower.local 'cd ~/ai-flower-assistant && bash scripts/install_from_local.sh'"

# Schedule a reboot so the I2S overlay takes effect
shutdown -r +1 "Flower first-boot setup complete. Rebooting in 1 minute so I2S activates."
