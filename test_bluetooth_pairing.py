"""
Test de emparejamiento Bluetooth usando PowerShell
Para Joy-Con, DualSense, Xbox (Bluetooth Classic/HID)
"""

import subprocess
import json
import time

print("=" * 60)
print("🎮 Test de Bluetooth Classic (Joy-Con, DualSense, Xbox)")
print("=" * 60)

def run_powershell(command):
    """Ejecutar comando PowerShell y retornar resultado"""
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), -1

def scan_unpaired_devices():
    """Escanear dispositivos Bluetooth no emparejados"""
    print("\n🔎 Buscando dispositivos Bluetooth no emparejados...")
    print("   💡 Pon tu Joy-Con/DualSense en modo emparejamiento!")
    print("   ⏱️  Escaneando durante 15 segundos...\n")
    
    # Comando para buscar dispositivos no emparejados
    command = """
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType=WindowsRuntime]
    $null = [Windows.Devices.Bluetooth.BluetoothDevice, Windows.Devices.Bluetooth, ContentType=WindowsRuntime]

    # Selector para dispositivos Bluetooth no emparejados
    $selector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelectorFromPairingState($false)
    
    # Crear watcher
    $watcher = [Windows.Devices.Enumeration.DeviceInformation]::CreateWatcher($selector)
    
    $devices = @{}
    $deviceAdded = {
        param($sender, $deviceInfo)
        $devices[$deviceInfo.Id] = @{
            Id = $deviceInfo.Id
            Name = $deviceInfo.Name
            CanPair = $deviceInfo.Pairing.CanPair
        }
    }
    
    $null = Register-ObjectEvent -InputObject $watcher -EventName Added -Action $deviceAdded
    $watcher.Start()
    
    Start-Sleep -Seconds 15
    
    $watcher.Stop()
    Get-EventSubscriber | Unregister-Event
    Get-Job | Remove-Job -Force
    
    # Convertir a JSON
    $devices.Values | ConvertTo-Json
    """
    
    stdout, stderr, code = run_powershell(command)
    
    if code != 0 or stderr:
        print(f"❌ Error en PowerShell: {stderr}")
        return []
    
    if not stdout or stdout == "null":
        print("⚠️  No se encontraron dispositivos")
        return []
    
    try:
        # Parsear JSON
        devices = json.loads(stdout)
        if not isinstance(devices, list):
            devices = [devices]
        
        print(f"✅ Encontrados {len(devices)} dispositivos!\n")
        print("=" * 60)
        
        gamepad_keywords = ['joy', 'con', 'nintendo', 'switch', 'pro controller',
                          'dualsense', 'dualshock', 'playstation', 'ps4', 'ps5',
                          'xbox', 'controller', 'gamepad']
        
        gamepads = []
        others = []
        
        for i, device in enumerate(devices, 1):
            name = device.get('Name', 'Sin nombre')
            can_pair = device.get('CanPair', False)
            device_id = device.get('Id', '')
            
            is_gamepad = any(kw in name.lower() for kw in gamepad_keywords)
            
            if is_gamepad:
                gamepads.append(device)
                print(f"🎮 #{i} {name}")
            else:
                others.append(device)
                print(f"📱 #{i} {name}")
            
            print(f"   ID: {device_id[:50]}...")
            print(f"   Emparejar: {'✅ Sí' if can_pair else '❌ No'}")
            print()
        
        if gamepads:
            print(f"\n🕹️  GAMEPADS DETECTADOS: {len(gamepads)}")
            return gamepads
        else:
            print("\n⚠️  No se detectaron gamepads")
            print("\n💡 Asegúrate de:")
            print("   • Joy-Con: Mantener botón sync 3+ segundos (LED parpadeando)")
            print("   • DualSense: Mantener PS + Share hasta parpadeo azul")
            print("   • Xbox: Mantener botón pair hasta parpadeo")
            print("   • Bluetooth activado en Windows")
            return []
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando JSON: {e}")
        print(f"Salida: {stdout[:200]}")
        return []

def pair_device(device_id, device_name):
    """Emparejar un dispositivo"""
    print(f"\n🔗 Intentando emparejar: {device_name}")
    print(f"   ID: {device_id[:50]}...")
    
    command = f"""
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType=WindowsRuntime]
    
    $deviceId = "{device_id}"
    $device = [Windows.Devices.Enumeration.DeviceInformation]::CreateFromIdAsync($deviceId).GetAwaiter().GetResult()
    
    if ($device) {{
        $pairingResult = $device.Pairing.PairAsync().GetAwaiter().GetResult()
        
        @{{
            Status = $pairingResult.Status.ToString()
            ProtectionLevel = $pairingResult.ProtectionLevelUsed.ToString()
        }} | ConvertTo-Json
    }} else {{
        "null"
    }}
    """
    
    stdout, stderr, code = run_powershell(command)
    
    if code != 0 or stderr:
        print(f"❌ Error: {stderr}")
        return False
    
    try:
        result = json.loads(stdout)
        status = result.get('Status', 'Unknown')
        
        if status == 'Paired':
            print(f"✅ ¡Emparejado exitosamente!")
            return True
        else:
            print(f"⚠️  Estado: {status}")
            return False
            
    except:
        print(f"❌ No se pudo emparejar")
        return False

def main():
    print("\n🚀 Iniciando...\n")
    
    # Escanear
    devices = scan_unpaired_devices()
    
    # Si hay dispositivos, ofrecer emparejar
    if devices:
        print("\n" + "=" * 60)
        print("💡 Dispositivos listos para emparejar")
        print("=" * 60)
        
        # Auto-emparejar primer gamepad
        first = devices[0]
        print(f"\n¿Emparejar '{first['Name']}'?")
        print("Ejecutando en 3 segundos...")
        time.sleep(3)
        
        pair_device(first['Id'], first['Name'])
    
    print("\n" + "=" * 60)
    print("✅ Test completado")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelado")
