@echo off
:: Script para eliminar Joy-Cons vinculados
:: Ejecuta el script PowerShell como administrador

echo Iniciando eliminador de Joy-Cons...
echo.

:: Verificar si ya tiene permisos de administrador
net session >nul 2>&1
if %errorLevel% == 0 (
    :: Ya es administrador, ejecutar directamente
    powershell -ExecutionPolicy Bypass -File "%~dp0remove_joycons.ps1"
) else (
    :: Solicitar permisos de administrador
    powershell -Command "Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0remove_joycons.ps1\"' -Verb RunAs"
)
