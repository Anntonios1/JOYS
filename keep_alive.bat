@echo off
echo ========================================
echo   MANTENER JOY-CONS CONECTADOS
echo ========================================
echo.
echo Este script evita que los Joy-Cons se desconecten
echo manteniendo una conexion activa constantemente.
echo.
echo Presiona Ctrl+C para detener
echo.
pause

cd /d "%~dp0"
python keep_joycons_alive.py
