# Abrir puerto 8000 en el Firewall de Windows
# Ejecutar como Administrador

Write-Host "🔥 Configurando Firewall de Windows para puerto 8000..." -ForegroundColor Yellow

# Eliminar regla existente si existe
Remove-NetFirewallRule -DisplayName "Gamepad Monitor API" -ErrorAction SilentlyContinue

# Crear nueva regla
New-NetFirewallRule -DisplayName "Gamepad Monitor API" `
                    -Direction Inbound `
                    -LocalPort 8000 `
                    -Protocol TCP `
                    -Action Allow `
                    -Profile Any `
                    -Description "Permite acceso al API de Gamepad Monitor desde red local"

Write-Host "✅ Regla de firewall creada exitosamente" -ForegroundColor Green
Write-Host ""
Write-Host "Ahora puedes acceder desde tu teléfono:" -ForegroundColor Cyan

# Obtener IP local
$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like "192.168.*"}).IPAddress
if ($localIP) {
    Write-Host "📱 http://$localIP`:8000" -ForegroundColor Green
} else {
    Write-Host "No se pudo detectar la IP local. Usa 'ipconfig' para encontrarla." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Para verificar que el servidor está escuchando:" -ForegroundColor Cyan
Write-Host "netstat -an | findstr :8000" -ForegroundColor White
