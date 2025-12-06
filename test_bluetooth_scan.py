"""
Script de prueba para escaneo Bluetooth usando winsdk
Ejecutar: python test_bluetooth_scan.py
"""

import asyncio
import sys

print("=" * 60)
print("🔍 Test de Escaneo Bluetooth Classic (HID) con winsdk")
print("=" * 60)

# Verificar que winsdk esté instalado
try:
    from winsdk.windows.devices.bluetooth import BluetoothDevice
    from winsdk.windows.devices.enumeration import (
        DeviceInformation, 
        DevicePairingResultStatus,
        DeviceInformationKind,
        DeviceClass
    )
    print("✅ winsdk instalado correctamente")
except ImportError as e:
    print(f"❌ Error: winsdk no está instalado")
    print(f"   Instala con: pip install winsdk")
    print(f"   Detalles: {e}")
    sys.exit(1)

async def scan_bluetooth_devices():
    """Escanear dispositivos Bluetooth no emparejados"""
    try:
        print("\n🔎 Probando diferentes métodos de escaneo...")
        
        discovered_devices = []
        
        # Método 1: Usar BluetoothLEAdvertisementWatcher para descubrimiento activo
        print("\n📡 Método 1: BluetoothLEAdvertisementWatcher")
        try:
            from winsdk.windows.devices.bluetooth.advertisement import (
                BluetoothLEAdvertisementWatcher,
                BluetoothLEScanningMode
            )
            
            watcher = BluetoothLEAdvertisementWatcher()
            watcher.scanning_mode = BluetoothLEScanningMode.ACTIVE
            
            scan_complete = asyncio.Event()
            device_addresses = set()
            
            def received_handler(watcher, args):
                address = args.bluetooth_address
                if address not in device_addresses:
                    device_addresses.add(address)
                    name = args.advertisement.local_name if args.advertisement.local_name else f"Device_{hex(address)}"
                    print(f"   ✨ Anuncio BLE detectado: {name} (RSSI: {args.raw_signal_strength_in_d_bm} dBm)")
                    discovered_devices.append({
                        'address': address,
                        'name': name,
                        'rssi': args.raw_signal_strength_in_d_bm,
                        'type': 'BLE'
                    })
            
            def stopped_handler(watcher, args):
                print("   ⏹️ Watcher detenido")
                scan_complete.set()
            
            # Registrar handlers
            watcher.add_received(received_handler)
            watcher.add_stopped(stopped_handler)
            
            print("   ⏳ Escaneando durante 10 segundos...")
            watcher.start()
            
            # Esperar 10 segundos
            await asyncio.sleep(10)
            
            # Detener watcher
            watcher.stop()
            await asyncio.sleep(1)
            
            print(f"   ✅ Método 1 completado: {len(device_addresses)} anuncios detectados")
            
        except Exception as e:
            print(f"   ❌ Método 1 falló: {e}")
            import traceback
            traceback.print_exc()
        
        # Método 2: Usar dispositivos emparejados como referencia
        print("\n📋 Método 2: Listar dispositivos ya emparejados")
        try:
            # Selector para dispositivos BLE emparejados
            paired_selector = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
            
            # Intentar diferentes formas de obtener dispositivos
            print("   ⏳ Buscando dispositivos emparejados...")
            
            # Crear watcher sin selector string, usando propiedades
            from winsdk.windows.devices.enumeration import DeviceClass
            
            # Probar con clase de dispositivo
            try:
                watcher2 = DeviceInformation.create_watcher_with_kind_aqs_filter_and_additional_properties(
                    paired_selector,
                    [],
                    DeviceInformationKind.DEVICE_INTERFACE
                )
                print("   ✅ Watcher creado con método alternativo")
            except:
                print("   ⚠️ No se pudo crear watcher con método alternativo")
            
        except Exception as e:
            print(f"   ❌ Método 2 falló: {e}")
        
        print(f"\n✅ Escaneo completado!")
        print(f"📊 Dispositivos encontrados: {len(discovered_devices)}")
        
        if discovered_devices:
            print("\n" + "=" * 60)
            print("📱 DISPOSITIVOS DETECTADOS:")
            print("=" * 60)
            
            for i, device in enumerate(discovered_devices, 1):
                print(f"\n🎮 Dispositivo #{i}:")
                print(f"   Nombre: {device['name']}")
                print(f"   Dirección: {hex(device['address'])}")
                print(f"   RSSI: {device['rssi']} dBm")
                print(f"   Tipo: {device['type']}")
        else:
            print("\n⚠️ No se encontraron dispositivos Bluetooth")
            print("\n💡 Consejos:")
            print("   • Activa Bluetooth en Windows")
            print("   • Pon tus dispositivos en modo emparejamiento")
            print("   • Mantén los dispositivos cerca (< 10 metros)")
            print("   • Presiona el botón de sincronización/emparejamiento")
            print("   • Los dispositivos BLE deben estar transmitiendo anuncios")
        
        return discovered_devices
        
    except Exception as e:
        print(f"\n❌ Error durante el escaneo:")
        print(f"   Tipo: {type(e).__name__}")
        print(f"   Mensaje: {e}")
        import traceback
        print("\n📋 Traceback completo:")
        traceback.print_exc()
        return []

async def test_pairing(device):
    """Probar emparejamiento con un dispositivo"""
    try:
        print(f"\n🔗 Intentando conectar con dispositivo BLE: {device['name']}")
        print(f"   Dirección: {hex(device['address'])}")
        
        # Obtener dispositivo BLE desde la dirección
        print("⏳ Obteniendo información del dispositivo...")
        ble_device = await BluetoothLEDevice.from_bluetooth_address_async(device['address'])
        
        if not ble_device:
            print("❌ No se pudo obtener el dispositivo BLE")
            return False
        
        print(f"✅ Dispositivo obtenido: {ble_device.name}")
        print(f"   Estado de conexión: {ble_device.connection_status}")
        
        # Intentar emparejar
        if hasattr(ble_device, 'device_information') and ble_device.device_information:
            device_info = ble_device.device_information
            
            if device_info.pairing and device_info.pairing.can_pair:
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
            else:
                print("⚠️ El dispositivo no soporta emparejamiento o ya está emparejado")
        else:
            print("⚠️ No se pudo acceder a la información de emparejamiento")
        
        return False
            
    except Exception as e:
        print(f"❌ Error al emparejar: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Función principal"""
    print("\n🚀 Iniciando prueba de escaneo Bluetooth...\n")
    
    # Escanear dispositivos
    devices = await scan_bluetooth_devices()
    
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
