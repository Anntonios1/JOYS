"""
Script de prueba para escaneo Bluetooth Classic (HID) usando winsdk
Los gamepads usan Bluetooth Classic, no BLE
Ejecutar: python test_bluetooth_classic.py
"""

import asyncio
import sys

print("=" * 60)
print("🔍 Test de Escaneo Bluetooth Classic (HID)")
print("=" * 60)

# Verificar que winsdk esté instalado
try:
    from winsdk.windows.devices.bluetooth import BluetoothDevice
    from winsdk.windows.devices.enumeration import (
        DeviceInformation, 
        DevicePairingResultStatus,
        DeviceInformationKind
    )
    print("✅ winsdk instalado correctamente")
except ImportError as e:
    print(f"❌ Error: winsdk no está instalado")
    print(f"   Instala con: pip install winsdk")
    print(f"   Detalles: {e}")
    sys.exit(1)

async def scan_bluetooth_classic():
    """Escanear dispositivos Bluetooth Classic (HID) no emparejados"""
    try:
        print("\n🔎 Escaneando dispositivos Bluetooth Classic (gamepads)...")
        
        discovered_devices = []
        
        # Selector para dispositivos Bluetooth Classic no emparejados
        selector = BluetoothDevice.get_device_selector_from_pairing_state(False)
        print(f"📋 Selector: {selector[:80]}...")
        
        # Usar find_all_async para obtener dispositivos
        print("\n⏳ Buscando dispositivos (esto puede tardar 10-15 segundos)...")
        print("   💡 Pon tus dispositivos en modo emparejamiento ahora!")
        
        # find_all_async busca dispositivos que coinciden con el selector
        device_collection = await DeviceInformation.find_all_async(selector)
        
        print(f"\n✅ Búsqueda completada!")
        print(f"📊 Dispositivos encontrados: {len(device_collection) if device_collection else 0}")
        
        if device_collection and len(device_collection) > 0:
            for device_info in device_collection:
                name = device_info.name if device_info.name else "Sin nombre"
                print(f"   ✨ {name}")
                discovered_devices.append(device_info)
        
        if discovered_devices:
            print("\n" + "=" * 60)
            print("📱 DISPOSITIVOS DETECTADOS:")
            print("=" * 60)
            
            for i, device_info in enumerate(discovered_devices, 1):
                print(f"\n🎮 Dispositivo #{i}:")
                print(f"   Nombre: {device_info.name if device_info.name else 'Sin nombre'}")
                print(f"   ID: {device_info.id}")
                print(f"   Habilitado: {device_info.is_enabled}")
                
                if hasattr(device_info, 'pairing') and device_info.pairing:
                    print(f"   Emparejado: {device_info.pairing.is_paired}")
                    print(f"   Puede emparejar: {device_info.pairing.can_pair}")
        else:
            print("\n⚠️ No se encontraron dispositivos Bluetooth Classic")
            print("\n💡 Consejos para modo emparejamiento:")
            print("   🕹️  Joy-Con: Mantén botón sincronización 3+ segundos (LED parpadea)")
            print("   🎮 DualSense: Mantén PS + Share hasta parpadeo rápido")
            print("   🎮 DualShock 4: Mantén PS + Share hasta parpadeo blanco")
            print("   🎮 Xbox: Mantén botón sincronización hasta parpadeo rápido")
            print("   ✅ Bluetooth debe estar activo en Windows")
            print("   📍 Mantén dispositivo cerca (< 10 metros)")
            print("\n   ⚠️ IMPORTANTE: Los dispositivos deben estar en modo emparejamiento")
            print("      ANTES de iniciar el escaneo")
        
        return discovered_devices
        
    except Exception as e:
        print(f"\n❌ Error durante el escaneo:")
        print(f"   Tipo: {type(e).__name__}")
        print(f"   Mensaje: {e}")
        import traceback
        print("\n📋 Traceback completo:")
        traceback.print_exc()
        return []

async def test_pairing(device_info):
    """Probar emparejamiento con un dispositivo"""
    try:
        print(f"\n🔗 Intentando emparejar: {device_info.name}")
        
        if not hasattr(device_info, 'pairing') or not device_info.pairing:
            print("❌ El dispositivo no tiene información de emparejamiento")
            return False
        
        if not device_info.pairing.can_pair:
            print("⚠️ Este dispositivo no se puede emparejar")
            return False
        
        print("⏳ Emparejando...")
        result = await device_info.pairing.pair_async()
        
        print(f"📊 Resultado: {result.status}")
        
        if result.status == DevicePairingResultStatus.PAIRED:
            print("✅ ¡Emparejamiento exitoso!")
            return True
        elif result.status == DevicePairingResultStatus.ALREADY_PAIRED:
            print("ℹ️ El dispositivo ya estaba emparejado")
            return True
        else:
            print(f"❌ Emparejamiento falló: {result.status}")
            return False
            
    except Exception as e:
        print(f"❌ Error al emparejar: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Función principal"""
    print("\n🚀 Iniciando prueba de escaneo Bluetooth Classic...\n")
    
    # Escanear dispositivos
    devices = await scan_bluetooth_classic()
    
    # Si hay dispositivos, preguntar si emparejar
    if devices and len(devices) > 0:
        print("\n" + "=" * 60)
        response = input("\n¿Deseas emparejar algún dispositivo? (s/n): ").lower()
        
        if response == 's':
            try:
                device_num = int(input(f"Número de dispositivo (1-{len(devices)}): "))
                if 1 <= device_num <= len(devices):
                    device = devices[device_num - 1]
                    await test_pairing(device)
                else:
                    print("⚠️ Número inválido")
            except ValueError:
                print("⚠️ Entrada inválida")
            except Exception as e:
                print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Prueba completada")
    print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelado por el usuario")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
