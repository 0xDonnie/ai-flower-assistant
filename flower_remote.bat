@echo off
REM Launcher for the Flower Remote GUI — double-click to open the button window.
start "" powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0scripts\flower_remote.ps1"
