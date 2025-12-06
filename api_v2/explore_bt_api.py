"""
Explorar la API de Bluetooth de Windows para ver qué datos proporciona
"""
import asyncio
from winsdk.windows.devices.enumeration import DeviceInformation, DeviceInformationKind
from winsdk.windows.devices.bluetooth import BluetoothDevice

async def get_signal_strength():
    print('=' * 70)
    print('INTENTANDO OBTENER RSSI / SIGNAL STRENGTH')
    print('=' * 70)
    
    # Propiedades que queremos
    requested_properties = [
        'System.Devices.Aep.SignalStrength',
        'System.Devices.Aep.IsConnected',
        'System.Devices.Aep.IsPaired',
        'System.Devices.Aep.IsPresent',
        'System.Devices.Aep.Bluetooth.LastSeenTime',
        'System.Devices.Aep.DeviceAddress',
    ]
    
    # Buscar con kind AssociationEndpoint para obtener más info
    # Bluetooth Protocol ID
    selector = '(System.Devices.Aep.ProtocolId:="{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}")'
    
    try:
        devices = await DeviceInformation.find_all_async(
            selector,
            requested_properties,
            DeviceInformationKind.ASSOCIATION_ENDPOINT
        )
        
        device_list = list(devices)
        print(f'\nDispositivos Bluetooth encontrados: {len(device_list)}')
        
        for dev in device_list:
            print(f'\n### {dev.name}')
            print(f'    ID: {dev.id[:60]}...')
            
            props = dev.properties
            for key in props:
                try:
                    value = props[key]
                    # Convertir objetos de Windows a valores legibles
                    if hasattr(value, 'value'):
                        value = value.value
                    print(f'    {key.split(".")[-1]}: {value}')
                except Exception as e:
                    print(f'    {key.split(".")[-1]}: <error: {e}>')
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()


async def explore_ble_rssi():
    """Explorar RSSI en dispositivos BLE"""
    print('\n' + '=' * 70)
    print('EXPLORANDO BLE ADVERTISEMENT (para RSSI)')
    print('=' * 70)
    
    try:
        from winsdk.windows.devices.bluetooth.advertisement import (
            BluetoothLEAdvertisementWatcher,
            BluetoothLEScanningMode
        )
        
        watcher = BluetoothLEAdvertisementWatcher()
        watcher.scanning_mode = BluetoothLEScanningMode.ACTIVE
        
        devices_found = {}
        
        def on_received(sender, args):
            addr = hex(args.bluetooth_address)
            rssi = args.raw_signal_strength_in_d_bm
            
            if addr not in devices_found:
                devices_found[addr] = rssi
                print(f'  BLE Device: {addr} | RSSI: {rssi} dBm')
        
        watcher.add_received(on_received)
        watcher.start()
        
        print('Escaneando BLE por 5 segundos...')
        await asyncio.sleep(5)
        
        watcher.stop()
        
        print(f'\nTotal dispositivos BLE encontrados: {len(devices_found)}')
        
    except Exception as e:
        print(f'Error BLE: {e}')


async def main():
    # Datos de dispositivo específico
    print('=' * 70)
    print('DATOS COMPLETOS DE UN JOY-CON')
    print('=' * 70)
    
    import re
    mac_int = int('DC68EB8346EE', 16)  # Joy-Con R
    
    bt_device = await BluetoothDevice.from_bluetooth_address_async(mac_int)
    
    if bt_device:
        print(f'\n### {bt_device.name}')
        print(f'    MAC: {hex(bt_device.bluetooth_address)}')
        print(f'    Estado conexión: {"Conectado" if bt_device.connection_status == 1 else "Desconectado"}')
        print(f'    Tipo: {"Clásico" if bt_device.bluetooth_device_id.is_classic_device else "BLE"}')
        print(f'    Conexión segura: {bt_device.was_secure_connection_used_for_pairing}')
        
        cod = bt_device.class_of_device
        if cod:
            # Decodificar Class of Device
            major_classes = {0: 'Misc', 1: 'Computer', 2: 'Phone', 3: 'Network', 
                           4: 'Audio/Video', 5: 'Peripheral', 6: 'Imaging', 
                           7: 'Wearable', 8: 'Toy', 9: 'Health'}
            print(f'\n    Class of Device:')
            print(f'      Major: {major_classes.get(cod.major_class, "Unknown")} ({cod.major_class})')
            print(f'      Minor: {cod.minor_class}')
            print(f'      Services: {bin(cod.service_capabilities)}')
        
        # SDP Records
        sdp = bt_device.sdp_records
        if sdp:
            print(f'\n    SDP Records: {len(list(sdp))} registros')
            for i, record in enumerate(sdp):
                print(f'      [{i}] {record}')
        
        # RFCOMM Services
        try:
            services = await bt_device.get_rfcomm_services_async()
            if services and services.services:
                print(f'\n    RFCOMM Services: {len(list(services.services))}')
                for svc in services.services:
                    print(f'      - UUID: {svc.service_id.uuid}')
        except Exception as e:
            print(f'    RFCOMM: {e}')
    
    # Ahora obtener datos de todos los dispositivos
    await get_signal_strength()
    
    # Explorar BLE (por si hay dispositivos BLE)
    await explore_ble_rssi()


if __name__ == '__main__':
    asyncio.run(main())
