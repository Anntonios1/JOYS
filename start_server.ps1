# Script para iniciar el servidor de Gamepad Monitor
# Ejecutar como: .\start_server.ps1

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   🎮 Gamepad Monitor API Server" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# Verificar Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python no encontrado. Instala Python 3.11+" -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "✅ $pythonVersion" -ForegroundColor Green

# Cambiar al directorio de la API
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiPath = Join-Path $scriptPath "api"

if (-not (Test-Path $apiPath)) {
    Write-Host "❌ Directorio 'api' no encontrado" -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Set-Location $apiPath
Write-Host "📁 Directorio: $apiPath" -ForegroundColor Yellow
Write-Host ""

# Verificar dependencias
Write-Host "🔍 Verificando dependencias..." -ForegroundColor Yellow
$packages = @("fastapi", "uvicorn", "hidapi")
$missing = @()

foreach ($package in $packages) {
    python -c "import $package" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $missing += $package
    }
}

if ($missing.Count -gt 0) {
    Write-Host "❌ Faltan dependencias: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Instalando..." -ForegroundColor Yellow
    pip install fastapi uvicorn hidapi
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "🚀 Iniciando servidor..." -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📡 URL: http://localhost:8000" -ForegroundColor Cyan
Write-Host "🌐 Frontend: http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Presiona Ctrl+C para detener el servidor" -ForegroundColor Yellow
Write-Host ""

# Iniciar servidor
try {
    python main.py
}
catch {
    Write-Host ""
    Write-Host "❌ Error al iniciar servidor: $_" -ForegroundColor Red
}
finally {
    Write-Host ""
    Write-Host "🛑 Servidor detenido" -ForegroundColor Yellow
    Read-Host "Presiona Enter para cerrar"
}
