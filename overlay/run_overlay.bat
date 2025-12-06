@echo off
title Gamepad Monitor Overlay
cd /d "%~dp0"

REM Usar pythonw para que no aparezca ventana de consola
start "" pythonw gamepad_overlay.py

REM Si prefieres ver la consola para debug, usa:
REM python gamepad_overlay.py
