"""
Investigación: LTK (Link Keys) - Problema de reconexión Joy-Con
"""

import subprocess
import winreg
import json

print("=" * 70)
print("🔑 Investigación: Bluetooth Link Keys (LTK)")
print("=" * 70)

print("""
📋 EL PROBLEMA DE LTK CON JOY-CON:

1. Al emparejar, Windows y Joy-Con intercambian Link Keys (LTK)
2. Estas claves se guardan para reconexiones futuras
3. PROBLEMA: Joy-Con puede rotar/cambiar su LTK
4. Windows sigue usando la LTK antigua
5. Reconexión falla porque las claves no coinciden

SOLUCIÓN: Limpiar LTKs guardadas y reemparejar

Las LTKs se guardan en el registro de Windows:
HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\BTHPORT\\Parameters\\Keys

""")

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

print("\n🔍 Buscando información del Joy-Con...\n")

# Obtener dirección Bluetooth del Joy-Con
stdout, _ = run_ps("""
Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Joy*'} | 
Select-Object FriendlyName, InstanceId | ConvertTo-Json
""")

if stdout:
    try:
        device = json.loads(stdout)
        instance_id = device.get('InstanceId', '')
        
        print(f"✅ Dispositivo: {device.get('FriendlyName', 'N/A')}")
        print(f"   Instance ID: {instance_id}\n")
        
        # Extraer dirección MAC del InstanceId
        # Formato: BTHENUM\DEV_XXXXXXXXXXXX\...
        if 'DEV_' in instance_id:
            mac_part = instance_id.split('DEV_')[1].split('\\')[0]
            # Convertir a formato MAC: XX:XX:XX:XX:XX:XX
            mac_addr = ':'.join([mac_part[i:i+2] for i in range(0, len(mac_part), 2)])
            print(f"📍 Dirección MAC: {mac_addr}")
            print(f"   (formato Windows): {mac_part}\n")
        else:
            mac_part = None
            print("⚠️  No se pudo extraer dirección MAC\n")
            
    except:
        mac_part = None
        print("⚠️  No se pudo parsear información del dispositivo\n")
else:
    mac_part = None
    print("❌ No se encontró Joy-Con\n")

print("=" * 70)
print("🔐 BUSCANDO LINK KEYS EN EL REGISTRO")
print("=" * 70)
print("\n⚠️  Nota: Requiere permisos de administrador para ver/modificar\n")

# Intentar leer registro (requiere admin)
print("📂 Ubicación de las claves:")
print("   HKLM\\SYSTEM\\CurrentControlSet\\Services\\BTHPORT\\Parameters\\Keys\n")

stdout, _ = run_ps("""
try {
    $path = "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\BTHPORT\\Parameters\\Keys"
    if (Test-Path $path) {
        $adapters = Get-ChildItem -Path $path
        foreach ($adapter in $adapters) {
            Write-Host "Adaptador: $($adapter.PSChildName)"
            $devices = Get-ChildItem -Path $adapter.PSPath
            foreach ($device in $devices) {
                Write-Host "  Device: $($device.PSChildName)"
            }
        }
        Write-Host "SUCCESS"
    } else {
        Write-Host "PATH_NOT_FOUND"
    }
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
}
""")

if "SUCCESS" in stdout:
    print("✅ Claves encontradas:")
    print(stdout.replace("SUCCESS", ""))
elif "denied" in stdout.lower() or "acceso" in stdout.lower():
    print("❌ Acceso denegado - Se requieren permisos de administrador")
elif "PATH_NOT_FOUND" in stdout:
    print("⚠️  Ruta no encontrada - puede que no haya claves guardadas")
else:
    print(f"⚠️  Resultado: {stdout[:200]}")

print("\n" + "=" * 70)
print("💡 SOLUCIONES PARA EL PROBLEMA DE LTK:")
print("=" * 70)
print("""
OPCIÓN 1: Limpiar y reemparejar (MÁS SIMPLE)
   1. Olvidar el Joy-Con en Windows:
      Settings → Bluetooth → Joy-Con → Remove device
   
   2. Reemparejar desde cero:
      - Joy-Con: Botón SYNC 3+ segundos
      - Windows: Add Bluetooth device
   
   3. Conectar inmediatamente después de emparejar
      ¡No dejes que se duerma!

OPCIÓN 2: Script automático de limpieza (REQUIERE ADMIN)
   - Eliminar claves del registro
   - Forzar reemparejamiento
   - Reconectar automáticamente

OPCIÓN 3: Usar BetterJoy/JoyShockMapper
   - Estos programas manejan las LTKs correctamente
   - Mantienen la conexión activa
   - Emulan XInput para compatibilidad

OPCIÓN 4: Servicio de reconexión persistente
   - Servicio en segundo plano con permisos
   - Monitorea desconexiones
   - Restablece conexión automáticamente
   - Maneja rotación de LTKs
""")

print("\n🎯 RECOMENDACIÓN:")
print("-" * 70)
print("""
Para el overlay, implementar:

1. Botón "Limpiar y Reemparejar":
   - Ejecuta script como admin
   - Elimina dispositivo del sistema
   - Abre asistente de emparejamiento
   - Guía al usuario paso a paso

2. O mejor: Integrar con BetterJoy
   - Detectar si está instalado
   - Usarlo como backend
   - Mostrar estado en overlay

3. Para reconexión rápida:
   - Ciclo Disable/Enable (requiere admin)
   - O botón que abre Settings → Bluetooth
   - Con instrucciones claras
""")

print("\n¿Quieres que implemente:")
print("   A) Script de limpieza de LTK (requiere admin)")
print("   B) Guía de reemparejamiento en el overlay")
print("   C) Integración con BetterJoy")
print("   D) Todo lo anterior")
print("=" * 70)
