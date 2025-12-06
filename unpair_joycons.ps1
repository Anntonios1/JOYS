# Script para desemparejar Joy-Cons usando Bluetooth de Windows
# Requiere permisos de administrador

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Desemparejador de Joy-Cons" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar permisos de administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Este script requiere permisos de administrador" -ForegroundColor Yellow
    Write-Host "Ejecuta PowerShell como administrador y vuelve a intentar" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit
}

Write-Host "Buscando Joy-Cons emparejados..." -ForegroundColor Yellow
Write-Host ""

# Cargar la API de Bluetooth de Windows
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

Function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

[Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType = WindowsRuntime] | Out-Null
[Windows.Devices.Bluetooth.BluetoothDevice, Windows.Devices.Bluetooth, ContentType = WindowsRuntime] | Out-Null

# Buscar todos los dispositivos Bluetooth emparejados
$deviceSelector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelector()
$findDevicesOp = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($deviceSelector)
$devices = Await $findDevicesOp ([Windows.Devices.Enumeration.DeviceInformationCollection])

$joycons = @()
$index = 1

foreach ($device in $devices) {
    if ($device.Name -like "*Joy-Con*" -or $device.Name -like "*Nintendo*") {
        Write-Host "[$index] $($device.Name)" -ForegroundColor White
        Write-Host "    ID: $($device.Id)" -ForegroundColor Gray
        Write-Host "    Estado: Emparejado" -ForegroundColor Green
        Write-Host ""
        
        $joycons += $device
        $index++
    }
}

if ($joycons.Count -eq 0) {
    Write-Host "No se encontraron Joy-Cons emparejados" -ForegroundColor Green
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$confirm = Read-Host "Deseas desemparejar TODOS estos dispositivos? (S/N)"

if ($confirm -ne "S" -and $confirm -ne "s") {
    Write-Host ""
    Write-Host "Operacion cancelada" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit
}

Write-Host ""
Write-Host "Desemparejando dispositivos..." -ForegroundColor Yellow
Write-Host ""

$removed = 0
$failed = 0

foreach ($deviceInfo in $joycons) {
    try {
        Write-Host "Desemparejando: $($deviceInfo.Name)..." -NoNewline
        
        # Obtener el objeto BluetoothDevice
        $btDeviceOp = [Windows.Devices.Bluetooth.BluetoothDevice]::FromIdAsync($deviceInfo.Id)
        $btDevice = Await $btDeviceOp ([Windows.Devices.Bluetooth.BluetoothDevice])
        
        if ($btDevice -ne $null) {
            # Desemparejar el dispositivo
            $unpairOp = $deviceInfo.Pairing.UnpairAsync()
            $unpairResult = Await $unpairOp ([Windows.Devices.Enumeration.DeviceUnpairingResult])
            
            $btDevice.Dispose()
            
            if ($unpairResult.Status -eq [Windows.Devices.Enumeration.DeviceUnpairingResultStatus]::Unpaired) {
                Write-Host " OK" -ForegroundColor Green
                $removed++
            } else {
                Write-Host " FALLO ($($unpairResult.Status))" -ForegroundColor Red
                $failed++
            }
        } else {
            Write-Host " ERROR (no se pudo acceder)" -ForegroundColor Red
            $failed++
        }
        
    } catch {
        Write-Host " ERROR" -ForegroundColor Red
        Write-Host "   $($_.Exception.Message)" -ForegroundColor Gray
        $failed++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Resumen:" -ForegroundColor Cyan
Write-Host "   Desemparejados: $removed" -ForegroundColor Green
if ($failed -gt 0) {
    Write-Host "   Fallidos: $failed" -ForegroundColor Red
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($removed -gt 0) {
    Write-Host "Los Joy-Cons han sido desemparejados del sistema" -ForegroundColor Green
    Write-Host ""
    Write-Host "Para volver a emparejarlos:" -ForegroundColor Yellow
    Write-Host "   1. Ve a Configuracion > Bluetooth y dispositivos" -ForegroundColor Gray
    Write-Host "   2. Manten presionado el boton SYNC en el Joy-Con" -ForegroundColor Gray
    Write-Host "   3. Selecciona Agregar dispositivo en Windows" -ForegroundColor Gray
    Write-Host ""
}

Write-Host ""
Read-Host "Presiona Enter para salir"
