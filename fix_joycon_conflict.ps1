# Script para resolver conflicto de direcciones de Joy-Con
# EJECUTAR COMO ADMINISTRADOR

Write-Host "🔧 Reparando conflicto de Joy-Cons..." -ForegroundColor Cyan
Write-Host ""

# 1. Buscar Joy-Cons con problemas
$joycons = Get-PnpDevice | Where-Object {
    $_.FriendlyName -like "*Joy-Con*" -or 
    $_.InstanceId -like "*VID_057E*PID_2006*" -or 
    $_.InstanceId -like "*VID_057E*PID_2007*"
}

if ($joycons) {
    Write-Host "📱 Joy-Cons encontrados:" -ForegroundColor Yellow
    foreach ($jc in $joycons) {
        Write-Host "   • $($jc.FriendlyName) - Estado: $($jc.Status)" -ForegroundColor Gray
    }
    Write-Host ""
    
    # 2. Remover dispositivos con error
    $problemDevices = $joycons | Where-Object { $_.Status -ne "OK" }
    
    if ($problemDevices) {
        Write-Host "🗑️  Removiendo dispositivos con conflicto..." -ForegroundColor Yellow
        foreach ($device in $problemDevices) {
            try {
                Write-Host "   → Removiendo: $($device.FriendlyName)" -ForegroundColor Gray
                $device | Remove-PnpDevice -Confirm:$false -ErrorAction Stop
                Write-Host "   ✅ Removido" -ForegroundColor Green
            } catch {
                Write-Host "   ⚠️  Error: $_" -ForegroundColor Red
            }
        }
        Write-Host ""
    }
    
    # 3. Escanear cambios de hardware
    Write-Host "🔄 Re-escaneando hardware..." -ForegroundColor Cyan
    $devicesClass = [wmiclass]"Win32_PnPEntity"
    $devicesClass.psbase.Scope.Options.EnablePrivileges = $true
    $null = (Get-WmiObject Win32_PnPEntity | Where-Object {$_.ConfigManagerErrorCode -eq 0})[0].psbase.Scope.Path.Server
    
    # Forzar re-escaneo
    pnputil /scan-devices
    
    Start-Sleep -Seconds 2
    Write-Host "✅ Escaneo completado" -ForegroundColor Green
    Write-Host ""
    
    # 4. Mostrar estado actual
    Write-Host "📊 Estado actual:" -ForegroundColor Cyan
    $joycons = Get-PnpDevice | Where-Object {
        $_.FriendlyName -like "*Joy-Con*" -or 
        $_.InstanceId -like "*VID_057E*PID_2006*" -or 
        $_.InstanceId -like "*VID_057E*PID_2007*"
    }
    
    if ($joycons) {
        foreach ($jc in $joycons) {
            $statusColor = if ($jc.Status -eq "OK") { "Green" } else { "Red" }
            Write-Host "   • $($jc.FriendlyName): " -NoNewline
            Write-Host "$($jc.Status)" -ForegroundColor $statusColor
        }
    } else {
        Write-Host "   ℹ️  No hay Joy-Cons detectados" -ForegroundColor Yellow
    }
    
} else {
    Write-Host "❌ No se encontraron Joy-Cons" -ForegroundColor Red
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "📝 SIGUIENTE PASO:" -ForegroundColor Cyan
Write-Host "   1. Presiona el botón de sincronización en cada Joy-Con" -ForegroundColor Yellow
Write-Host "   2. Ve a Configuración → Bluetooth y dispositivos" -ForegroundColor Yellow
Write-Host "   3. Agregar dispositivo → Bluetooth" -ForegroundColor Yellow
Write-Host "   4. Selecciona cada Joy-Con cuando aparezca" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
