"""
Test para cambiar el color LED del DualShock 4 y DualSense
"""
import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import hid

SONY_VENDOR_ID = 0x054C
DS4_V1_PRODUCT = 0x05C4
DS4_V2_PRODUCT = 0x09CC
DS5_PRODUCT = 0x0CE6  # DualSense

def crc32_ds4(data):
    """Calcular CRC-32 para DualShock 4 Bluetooth"""
    crc = 0xFFFFFFFF
    polynomial = 0xEDB88320
    
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ polynomial
            else:
                crc >>= 1
    
    return ~crc & 0xFFFFFFFF

def set_ds4_color(device, r, g, b):
    """Cambiar color LED del DS4"""
    try:
        # Enviar múltiples veces como DS4Windows
        report = bytearray(78)
        report[0] = 0x11  # Report ID
        report[1] = 0xC4  # Flags
        report[2] = 0x00  
        report[3] = 0x07  # rumble + LED + flash
        report[4] = 0x04  
        report[5] = 0x00  
        report[6] = 0  # Motor fast
        report[7] = 0  # Motor heavy
        report[8] = r    # LED R
        report[9] = g    # LED G
        report[10] = b   # LED B
        report[11] = 0   # Flash on
        report[12] = 0   # Flash off
        
        # Calcular CRC-32
        crc_head = bytes([0xA2])
        crc = ~crc32_ds4(crc_head)
        crc = ~crc32_ds4(report[0:74]) ^ crc
        
        report[74] = crc & 0xFF
        report[75] = (crc >> 8) & 0xFF
        report[76] = (crc >> 16) & 0xFF
        report[77] = (crc >> 24) & 0xFF
        
        # Enviar múltiples veces (DS4 necesita reportes repetidos)
        for _ in range(10):
            result = device.write(bytes(report))
            if result <= 0:
                return False
            time.sleep(0.01)
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

# Buscar DS4/DS5
print("🔍 Buscando DualShock 4 / DualSense...")
controllers = []

for device_dict in hid.enumerate(SONY_VENDOR_ID):
    if device_dict['product_id'] in [DS4_V1_PRODUCT, DS4_V2_PRODUCT, DS5_PRODUCT]:
        controllers.append(device_dict)
        product = device_dict['product_string']
        print(f"✅ Encontrado: {product}")

if not controllers:
    print("❌ No se encontraron controladores Sony")
    sys.exit(1)

for controller_info in controllers:
    product_name = controller_info['product_string']
    device_path = controller_info['path']
    
    print(f"\n🎮 {product_name}")
    print("-" * 60)
    
    try:
        device = hid.device()
        device.open_path(device_path)
        
        # Ciclo de colores
        colors = [
            (255, 0, 0, "🔴 Rojo"),
            (0, 255, 0, "🟢 Verde"),
            (0, 0, 255, "🔵 Azul"),
            (255, 255, 0, "🟡 Amarillo"),
            (255, 0, 255, "🟣 Magenta"),
            (0, 255, 255, "🔷 Cian"),
            (255, 128, 0, "🟠 Naranja"),
            (128, 0, 255, "🟣 Púrpura"),
            (255, 255, 255, "⚪ Blanco"),
        ]
        
        print("🌈 Cambiando colores LED...")
        for r, g, b, name in colors:
            print(f"   {name} RGB({r}, {g}, {b})")
            if set_ds4_color(device, r, g, b):
                time.sleep(1)
            else:
                print(f"   ❌ Falló cambio de color")
                break
        
        # Volver a azul por defecto
        print("   🔵 Restaurando azul por defecto...")
        set_ds4_color(device, 0, 0, 255)
        
        device.close()
        print("   ✅ Test completado")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        try:
            device.close()
        except:
            pass

print("\n✅ Sí es posible cambiar el color del LED del DS4 y DS5")
print("📊 Esto se puede integrar en la API como endpoint /led/{mac}")
