# Script para eliminar Joy-Cons vinculados de Windows
# Requiere permisos de administrador

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Eliminador de Joy-Cons Vinculados" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar permisos de administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️  Este script requiere permisos de administrador" -ForegroundColor Yellow
    Write-Host "   Ejecuta PowerShell como administrador y vuelve a intentar" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit
}

Write-Host "🔍 Buscando Joy-Cons vinculados..." -ForegroundColor Yellow
Write-Host ""

# Buscar dispositivos Bluetooth de Nintendo
$nintendoDevices = Get-PnpDevice | Where-Object { 
    $_.FriendlyName -like "*Joy-Con*" -or 
    $_.FriendlyName -like "*Nintendo*" -or
    $_.InstanceId -like "*VID_057E*PID_2006*" -or  # Joy-Con L
    $_.InstanceId -like "*VID_057E*PID_2007*"      # Joy-Con R
}

if ($nintendoDevices.Count -eq 0) {
    Write-Host "✅ No se encontraron Joy-Cons vinculados" -ForegroundColor Green
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit
}

Write-Host "📋 Joy-Cons encontrados:" -ForegroundColor Cyan
Write-Host ""

$deviceList = @()
$index = 1

foreach ($device in $nintendoDevices) {
    $status = if ($device.Status -eq "OK") { "✅ Conectado" } else { "⚠️  Desconectado" }
    Write-Host "[$index] $status - $($device.FriendlyName)" -ForegroundColor White
    Write-Host "    ID: $($device.InstanceId)" -ForegroundColor Gray
    Write-Host ""
    
    $deviceList += $device
    $index++
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$confirm = Read-Host "¿Deseas eliminar TODOS estos dispositivos? (S/N)"

if ($confirm -ne "S" -and $confirm -ne "s") {
    Write-Host ""
    Write-Host "❌ Operación cancelada" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit
}

Write-Host ""
Write-Host "🗑️  Eliminando dispositivos..." -ForegroundColor Yellow
Write-Host ""

$removed = 0
$failed = 0

foreach ($device in $deviceList) {
    try {
        Write-Host "Eliminando: $($device.FriendlyName)..." -NoNewline
        
        $instanceId = $device.InstanceId
        
        # Extraer la dirección MAC del Bluetooth del InstanceId
        # Formato: BTHENUM\DEV_XXXXXXXXXXXX\...
        if ($instanceId -match "DEV_([0-9A-F]{12})") {
            $macAddress = $matches[1]
            
            # Desinstalar el driver usando pnputil
            $result = pnputil /remove-device "$instanceId" 2>&1
            
            # Limpiar el registro de dispositivos Bluetooth
            $btRegPath = "HKLM:\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices\$macAddress"
            if (Test-Path $btRegPath) {
                Remove-Item -Path $btRegPath -Recurse -Force -ErrorAction SilentlyContinue
            }
            
            # También limpiar la cache de enum
            $enumPath = "HKLM:\SYSTEM\CurrentControlSet\Enum\$($instanceId.Replace('\','\\'))"
            if (Test-Path $enumPath) {
                Remove-Item -Path $enumPath -Recurse -Force -ErrorAction SilentlyContinue
            }
            
            Write-Host " ✅" -ForegroundColor Green
            $removed++
        } else {
            Write-Host " ❌ (no se pudo extraer MAC)" -ForegroundColor Red
            $failed++
        }
        
    } catch {
        Write-Host " ❌" -ForegroundColor Red
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Gray
        $failed++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "📊 Resumen:" -ForegroundColor Cyan
Write-Host "   ✅ Eliminados: $removed" -ForegroundColor Green
if ($failed -gt 0) {
    Write-Host "   ❌ Fallidos: $failed" -ForegroundColor Red
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($removed -gt 0) {
    Write-Host "✨ Los Joy-Cons han sido desvinculados del sistema" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 Tip: Para volver a vincularlos:" -ForegroundColor Yellow
    Write-Host "   1. Ve a Configuración > Bluetooth y dispositivos" -ForegroundColor Gray
    Write-Host "   2. Mantén presionado el botón SYNC en el Joy-Con" -ForegroundColor Gray
    Write-Host "   3. Selecciona 'Agregar dispositivo' en Windows" -ForegroundColor Gray
    Write-Host ""
    
    $restart = Read-Host "¿Deseas reiniciar ahora para aplicar todos los cambios? (S/N)"
    if ($restart -eq "S" -or $restart -eq "s") {
        Write-Host ""
        Write-Host "🔄 Reiniciando en 5 segundos..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        Restart-Computer -Force
    }
}

Write-Host ""
Read-Host "Presiona Enter para salir"
