"""
Test de Bluetooth usando comandos nativos de Windows
Para Joy-Con, DualSense, Xbox
"""

import subprocess
import time
import re

print("=" * 60)
print("🎮 Detector de Dispositivos Bluetooth")
print("=" * 60)

def run_powershell(command):
    """Ejecutar comando PowerShell"""
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            errors='ignore'
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), -1

def scan_bluetooth_devices():
    """Escanear dispositivos Bluetooth disponibles"""
    print("\n🔎 Escaneando dispositivos Bluetooth...")
    print("   💡 Pon tu Joy-Con en modo emparejamiento (LED parpadeando)")
    print("   ⏱️  Iniciando escaneo...\n")
    
    # Comando 1: Iniciar descubrimiento
    command_start = """
    [void][Windows.Devices.Bluetooth.BluetoothAdapter, Windows.Devices.Bluetooth, ContentType=WindowsRuntime]
    $adapter = [Windows.Devices.Bluetooth.BluetoothAdapter]::GetDefaultAsync().GetAwaiter().GetResult()
    if ($adapter) {
        Write-Host "Bluetooth activo: $($adapter.IsEnabled)"
        Write-Host "Dirección: $($adapter.BluetoothAddress)"
    }
    """
    
    stdout, stderr, code = run_powershell(command_start)
    if stdout:
        print(f"📡 {stdout}\n")
    
    # Comando 2: Listar dispositivos del sistema
    command_list = """
    Get-PnpDevice -Class Bluetooth | Where-Object {
        $_.Status -eq 'Unknown' -or 
        $_.Status -eq 'Error' -or
        $_.InstanceId -like '*BTHENUM*'
    } | Select-Object FriendlyName, Status, InstanceId | Format-List
    """
    
    stdout, stderr, code = run_powershell(command_list)
    
    if stdout:
        print("📱 Dispositivos Bluetooth del sistema:")
        print("=" * 60)
        print(stdout)
        print()
    
    # Comando 3: BTH Pairing Tool (método alternativo)
    print("\n🔧 Intentando método alternativo con btpair...")
    command_btpair = """
    # Intentar usar btpair si está disponible
    $btpair = Get-Command btpair.exe -ErrorAction SilentlyContinue
    if ($btpair) {
        btpair /list
    } else {
        Write-Host "btpair no disponible"
    }
    """
    
    stdout, stderr, code = run_powershell(command_btpair)
    if stdout and "no disponible" not in stdout:
        print(stdout)
    
    # Comando 4: Usar WMI
    print("\n🔍 Buscando con WMI...")
    command_wmi = """
    Get-WmiObject -Namespace root\\cimv2 -Class Win32_PnPEntity | 
    Where-Object {$_.Name -like '*Bluetooth*' -or $_.Name -like '*Joy*' -or $_.Name -like '*Nintendo*'} |
    Select-Object Name, Status, DeviceID |
    Format-Table -AutoSize
    """
    
    stdout, stderr, code = run_powershell(command_wmi)
    if stdout:
        print("🎮 Dispositivos relacionados:")
        print(stdout)
        print()

def try_manual_pairing():
    """Intentar emparejamiento manual abriendo configuración"""
    print("\n" + "=" * 60)
    print("💡 MÉTODO ALTERNATIVO")
    print("=" * 60)
    print("\nSi no detecta el Joy-Con automáticamente, vamos a usar")
    print("PowerShell para emparejar directamente:\n")
    
    print("📝 Pasos manuales:")
    print("   1. Mantén presionado el botón SYNC del Joy-Con")
    print("   2. Espera que el LED parpadee rápidamente")
    print("   3. Ejecuta: bluetoothctl (si tienes WSL)")
    print("   O usa: Settings -> Bluetooth -> Add device\n")
    
    # Abrir configuración de Bluetooth
    print("🔧 Abriendo configuración de Bluetooth...")
    command = "Start-Process ms-settings:bluetooth"
    run_powershell(command)
    
    print("✅ Configuración abierta")
    print("   Busca 'Joy-Con (L)' o 'Joy-Con (R)' en la lista")

def main():
    print("\n🚀 Iniciando detección...\n")
    
    # Escanear
    scan_bluetooth_devices()
    
    # Método alternativo
    print("\n⚠️  Si no aparece tu Joy-Con arriba...")
    response = input("\n¿Abrir configuración de Bluetooth de Windows? (s/n): ")
    
    if response.lower() == 's':
        try_manual_pairing()
    
    print("\n" + "=" * 60)
    print("✅ Test completado")
    print("=" * 60)
    print("\n💡 Nota: Windows puede requerir permisos de administrador")
    print("   para descubrir dispositivos nuevos automáticamente.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelado")
