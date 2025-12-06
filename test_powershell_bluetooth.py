"""
Test de Bluetooth usando PowerShell directo (sin winsdk)
Para Joy-Con, DualSense, Xbox
"""

import subprocess
import json
import time

print("=" * 60)
print("🎮 Bluetooth Scanner - PowerShell Edition")
print("=" * 60)

def run_powershell(script):
    """Ejecutar script PowerShell y retornar resultado"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=60,
            encoding='utf-8',
            errors='replace'
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", -1
    except Exception as e:
        return "", str(e), -1

def scan_bluetooth_devices():
    """Escanear dispositivos Bluetooth disponibles"""
    print("\n🔎 Buscando dispositivos Bluetooth...")
    print("   💡 Pon tu Joy-Con/DualSense en modo emparejamiento!")
    print("   ⏱️  Escaneando durante 15 segundos...\n")
    
    # Script PowerShell para escanear
    ps_script = """
    # Cargar APIs de Windows Runtime
    [Windows.Devices.Enumeration.DeviceInformation,Windows.Devices.Enumeration,ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Bluetooth.BluetoothDevice,Windows.Devices.Bluetooth,ContentType=WindowsRuntime] | Out-Null

    # Crear lista para almacenar dispositivos
    $foundDevices = @()
    $deviceIds = @{}

    # Selector para dispositivos Bluetooth
    $selector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelector()

    # Evento para dispositivos encontrados
    $watcher = [Windows.Devices.Enumeration.DeviceInformation]::CreateWatcher($selector)

    $added = {
        param($sender, $deviceInfo)
        
        $id = $deviceInfo.Id
        if (-not $deviceIds.ContainsKey($id)) {
            $deviceIds[$id] = $true
            
            $deviceObj = [PSCustomObject]@{
                Name = $deviceInfo.Name
                Id = $id
                IsPaired = $deviceInfo.Pairing.IsPaired
                CanPair = $deviceInfo.Pairing.CanPair
            }
            
            $script:foundDevices += $deviceObj
            
            Write-Host "[+] Encontrado: $($deviceInfo.Name) | Emparejado: $($deviceInfo.Pairing.IsPaired)"
        }
    }

    Register-ObjectEvent -InputObject $watcher -EventName Added -Action $added | Out-Null

    Write-Host "Iniciando escaneo..." -ForegroundColor Yellow
    $watcher.Start()

    # Escanear durante 15 segundos
    Start-Sleep -Seconds 15

    Write-Host "Deteniendo escaneo..." -ForegroundColor Yellow
    $watcher.Stop()

    # Limpiar eventos
    Get-EventSubscriber | Where-Object { $_.SourceObject -eq $watcher } | Unregister-Event
    Get-Job | Remove-Job -Force

    # Retornar dispositivos como JSON
    if ($foundDevices.Count -gt 0) {
        $foundDevices | ConvertTo-Json -Depth 3
    } else {
        Write-Host "No se encontraron dispositivos" -ForegroundColor Red
        "[]"
    }
    """
    
    stdout, stderr, code = run_powershell(ps_script)
    
    if stderr and "Cannot subscribe" in stderr:
        print("❌ Error: PowerShell no puede suscribirse a eventos WinRT")
        print("   Usando método alternativo...\n")
        return scan_bluetooth_alternative()
    
    if not stdout or stdout == "[]":
        print("⚠️  No se encontraron dispositivos\n")
        return []
    
    try:
        # Parsear JSON
        devices = json.loads(stdout)
        if not isinstance(devices, list):
            devices = [devices]
        
        print(f"\n✅ Encontrados {len(devices)} dispositivos!")
        print("=" * 60)
        
        display_devices(devices)
        return devices
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando respuesta: {e}")
        print(f"Salida: {stdout[:300]}")
        return []

def scan_bluetooth_alternative():
    """Método alternativo usando Get-PnpDevice"""
    print("🔧 Usando método alternativo (dispositivos del sistema)...\n")
    
    ps_script = """
    # Obtener dispositivos Bluetooth del sistema
    $devices = Get-PnpDevice -Class Bluetooth | Where-Object {
        $_.Status -ne 'OK' -or $_.FriendlyName -like '*Joy*' -or 
        $_.FriendlyName -like '*Nintendo*' -or $_.FriendlyName -like '*DualSense*' -or
        $_.FriendlyName -like '*Xbox*' -or $_.FriendlyName -like '*Controller*'
    } | Select-Object FriendlyName, Status, InstanceId

    $result = @()
    foreach ($dev in $devices) {
        $result += [PSCustomObject]@{
            Name = $dev.FriendlyName
            Id = $dev.InstanceId
            IsPaired = ($dev.Status -eq 'OK')
            CanPair = ($dev.Status -ne 'OK')
        }
    }

    if ($result.Count -gt 0) {
        $result | ConvertTo-Json -Depth 2
    } else {
        "[]"
    }
    """
    
    stdout, stderr, code = run_powershell(ps_script)
    
    if not stdout or stdout == "[]":
        print("⚠️  No se encontraron dispositivos en el sistema\n")
        return []
    
    try:
        devices = json.loads(stdout)
        if not isinstance(devices, list):
            devices = [devices]
        
        print(f"✅ Encontrados {len(devices)} dispositivos en el sistema")
        print("=" * 60)
        
        display_devices(devices)
        return devices
    except:
        return []

def display_devices(devices):
    """Mostrar dispositivos encontrados"""
    gamepad_keywords = ['joy', 'con', 'nintendo', 'switch', 'pro controller',
                      'dualsense', 'dualshock', 'playstation', 'ps4', 'ps5',
                      'xbox', 'controller', 'gamepad']
    
    gamepads = []
    others = []
    
    for device in devices:
        name = device.get('Name', 'Sin nombre')
        is_gamepad = any(kw in name.lower() for kw in gamepad_keywords)
        
        if is_gamepad:
            gamepads.append(device)
        else:
            others.append(device)
    
    if gamepads:
        print("\n🎮 GAMEPADS/CONTROLADORES:")
        for i, dev in enumerate(gamepads, 1):
            name = dev.get('Name', 'Sin nombre')
            is_paired = dev.get('IsPaired', False)
            can_pair = dev.get('CanPair', False)
            
            print(f"\n   #{i} 🕹️  {name}")
            print(f"      Estado: {'✅ Emparejado' if is_paired else '❌ No emparejado'}")
            if not is_paired and can_pair:
                print(f"      🔗 Puede emparejarse")
    
    if others:
        print(f"\n📱 OTROS DISPOSITIVOS ({len(others)}):")
        for i, dev in enumerate(others[:5], 1):
            name = dev.get('Name', 'Sin nombre')
            is_paired = dev.get('IsPaired', False)
            print(f"   #{i} {name} {'(emparejado)' if is_paired else ''}")

def main():
    print("\n🚀 Iniciando...\n")
    
    devices = scan_bluetooth_devices()
    
    print("\n" + "=" * 60)
    print("✅ Escaneo completado")
    print("=" * 60)
    
    if devices:
        print(f"\n💡 Encontrados {len(devices)} dispositivos")
        print("   Este método funciona con PowerShell + Python")
    else:
        print("\n⚠️  No se detectaron dispositivos")
        print("\n💡 Consejos:")
        print("   🕹️  Joy-Con: Botón sync 3+ segundos")
        print("   🎮 DualSense: PS + Share hasta parpadeo")
        print("   🎮 Xbox: Botón pair hasta parpadeo")
        print("   ✅ Bluetooth activo en Windows")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelado")
