"""
Test simplificado - solo listar dispositivos Bluetooth del sistema
"""

import subprocess
import json

print("=" * 60)
print("🎮 Test Simple - Dispositivos Bluetooth")
print("=" * 60)

def run_ps(cmd):
    result = subprocess.run(
        ["powershell", "-Command", cmd],
        capture_output=True,
        text=True,
        timeout=10
    )
    return result.stdout.strip()

print("\n📱 Dispositivos Bluetooth en este PC:\n")

# Método 1: Get-PnpDevice
ps_cmd = """
Get-PnpDevice -Class Bluetooth | 
Where-Object {$_.Status -eq 'OK' -and $_.FriendlyName -like '*controller*'} |
Select-Object FriendlyName, Status |
ConvertTo-Json
"""

output = run_ps(ps_cmd)
try:
    devices = json.loads(output) if output else []
    if not isinstance(devices, list):
        devices = [devices]
    
    for dev in devices:
        print(f"✅ {dev['FriendlyName']}")
except:
    print("No se encontraron controladores emparejados")

print("\n" + "=" * 60)
print("💡 Para escanear dispositivos NUEVOS:")
print("   1. Windows no permite escaneo en segundo plano fácilmente")
print("   2. La mejor opción es usar la API del sistema")
print("   3. O implementar con btpair.exe (herramienta nativa)")
print("=" * 60)

# Test: ¿Existe Joy-Con en el sistema?
print("\n🔍 Buscando Joy-Con...")
ps_joy = """
Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Joy*'} | 
Select-Object FriendlyName, Status | Format-List
"""
output = run_ps(ps_joy)
if output:
    print(output)
else:
    print("❌ No hay Joy-Con emparejado en el sistema")
    print("   Primero debes emparejarlo manualmente una vez")
    print("   Luego podremos detectarlo y reconectarlo automáticamente")

print("\n" + "=" * 60)
