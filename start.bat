# Gamepad Monitor - Inicio Rápido
@echo off
echo ==============================================
echo   Gamepad Monitor - Sistema de Control
echo ==============================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado
    echo Descarga Python desde: https://python.org
    pause
    exit /b 1
)

echo [1/4] Instalando dependencias...
pip install -q -r api\requirements.txt

echo [2/4] Iniciando API en segundo plano...
start /B python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

echo [3/4] Esperando a que la API inicie...
timeout /t 3 /nobreak >nul

echo [4/4] Abriendo frontend...
start http://localhost:8000/docs
start python -m http.server 8080 -d frontend

echo.
echo ==============================================
echo   Sistema iniciado correctamente!
echo ==============================================
echo.
echo   Frontend:  http://localhost:8080
echo   API:       http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo.
echo Presiona Ctrl+C para detener el servidor
pause
