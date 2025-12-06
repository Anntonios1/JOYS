@echo off
title Gamepad Monitor Server
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "start_server.ps1"
pause
