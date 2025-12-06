# Script para reconectar Joy-Cons automáticamente
# Ejecutar como administrador

Write-Host "🎮 Reconectando Joy-Cons..." -ForegroundColor Cyan

# Buscar dispositivos Bluetooth emparejados pero desconectados
$bluetoothDevices = Get-PnpDevice -Class Bluetooth | Where-Object {
    $_.FriendlyName -like "*Joy-Con*" -and $_.Status -eq "Error"
}

if ($bluetoothDevices.Count -eq 0) {
    Write-Host "✅ No hay Joy-Cons desconectados" -ForegroundColor Green
    exit 0
}

foreach ($device in $bluetoothDevices) {
    Write-Host "🔄 Reconectando: $($device.FriendlyName)..." -ForegroundColor Yellow
    
    # Deshabilitar y habilitar el dispositivo
    Disable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false
    Start-Sleep -Milliseconds 500
    Enable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false
    Start-Sleep -Milliseconds 1000
}

Write-Host "✅ Proceso completado" -ForegroundColor Green
Write-Host "💡 Presiona un botón en cada Joy-Con para conectarlos" -ForegroundColor Cyan
