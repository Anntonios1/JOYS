# Gamepad Monitor - Inicio Rápido PowerShell
# Ejecuta este script para iniciar todo el sistema

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   Gamepad Monitor - Sistema de Control" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ ERROR: Python no está instalado" -ForegroundColor Red
    Write-Host "  Descarga Python desde: https://python.org" -ForegroundColor Yellow
    pause
    exit 1
}

# Instalar dependencias
Write-Host "`n[1/4] Instalando dependencias..." -ForegroundColor Yellow
pip install -q -r api\requirements.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Dependencias instaladas" -ForegroundColor Green
} else {
    Write-Host "✗ Error instalando dependencias" -ForegroundColor Red
    pause
    exit 1
}

# Iniciar API
Write-Host "`n[2/4] Iniciando API..." -ForegroundColor Yellow
$apiJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
}
Write-Host "✓ API iniciada (Job ID: $($apiJob.Id))" -ForegroundColor Green

# Esperar a que la API inicie
Write-Host "`n[3/4] Esperando a que la API inicie..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Verificar que la API está corriendo
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000" -UseBasicParsing -TimeoutSec 5
    Write-Host "✓ API respondiendo correctamente" -ForegroundColor Green
} catch {
    Write-Host "⚠ API puede tardar unos segundos en iniciar" -ForegroundColor Yellow
}

# Iniciar servidor frontend
Write-Host "`n[4/4] Iniciando servidor frontend..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python -m http.server 8080 -d frontend
}
Write-Host "✓ Frontend iniciado (Job ID: $($frontendJob.Id))" -ForegroundColor Green

Start-Sleep -Seconds 2

# Abrir navegador
Write-Host "`n✓ Abriendo navegador..." -ForegroundColor Green
Start-Process "http://localhost:8080"
Start-Process "http://localhost:8000/docs"

Write-Host "`n" -NoNewline
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   Sistema iniciado correctamente!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend:  " -NoNewline
Write-Host "http://localhost:8080" -ForegroundColor Blue
Write-Host "  API:       " -NoNewline
Write-Host "http://localhost:8000" -ForegroundColor Blue
Write-Host "  API Docs:  " -NoNewline
Write-Host "http://localhost:8000/docs" -ForegroundColor Blue
Write-Host ""
Write-Host "  API Job:      $($apiJob.Id)" -ForegroundColor Gray
Write-Host "  Frontend Job: $($frontendJob.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "Presiona Ctrl+C para detener todo" -ForegroundColor Yellow

# Mantener script corriendo
try {
    while ($true) {
        # Verificar si los jobs siguen corriendo
        $apiState = Get-Job -Id $apiJob.Id | Select-Object -ExpandProperty State
        $frontendState = Get-Job -Id $frontendJob.Id | Select-Object -ExpandProperty State
        
        if ($apiState -ne "Running" -or $frontendState -ne "Running") {
            Write-Host "`n⚠ Un servicio se detuvo inesperadamente" -ForegroundColor Yellow
            break
        }
        
        Start-Sleep -Seconds 5
    }
} finally {
    Write-Host "`nDeteniendo servicios..." -ForegroundColor Yellow
    Stop-Job -Id $apiJob.Id
    Stop-Job -Id $frontendJob.Id
    Remove-Job -Id $apiJob.Id
    Remove-Job -Id $frontendJob.Id
    Write-Host "✓ Servicios detenidos" -ForegroundColor Green
}
