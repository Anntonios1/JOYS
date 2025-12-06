"""
Test usando BluetoothDevice.get_device_selector() para Bluetooth Classic
"""

import asyncio
from winsdk.windows.devices.bluetooth import BluetoothDevice
from winsdk.windows.devices.enumeration import DeviceInformation

print("=" * 60)
print("🎮 Test Bluetooth Classic con get_device_selector()")
print("=" * 60)

async def scan_classic_rfcomm():
    """Escanear dispositivos Bluetooth Classic"""
    print("\n🔎 Obteniendo selector de dispositivos...")
    selector = BluetoothDevice.get_device_selector()
    print(f"📋 Selector: {selector[:100]}...\n")

    print("🔍 Buscando dispositivos...")
    devices = await DeviceInformation.find_all_async(selector)
    
    print(f"✅ Encontrados {len(devices)} dispositivos totales\n")

    valid = []
    for i, d in enumerate(devices, 1):
        print(f"   {i}. Procesando: {d.name if d.name else 'Sin nombre'}")
        try:
            dev = await BluetoothDevice.from_id_async(d.id)
            if dev and dev.class_of_device:   # Solo clásico
                print(f"      ✅ Bluetooth Classic detectado!")
                print(f"         Class: {dev.class_of_device.raw_value}")
                print(f"         Emparejado: {d.pairing.is_paired}")
                valid.append(d)
            elif dev:
                print(f"      ⚠️  BLE (sin class_of_device)")
            else:
                print(f"      ⚠️  No se pudo obtener info")
        except Exception as e:
            print(f"      ❌ Error: {e}")

    return valid

async def main():
    print("\n🚀 Iniciando escaneo...\n")
    
    try:
        devices = await scan_classic_rfcomm()
        
        print("\n" + "=" * 60)
        print(f"📊 RESUMEN")
        print("=" * 60)
        print(f"✅ Dispositivos Bluetooth Classic: {len(devices)}\n")
        
        if devices:
            gamepad_keywords = ['joy', 'con', 'nintendo', 'switch', 'pro controller',
                              'dualsense', 'dualshock', 'playstation', 'ps4', 'ps5',
                              'xbox', 'controller', 'gamepad']
            
            gamepads = [d for d in devices if any(kw in (d.name or '').lower() for kw in gamepad_keywords)]
            
            if gamepads:
                print("🎮 GAMEPADS ENCONTRADOS:")
                for g in gamepads:
                    print(f"   • {g.name}")
                    print(f"     Emparejado: {'✅' if g.pairing.is_paired else '❌'}")
            else:
                print("📱 Dispositivos encontrados (no gamepads):")
                for d in devices[:5]:
                    print(f"   • {d.name if d.name else 'Sin nombre'}")
        else:
            print("⚠️  No se encontraron dispositivos Bluetooth Classic")
            print("\n💡 Nota: Este método solo muestra dispositivos YA conocidos")
            print("   por Windows (emparejados o previamente vistos)")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ Test completado")
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelado")
