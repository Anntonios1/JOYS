"""
Test real HID reading
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from modules.windows_hid_reader import get_windows_hid_reader

def test_real_battery():
    """Test reading real battery from Joy-Con"""
    print("🔋 Probando lectura real de batería via HID...")
    print()
    
    reader = get_windows_hid_reader()
    
    # Find Joy-Con devices
    devices = reader.find_joycon_devices()
    
    if not devices:
        print("❌ No se encontraron Joy-Cons via HID")
        print("   Verifica que:")
        print("   1. Los Joy-Cons estén conectados")
        print("   2. No estén siendo usados por otra aplicación")
        return
    
    print(f"✅ Encontrados {len(devices)} Joy-Cons via HID:")
    print()
    
    for i, device in enumerate(devices):
        print(f"  Dispositivo {i+1}:")
        print(f"    Vendor ID: {hex(device['vendor_id'])}")
        print(f"    Product ID: {hex(device['product_id'])}")
        print(f"    Manufacturer: {device['manufacturer_string']}")
        print(f"    Product: {device['product_string']}")
        
        # Try to read battery
        print(f"    Leyendo batería...")
        battery = reader.read_joycon_battery_real(device['path'])
        
        if battery is not None:
            print(f"    ✅ Batería: {battery}%")
        else:
            print(f"    ❌ No se pudo leer la batería")
        
        print()

if __name__ == "__main__":
    test_real_battery()
