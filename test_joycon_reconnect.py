"""
Test: Forzar reconexión del Joy-Con usando Windows API
"""

import subprocess
import time

print("=" * 70)
print("🔌 Test de Reconexión Forzada - Joy-Con")
print("=" * 70)

def run_ps(cmd):
    result = subprocess.run(
        ["powershell", "-Command", cmd],
        capture_output=True,
        text=True,
        timeout=30,
        encoding='utf-8',
        errors='replace'
    )
    return result.stdout.strip(), result.stderr.strip()

print("\n1️⃣ Obteniendo información del Joy-Con...")
stdout, _ = run_ps("""
Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Joy*'} | 
Select-Object FriendlyName, Status, InstanceId, Class | Format-List
""")
print(stdout)

print("\n2️⃣ Intentando habilitar el dispositivo...")
# Obtener InstanceId
stdout, _ = run_ps("""
$joycon = Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Joy*'} | Select-Object -First 1
if ($joycon) {
    Write-Output $joycon.InstanceId
} else {
    Write-Output "NO_JOYCON"
}
""")

if stdout and stdout != "NO_JOYCON":
    instance_id = stdout.strip()
    print(f"✅ Joy-Con encontrado: {instance_id[:50]}...")
    
    # Intentar disable/enable (requiere admin)
    print("\n3️⃣ Intentando ciclo Disable/Enable...")
    stdout, stderr = run_ps(f"""
    try {{
        Disable-PnpDevice -InstanceId '{instance_id}' -Confirm:$false -ErrorAction Stop
        Start-Sleep -Seconds 2
        Enable-PnpDevice -InstanceId '{instance_id}' -Confirm:$false -ErrorAction Stop
        Write-Output "SUCCESS"
    }} catch {{
        Write-Output "ERROR: $($_.Exception.Message)"
    }}
    """)
    
    if "SUCCESS" in stdout:
        print("✅ Ciclo completado exitosamente")
    else:
        print(f"⚠️ Resultado: {stdout}")
        if "Access" in stderr or "privilegio" in stderr:
            print("\n⚠️ Se requieren permisos de administrador")
    
    # Verificar estado después
    print("\n4️⃣ Verificando estado después del ciclo...")
    time.sleep(2)
    stdout, _ = run_ps("""
    Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Joy*'} | 
    Select-Object FriendlyName, Status
    """)
    print(stdout)
else:
    print("❌ No se encontró Joy-Con")

print("\n" + "=" * 70)
print("🔬 MÉTODO ALTERNATIVO: Usar API Bluetooth directa")
print("=" * 70)

print("\n5️⃣ Intentando conectar via Bluetooth API...")
stdout, stderr = run_ps("""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Devices.Enumeration.DeviceInformation,Windows.Devices.Enumeration,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Bluetooth.BluetoothDevice,Windows.Devices.Bluetooth,ContentType=WindowsRuntime] | Out-Null

# Buscar Joy-Con en dispositivos Bluetooth
$selector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelector()
$devices = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($selector).GetAwaiter().GetResult()

$joycon = $devices | Where-Object {$_.Name -like '*Joy*'}
if ($joycon) {
    Write-Output "Encontrado: $($joycon.Name)"
    Write-Output "ID: $($joycon.Id)"
    Write-Output "Emparejado: $($joycon.Pairing.IsPaired)"
    
    # Intentar obtener dispositivo Bluetooth
    try {
        $btDevice = [Windows.Devices.Bluetooth.BluetoothDevice]::FromIdAsync($joycon.Id).GetAwaiter().GetResult()
        if ($btDevice) {
            Write-Output "Estado: $($btDevice.ConnectionStatus)"
            Write-Output "BluetoothAddress: $($btDevice.BluetoothAddress)"
            
            # Intentar obtener servicios GATT
            $services = $btDevice.GetGattServicesAsync().GetAwaiter().GetResult()
            Write-Output "Servicios GATT: $($services.Services.Count)"
        }
    } catch {
        Write-Output "Error obteniendo dispositivo: $($_.Exception.Message)"
    }
} else {
    Write-Output "No se encontró Joy-Con en dispositivos Bluetooth"
}
""")

print(stdout if stdout else "❌ Error")
if stderr:
    print(f"Error: {stderr[:200]}")

print("\n" + "=" * 70)
print("💡 CONCLUSIONES:")
print("=" * 70)
print("""
Para reconectar el Joy-Con tenemos estas opciones:

1. DISABLE/ENABLE (Requiere Admin):
   - Funciona pero necesita permisos elevados
   - Puede usarse en el overlay si se ejecuta como admin

2. API BLUETOOTH:
   - Puede leer estado del dispositivo
   - NO puede forzar reconexión (limitación de Windows)

3. SOLUCIÓN RECOMENDADA:
   - Usar hidapi para comunicación directa
   - O integrar con BetterJoy/JoyShockMapper
   - O crear servicio en segundo plano con permisos
""")

print("\n🎯 ¿Siguiente paso?")
print("   A) Instalar hidapi y probar comunicación directa")
print("   B) Ejecutar overlay como administrador para disable/enable")
print("   C) Buscar/instalar BetterJoy")
print("=" * 70)
