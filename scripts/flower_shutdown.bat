@echo off
REM Shuts down the Pi cleanly via SSH.
REM Requires SSH key auth + passwordless sudo for shutdown.

REM TODO: set PI_HOST below to your Pi's user@hostname-or-ip
set PI_HOST=pi@your-flower.local

echo.
echo  Shutting down the Pi...
ssh %PI_HOST% "sudo shutdown -h now"

echo.
echo  Command sent. Wait ~15 seconds, then unplug power.
echo.
pause
