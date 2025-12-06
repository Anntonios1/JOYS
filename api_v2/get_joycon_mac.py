"""
Utilidad para obtener la MAC address de un Joy-Con desde su información HID
"""
import hid

def get_joycon_serial_from_hid(device_path: bytes) -> str:
    """
    Obtiene el número de serial del Joy-Con desde HID
    Este serial es único por dispositivo y se puede usar para identificarlo
    """
    try:
        device = hid.device()
        device.open_path(device_path)
        
        # Leer el serial number del dispositivo HID
        serial = device.get_serial_number_string()
        device.close()
        
        return serial if serial else ""
    except Exception as e:
        print(f"Error obteniendo serial: {e}")
        return ""

def get_joycon_bluetooth_mac_by_serial(serial: str, side: str) -> str:
    """
    Busca la MAC de Bluetooth del Joy-Con usando su serial
    """
    import asyncio
    from bluetooth_manager import BluetoothManager
    
    async def search():
        joycons = await BluetoothManager.find_joycons()
        
        for joycon in joycons:
            # Los Joy-Cons tienen nombres como "Joy-Con (L)" o "Joy-Con (R)"
            if f"Joy-Con ({side})" in joycon["name"]:
                # Extraer MAC del ID de Bluetooth
                # Formato: ...Dev_DC68EB8346EE... o similar
                device_id = joycon["id"]
                import re
                mac_match = re.search(r'Dev_([0-9A-F]{12})', device_id, re.IGNORECASE)
                if mac_match:
                    return mac_match.group(1).upper()
        
        return None
    
    return asyncio.run(search())

if __name__ == "__main__":
    # Buscar Joy-Cons
    devices = hid.enumerate(0x057E, 0)
    
    for dev in devices:
        if dev['product_id'] in [0x2006, 0x2007]:
            path = dev['path']
            side = "L" if dev['product_id'] == 0x2006 else "R"
            
            serial = get_joycon_serial_from_hid(path)
            print(f"Joy-Con ({side}):")
            print(f"  Serial HID: {serial}")
            print(f"  Path: {path}")
            
            # Buscar MAC de Bluetooth
            mac = get_joycon_bluetooth_mac_by_serial(serial, side)
            if mac:
                print(f"  MAC Bluetooth: {mac}")
            else:
                print(f"  MAC Bluetooth: No encontrada")
            print()
