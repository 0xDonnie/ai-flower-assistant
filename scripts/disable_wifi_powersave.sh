#!/usr/bin/env bash
# Disable WiFi power-save on wlan0, now + on every boot.
# Needed on Pi Zero 2 W (Cypress chip) to keep SSH reachable after idle.

set -euo pipefail

echo "Disabling WiFi power-save now..."
sudo iw dev wlan0 set power_save off

echo "Installing persistent systemd service..."
sudo tee /etc/systemd/system/wifi-powersave-off.service > /dev/null <<'EOF'
[Unit]
Description=Disable WiFi power-save on wlan0
After=sys-subsystem-net-devices-wlan0.device

[Service]
Type=oneshot
ExecStart=/usr/sbin/iw dev wlan0 set power_save off
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable wifi-powersave-off.service

echo "Verifica stato power-save:"
iw dev wlan0 get power_save

echo "DONE — SSH ora rimane sempre raggiungibile."
