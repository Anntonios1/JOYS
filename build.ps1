# Script de compilación automatizada
# Ejecutar como: .\build.ps1

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     🎮 Gamepad Monitor - Build Automatizado 🎮         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Paso 1: Limpiar builds anteriores
Write-Host "🗑️  Paso 1/5: Limpiando builds anteriores..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "*.spec") { Remove-Item -Force "*.spec" }
Write-Host "   ✅ Limpieza completada" -ForegroundColor Green
Write-Host ""

# Paso 2: Verificar dependencias
Write-Host "📦 Paso 2/5: Verificando dependencias..." -ForegroundColor Yellow
$requiredPackages = @("PyQt6", "fastapi", "uvicorn", "pyinstaller")
$missingPackages = @()

foreach ($package in $requiredPackages) {
    $installed = python -c "import $package; print('OK')" 2>$null
    if ($installed -eq "OK") {
        Write-Host "   ✅ $package instalado" -ForegroundColor Green
    } else {
        Write-Host "   ❌ $package NO instalado" -ForegroundColor Red
        $missingPackages += $package
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠️  Instalando paquetes faltantes..." -ForegroundColor Yellow
    pip install -r requirements_build.txt
    Write-Host ""
}

# Paso 3: Copiar archivos necesarios
Write-Host "📋 Paso 3/5: Preparando archivos..." -ForegroundColor Yellow
# Crear spec si no existe
if (!(Test-Path "gamepad_monitor.spec")) {
    Copy-Item "gamepad_monitor.spec.template" "gamepad_monitor.spec" -ErrorAction SilentlyContinue
}
Write-Host "   ✅ Archivos preparados" -ForegroundColor Green
Write-Host ""

# Paso 4: Compilar con PyInstaller
Write-Host "🔨 Paso 4/5: Compilando con PyInstaller..." -ForegroundColor Yellow
Write-Host "   (Esto puede tardar varios minutos)" -ForegroundColor Gray
Write-Host ""

pyinstaller gamepad_monitor.spec

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "   ✅ Compilación exitosa" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "   ❌ Error en la compilación" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Paso 5: Verificar resultado
Write-Host "✔️  Paso 5/5: Verificando resultado..." -ForegroundColor Yellow

if (Test-Path "dist\GamepadMonitor.exe") {
    $fileSize = (Get-Item "dist\GamepadMonitor.exe").Length / 1MB
    
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║              ✅ BUILD COMPLETADO ✅                      ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "📦 Ejecutable creado:" -ForegroundColor Cyan
    Write-Host "   📁 Ubicación: $(Get-Location)\dist\GamepadMonitor.exe" -ForegroundColor White
    Write-Host "   💾 Tamaño: $([math]::Round($fileSize, 2)) MB" -ForegroundColor White
    Write-Host ""
    Write-Host "🚀 Para ejecutar:" -ForegroundColor Cyan
    Write-Host "   cd dist" -ForegroundColor White
    Write-Host "   .\GamepadMonitor.exe" -ForegroundColor White
    Write-Host ""
    Write-Host "📦 Para distribuir:" -ForegroundColor Cyan
    Write-Host "   El archivo .exe es completamente portátil" -ForegroundColor White
    Write-Host "   No requiere instalación de Python" -ForegroundColor White
    Write-Host ""
    
    # Opción de ejecutar inmediatamente
    $response = Read-Host "¿Deseas ejecutar el programa ahora? (S/N)"
    if ($response -eq "S" -or $response -eq "s") {
        Write-Host ""
        Write-Host "▶️  Ejecutando GamepadMonitor..." -ForegroundColor Cyan
        Start-Process "dist\GamepadMonitor.exe"
    }
} else {
    Write-Host ""
    Write-Host "❌ Error: No se encontró el ejecutable" -ForegroundColor Red
    Write-Host "   Revisa los logs de PyInstaller arriba" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "   Gracias por usar Gamepad Monitor! 🎮✨" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
