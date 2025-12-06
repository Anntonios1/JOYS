@echo off
title Gamepad Monitor Overlay v2
cd /d "%~dp0"

REM Verificar si el API está corriendo
curl -s http://localhost:8000/api/devices >nul 2>&1
if errorlevel 1 (
    echo ⚠️ El servidor API no parece estar corriendo.
    echo    Inicia primero: python api_v2/main.py
    echo.
    echo ¿Iniciar el overlay de todas formas? (S/N)
    set /p continue="> "
    if /i not "%continue%"=="S" exit /b
)

echo 🎮 Iniciando Gamepad Monitor Overlay v2...
start "" pythonw gamepad_overlay_v2.py
