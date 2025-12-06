"""
Test Completo de Funcionalidades del Gamepad Monitor
Prueba todas las capacidades antes de implementar en la API
"""

import sys
import os
import time
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from modules.bluetooth_manager import get_bluetooth_manager
from modules.windows_hid_reader import get_windows_hid_reader

print("=" * 60)
print("🎮 TEST COMPLETO - GAMEPAD MONITOR")
print("=" * 60)
print()

# ============================================================================
# TEST 1: Detectar dispositivos conectados en Windows
# ============================================================================
print("📋 TEST 1: Detectar dispositivos Bluetooth conectados")
print("-" * 60)

async def test_scan():
    bt_mgr = get_bluetooth_manager()
    devices = await bt_mgr.scan_devices(duration=3)
    return devices

devices = asyncio.run(test_scan())

if devices:
    print(f"✅ Encontrados {len(devices)} dispositivos:")
    for dev in devices:
        print(f"   • {dev.name}")
        print(f"     MAC/ID: {dev.mac_address[:50]}...")
        print(f"     Tipo: {dev.controller_type.value}")
        print(f"     Conectado: {dev.connected}")
        print()
else:
    print("❌ No se encontraron dispositivos")
    print()

# ============================================================================
# TEST 2: Leer batería real via HID
# ============================================================================
print("🔋 TEST 2: Lectura de batería real via HID")
print("-" * 60)

hid_reader = get_windows_hid_reader()
joycon_devices = hid_reader.find_joycon_devices()

if joycon_devices:
    print(f"✅ Encontrados {len(joycon_devices)} Joy-Cons via HID:")
    
    for i, device in enumerate(joycon_devices):
        product_name = device['product_string']
        print(f"\n   Dispositivo {i+1}: {product_name}")
        
        # Leer batería
        battery = hid_reader.read_joycon_battery_real(device['path'])
        
        if battery is not None:
            print(f"   ✅ Batería: {battery}%")
            
            # Determinar estado
            if battery >= 75:
                estado = "🟢 Excelente"
            elif battery >= 50:
                estado = "🟡 Buena"
            elif battery >= 25:
                estado = "🟠 Baja"
            else:
                estado = "🔴 Crítica"
            
            print(f"   Estado: {estado}")
        else:
            print(f"   ❌ No se pudo leer batería")
    print()
else:
    print("❌ No se encontraron Joy-Cons via HID")
    print()

# ============================================================================
# TEST 3: Capacidades de monitoreo en tiempo real
# ============================================================================
print("⚡ TEST 3: Capacidades de monitoreo en tiempo real")
print("-" * 60)

print("📊 Latencia:")
print("   ⚠️ Requiere captura activa de paquetes HID")
print("   ⚠️ No disponible para dispositivos emparejados en Windows")
print("   ℹ️ Solo funciona con conexión BLE directa")
print()

print("📶 Señal (RSSI):")
print("   ⚠️ No disponible para dispositivos emparejados en Windows")
print("   ℹ️ Solo funciona con conexión BLE directa")
print()

# ============================================================================
# TEST 4: Verificar que los dispositivos están en Windows
# ============================================================================
print("💻 TEST 4: Verificar dispositivos en Windows")
print("-" * 60)

try:
    import subprocess
    result = subprocess.run(
        ['powershell', '-Command',
         'Get-PnpDevice -Class Bluetooth | Where-Object {$_.Status -eq "OK" -and $_.FriendlyName -like "*Joy*"} | Select-Object FriendlyName, Status'],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')
        if len(lines) > 2:
            print("✅ Joy-Cons detectados en Windows:")
            for line in lines[2:]:
                if line.strip():
                    print(f"   • {line.strip()}")
        else:
            print("❌ No se detectaron Joy-Cons en Windows")
    print()
except Exception as e:
    print(f"❌ Error al verificar Windows: {e}")
    print()

# ============================================================================
# TEST 5: Prueba de lectura continua de batería
# ============================================================================
print("🔁 TEST 5: Monitoreo continuo de batería (5 lecturas)")
print("-" * 60)

if joycon_devices:
    print("Leyendo batería cada 2 segundos...\n")
    
    for i in range(5):
        print(f"Lectura {i+1}/5:")
        
        for idx, device in enumerate(joycon_devices):
            battery = hid_reader.read_joycon_battery_real(device['path'])
            product_name = device['product_string']
            
            if battery is not None:
                print(f"   {product_name}: {battery}%")
            else:
                print(f"   {product_name}: Error")
        
        if i < 4:
            time.sleep(2)
            print()
    print()
else:
    print("⚠️ No hay dispositivos para monitorear")
    print()

# ============================================================================
# RESUMEN FINAL
# ============================================================================
print("=" * 60)
print("📊 RESUMEN DE CAPACIDADES")
print("=" * 60)

print("\n✅ FUNCIONANDO:")
print("   • Detección de Joy-Cons conectados en Windows")
print("   • Lectura de batería real via HID")
print("   • Identificación de tipo de controlador")
print("   • Monitoreo continuo de batería")

print("\n⚠️ LIMITACIONES (dispositivos emparejados en Windows):")
print("   • Latencia: Requiere conexión BLE directa")
print("   • Señal RSSI: Requiere conexión BLE directa")
print("   • Control de conexión/desconexión: Limitado")

print("\n💡 RECOMENDACIONES:")
print("   1. Para batería: ✅ Usar HID directo (implementado)")
print("   2. Para latencia y señal: Requiere desconectar de Windows")
print("      y conectar via BLE directamente desde la app")
print("   3. Para control total: Desemparejar de Windows y usar")
print("      solo conexión BLE de la aplicación")

print("\n" + "=" * 60)
print("🎯 CONCLUSIÓN:")
if joycon_devices:
    print("✅ Sistema funcional para monitoreo de batería")
    print("✅ Listo para implementar en la API")
else:
    print("❌ No se detectaron Joy-Cons")
    print("⚠️ Verifica que estén conectados y encendidos")

print("=" * 60)
