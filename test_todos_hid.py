"""
Test - Detectar TODOS los dispositivos HID
Muestra batería, latencia y frecuencia de todos los dispositivos
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from modules.windows_hid_reader import get_windows_hid_reader

print("=" * 70)
print("🔍 DETECTANDO TODOS LOS DISPOSITIVOS HID")
print("=" * 70)
print()

hid_reader = get_windows_hid_reader()

# Encontrar todos los dispositivos
print("📋 Buscando dispositivos HID...")
all_devices = hid_reader.find_all_hid_devices()

print(f"✅ Encontrados {len(all_devices)} dispositivos HID\n")
print("=" * 70)

# Filtrar dispositivos relevantes (gamepads principalmente)
gamepad_keywords = ['joy', 'controller', 'gamepad', 'xbox', 'playstation', 
                    'nintendo', 'wireless', 'pro controller', 'dualshock', 'dualsense']

interesting_devices = []
for device in all_devices:
    product_name = device['product_string'].lower()
    if any(keyword in product_name for keyword in gamepad_keywords):
        interesting_devices.append(device)

if not interesting_devices:
    print("⚠️ No se encontraron gamepads, mostrando TODOS los dispositivos HID:\n")
    interesting_devices = all_devices[:20]  # Limitar a 20 para no saturar

print(f"\n🎮 DISPOSITIVOS DETECTADOS ({len(interesting_devices)}):")
print("=" * 70)

for idx, device in enumerate(interesting_devices):
    print(f"\n[{idx+1}] {device['product_string']}")
    print(f"    Fabricante: {device['manufacturer_string']}")
    print(f"    VID:PID: {device['vendor_id']:04X}:{device['product_id']:04X}")
    print(f"    Interface: {device['interface_number']}")
    
    # Intentar leer datos
    print(f"    📊 Leyendo datos reales...")
    
    try:
        # Leer batería
        data = hid_reader.get_device_data(
            device['path'], 
            vendor_id=device['vendor_id'],
            product_id=device['product_id'],
            measure_latency=False
        )
        
        if data.battery_percentage is not None:
            battery_bar = "█" * (data.battery_percentage // 10)
            print(f"    🔋 Batería: {data.battery_percentage}% [{battery_bar}]")
        else:
            print(f"    🔋 Batería: No disponible")
        
        # Medir latencia (solo para primeros 5 dispositivos para no demorar)
        if idx < 5:
            print(f"    ⚡ Midiendo latencia (2 segundos)...")
            latency, polling = hid_reader.measure_input_latency(device['path'], duration=2.0)
            
            if latency is not None and polling is not None:
                print(f"    ⚡ Latencia: {latency:.2f} ms")
                print(f"    📊 Frecuencia: {polling:.1f} Hz")
                
                # Clasificación
                if latency < 10:
                    quality = "🟢 EXCELENTE"
                elif latency < 20:
                    quality = "🟡 BUENA"
                elif latency < 50:
                    quality = "🟠 ACEPTABLE"
                else:
                    quality = "🔴 ALTA"
                
                print(f"    📈 Calidad: {quality}")
            else:
                print(f"    ⚡ Latencia: No se pudo medir (dispositivo inactivo o bloqueado)")
        else:
            print(f"    ⚡ Latencia: Omitida (para agilizar test)")
    
    except Exception as e:
        print(f"    ❌ Error: {e}")
    
    print("-" * 70)

print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)
print(f"\n✅ Total dispositivos HID: {len(all_devices)}")
print(f"🎮 Gamepads detectados: {len(interesting_devices)}")
print(f"\n💡 El sistema puede monitorear:")
print(f"   • Batería (donde esté disponible)")
print(f"   • Latencia de respuesta HID")
print(f"   • Frecuencia de polling")
print(f"   • Estado de conexión")
print(f"\n✅ Listo para implementar en la API")
print("=" * 70)
