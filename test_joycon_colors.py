"""
Test - Leer colores del Joy-Con via SPI
Los colores se almacenan en memoria SPI del Joy-Con
"""

import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from modules.windows_hid_reader import get_windows_hid_reader
import hid

print("=" * 70)
print("🎨 LEER COLORES DEL JOY-CON")
print("=" * 70)
print()

# Joy-Con IDs
NINTENDO_VENDOR_ID = 0x057E
JOYCON_L_PRODUCT = 0x2006
JOYCON_R_PRODUCT = 0x2007

# Buscar Joy-Cons
print("🔍 Buscando Joy-Cons...")
joycons = []

for device_dict in hid.enumerate(NINTENDO_VENDOR_ID):
    if device_dict['product_id'] in [JOYCON_L_PRODUCT, JOYCON_R_PRODUCT]:
        joycons.append(device_dict)
        print(f"✅ Encontrado: {device_dict['product_string']}")

if not joycons:
    print("❌ No se encontraron Joy-Cons")
    sys.exit(1)

print(f"\n✅ Total: {len(joycons)} Joy-Cons\n")
print("=" * 70)

# Leer colores de cada Joy-Con
for idx, joycon_info in enumerate(joycons):
    product_name = joycon_info['product_string']
    device_path = joycon_info['path']
    
    print(f"\n🎮 {product_name}")
    print("-" * 70)
    
    try:
        device = hid.device()
        device.open_path(device_path)
        device.set_nonblocking(False)
        
        print("📡 Enviando comando SPI READ (subcommand 0x10)...")
        
        # Construir comando para leer SPI
        # Formato: [report_id, rumble_data (8 bytes), subcmd, spi_address (4 bytes LE), size]
        report = bytearray(64)
        report[0] = 0x01  # Output report ID
        report[1] = 0x00  # Packet counter
        # Rumble data (neutral) bytes 2-9
        report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
        report[10] = 0x10  # Subcommand: SPI Flash Read
        
        # Dirección SPI 0x6050 (colors) en little-endian
        report[11] = 0x50  # Address low byte
        report[12] = 0x60  # Address high byte
        report[13] = 0x00
        report[14] = 0x00
        report[15] = 0x0C  # Read 12 bytes (body + buttons + grips)
        
        device.write(bytes(report))
        print("   ✅ Comando enviado")
        
        # Leer respuesta (intentar múltiples veces)
        print("   ⏳ Esperando respuesta...")
        
        response = None
        for attempt in range(10):
            time.sleep(0.05)
            data = device.read(64, timeout_ms=500)
            
            if data and len(data) >= 20:
                # Buscar respuesta con report ID 0x21 y subcommand 0x10
                if data[0] == 0x21 and data[14] == 0x10:
                    response = data
                    break
                elif attempt < 9:
                    print(f"      Intento {attempt+1}: Report 0x{data[0]:02X}, esperando 0x21...")
        
        if response and len(response) >= 20:
            # La respuesta del Joy-Con:
            # byte 0: report ID (0x21 para input report con subcmd reply)
            # bytes 1-12: standard input data
            # byte 13: ACK byte (0x80 | subcmd)
            # byte 14: subcommand ID reply  
            # bytes 15-18: SPI address
            # byte 19: size
            # bytes 20+: data
            
            print(f"   📋 Report ID: 0x{response[0]:02X}")
            print(f"   📋 Byte 13 (ACK): 0x{response[13]:02X}")
            print(f"   📋 Byte 14 (Subcmd): 0x{response[14]:02X}")
            
            if response[0] == 0x21 and response[14] == 0x10:  # Input report with SPI read reply
                print("   ✅ Respuesta SPI recibida\n")
                
                # Extraer colores (12 bytes desde posición 20)
                color_data = response[20:32]
                
                # Body color (bytes 0-2) - RGB
                body_r = color_data[0]
                body_g = color_data[1]
                body_b = color_data[2]
                
                # Buttons color (bytes 3-5) - RGB
                buttons_r = color_data[3]
                buttons_g = color_data[4]
                buttons_b = color_data[5]
                
                # Left grip color (bytes 6-8) - RGB
                left_grip_r = color_data[6]
                left_grip_g = color_data[7]
                left_grip_b = color_data[8]
                
                # Right grip color (bytes 9-11) - RGB
                right_grip_r = color_data[9]
                right_grip_g = color_data[10]
                right_grip_b = color_data[11]
                
                print(f"   🎨 COLORES DEL JOY-CON:")
                print(f"   ┌{'─' * 66}┐")
                print(f"   │ {'Body (Carcasa):':<30} RGB({body_r:3}, {body_g:3}, {body_b:3})  #{body_r:02X}{body_g:02X}{body_b:02X} │")
                print(f"   │ {'Buttons (Botones):':<30} RGB({buttons_r:3}, {buttons_g:3}, {buttons_b:3})  #{buttons_r:02X}{buttons_g:02X}{buttons_b:02X} │")
                print(f"   │ {'Left Grip:':<30} RGB({left_grip_r:3}, {left_grip_g:3}, {left_grip_b:3})  #{left_grip_r:02X}{left_grip_g:02X}{left_grip_b:02X} │")
                print(f"   │ {'Right Grip:':<30} RGB({right_grip_r:3}, {right_grip_g:3}, {right_grip_b:3})  #{right_grip_r:02X}{right_grip_g:02X}{right_grip_b:02X} │")
                print(f"   └{'─' * 66}┘")
                
            else:
                print(f"   ❌ Respuesta inesperada: subcmd reply = 0x{response[14]:02X}")
                print(f"   Bytes: {' '.join(f'{b:02X}' for b in response[:30])}")
        else:
            print(f"   ❌ No se recibió respuesta válida")
        
        device.close()
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        try:
            device.close()
        except:
            pass

print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)
print("\n💡 Los colores se leen desde la dirección SPI 0x6050")
print("   • Body: Bytes 0-2 (RGB)")
print("   • Buttons: Bytes 3-5 (RGB)")  
print("   • Left Grip: Bytes 6-8 (RGB)")
print("   • Right Grip: Bytes 9-11 (RGB)")
print("\n✅ Listo para implementar en la API")
print("=" * 70)
