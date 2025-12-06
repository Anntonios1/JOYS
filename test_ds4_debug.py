"""
Debug DualShock 4 - Ver raw data
"""

import hid
import time

DS4_VENDOR_ID = 0x054C
DS4_V2_PRODUCT_ID = 0x09CC

print("🔍 Buscando DualShock 4...")

for device_info in hid.enumerate(DS4_VENDOR_ID, DS4_V2_PRODUCT_ID):
    print(f"✅ Encontrado: {device_info['product_string']}")
    print(f"   Path: {device_info['path']}")
    
    try:
        device = hid.device()
        device.open_path(device_info['path'])
        device.set_nonblocking(True)
        
        print("\n📡 Leyendo reportes (mueve el stick o presiona botones)...")
        
        for i in range(50):
            data = device.read(64)
            
            if data:
                print(f"\nReporte #{i+1}: {len(data)} bytes")
                print(f"   Byte[0]: 0x{data[0]:02X} (Report ID)")
                
                if data[0] == 0x11 and len(data) >= 33:
                    # Bluetooth report - DS4Windows copia desde byte 2
                    # Entonces batería estaría en byte 32 (30+2 offset)
                    print(f"   Byte[32]: 0x{data[32]:02X} (batería BT, posición 30+offset)")
                    battery_byte = data[32]
                    charging = (battery_byte & 0x10) != 0
                    battery_raw = battery_byte & 0x0f
                    max_bat = 11 if charging else 8
                    percentage = (battery_raw * 100) // max_bat
                    print(f"   Raw: {battery_raw}, Charging: {charging}, Max: {max_bat}")
                    print(f"   Batería calculada: {percentage}%")
            else:
                print(".", end="", flush=True)
            
            time.sleep(0.1)
        
        device.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
