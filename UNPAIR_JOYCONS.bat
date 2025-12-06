@echo off
echo Iniciando desemparejador de Joy-Cons...

:: Verificar permisos de administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Solicitando permisos de administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Ejecutar el script de PowerShell
powershell -ExecutionPolicy Bypass -File "%~dp0unpair_joycons.ps1"
