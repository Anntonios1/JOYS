"""
Test de escaneo Bluetooth usando bleak (librería profesional)
pip install bleak
"""

import asyncio
import sys

print("=" * 60)
print("🔍 Test de Escaneo Bluetooth con bleak")
print("=" * 60)

# Verificar que bleak esté instalado
try:
    from bleak import BleakScanner
    print("✅ bleak instalado correctamente")
except ImportError:
    print("❌ bleak no está instalado")
    print("   Instala con: pip install bleak")
    sys.exit(1)

async def scan_bluetooth_devices():
    """Escanear dispositivos Bluetooth"""
    try:
        print("\n🔎 Escaneando dispositivos Bluetooth durante 10 segundos...")
        print("   💡 Pon tus dispositivos en modo emparejamiento!")
        
        # Escanear durante 10 segundos
        devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
        
        print(f"\n✅ Escaneo completado!")
        print(f"📊 Dispositivos encontrados: {len(devices)}")
        
        if devices:
            print("\n" + "=" * 60)
            print("📱 DISPOSITIVOS DETECTADOS:")
            print("=" * 60)
            
            gamepad_keywords = ['joy', 'con', 'nintendo', 'switch', 'pro controller',
                              'dualsense', 'dualshock', 'playstation', 'ps4', 'ps5',
                              'xbox', 'controller', 'gamepad']
            
            gamepads = []
            other = []
            
            for address, (device, adv_data) in devices.items():
                name = device.name if device.name else "Sin nombre"
                rssi = adv_data.rssi if adv_data else "N/A"
                
                # Clasificar
                is_gamepad = any(kw in name.lower() for kw in gamepad_keywords)
                
                device_info = {
                    'name': name,
                    'address': address,
                    'rssi': rssi,
                    'device': device
                }
                
                if is_gamepad:
                    gamepads.append(device_info)
                else:
                    other.append(device_info)
            
            # Mostrar gamepads primero
            if gamepads:
                print("\n🎮 GAMEPADS/CONTROLADORES:")
                for i, dev in enumerate(gamepads, 1):
                    print(f"\n   #{i} 🕹️  {dev['name']}")
                    print(f"      Dirección: {dev['address']}")
                    print(f"      RSSI: {dev['rssi']} dBm")
            
            # Mostrar otros dispositivos
            if other:
                print(f"\n📱 OTROS DISPOSITIVOS ({len(other)}):")
                for i, dev in enumerate(other[:5], 1):  # Máximo 5
                    print(f"   #{i} {dev['name']} | {dev['rssi']} dBm")
                
                if len(other) > 5:
                    print(f"   ... y {len(other) - 5} más")
        else:
            print("\n⚠️ No se encontraron dispositivos")
            print("\n💡 Consejos:")
            print("   🕹️  Joy-Con: Botón sincronización 3+ segundos")
            print("   🎮 DualSense: PS + Share hasta parpadeo")
            print("   🎮 Xbox: Botón sincronización hasta parpadeo")
            print("   ✅ Bluetooth activo en Windows")
        
        return devices
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    print("\n🚀 Iniciando escaneo...\n")
    devices = await scan_bluetooth_devices()
    
    print("\n" + "=" * 60)
    print("✅ Prueba completada")
    print("=" * 60)
    
    if devices:
        print(f"\n💡 bleak funciona correctamente!")
        print(f"   Encontró {len(devices)} dispositivos")
        print(f"\n   Podemos implementar esto en el overlay para:")
        print(f"   • Escaneo real de dispositivos")
        print(f"   • Emparejamiento automático")
        print(f"   • Detección de gamepads")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelado")
