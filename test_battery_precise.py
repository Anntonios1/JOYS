"""
Test Batería Precisa - Usando Subcomando 0x50
Basado en el método de jc_toolkit que es más preciso
"""

import sys
import time
import hid

print("=" * 70)
print("🔋 TEST BATERÍA PRECISA - SUBCOMANDO 0x50")
print("=" * 70)
print()

NINTENDO_VENDOR_ID = 0x057E
JOYCON_L_PRODUCT = 0x2006
JOYCON_R_PRODUCT = 0x2007

timming_byte = 0

def send_subcmd(device, subcmd, data=None):
    """Enviar subcomando al Joy-Con"""
    global timming_byte
    
    report = bytearray(49)
    report[0] = 0x01  # Output report ID
    report[1] = timming_byte & 0xF  # Packet counter
    timming_byte += 1
    # Rumble data (neutral)
    report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
    report[10] = subcmd  # Subcommand
    
    if data:
        report[11:11+len(data)] = data
    
    device.write(bytes(report))

def get_battery_subcmd_0x50(device):
    """
    Obtener batería usando subcomando 0x50 (método preciso de jc_toolkit)
    
    Retorna:
        - test_buf[0] = buf[0x2]:  Byte de batería del input report
        - test_buf[1] = buf[0xF]:  Valor del subcmd reply byte 1
        - test_buf[2] = buf[0x10]: Valor del subcmd reply byte 2
    """
    global timming_byte
    
    error_reading = 0
    
    while error_reading < 20:
        # Preparar comando
        buf = bytearray(49)
        buf[0] = 0x01  # cmd
        buf[1] = timming_byte & 0xF  # timer
        timming_byte += 1
        buf[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]  # rumble neutral
        buf[10] = 0x50  # subcmd = 0x50 (Request battery level)
        
        # Enviar comando
        device.write(bytes(buf))
        
        # Leer respuesta
        retries = 0
        while retries < 8:
            reply = device.read(64, timeout_ms=64)
            
            if reply and len(reply) >= 0x11:
                # Verificar que sea la respuesta correcta: *(u16*)&buf[0xD] == 0x50D0
                if len(reply) > 0xE and reply[0x0D] == 0xD0 and reply[0x0E] == 0x50:
                    # Extraer datos de batería
                    battery_byte = reply[0x2]      # Byte estándar de batería del input report
                    battery_reply1 = reply[0xF]    # Byte 1 del subcmd reply
                    battery_reply2 = reply[0x10]   # Byte 2 del subcmd reply
                    
                    return battery_byte, battery_reply1, battery_reply2
            
            retries += 1
        
        error_reading += 1
    
    return None, None, None

def parse_battery_byte(battery_byte):
    """Parsear el byte estándar de batería"""
    if battery_byte is None:
        return None, None
    
    # Nivel de batería en los 3 bits superiores (5, 6, 7)
    battery_level = (battery_byte >> 5) & 0x7  # 0-4 (5 niveles)
    
    # Estado de carga en bit 4
    charging = (battery_byte >> 4) & 0x1
    
    # Convertir a porcentaje
    battery_percent = battery_level * 25  # 0->0%, 1->25%, 2->50%, 3->75%, 4->100%
    
    return battery_percent, bool(charging)

# Buscar Joy-Cons
print("🔍 Buscando Joy-Cons...")
joycons = []

for device_dict in hid.enumerate(NINTENDO_VENDOR_ID):
    if device_dict['product_id'] in [JOYCON_L_PRODUCT, JOYCON_R_PRODUCT]:
        joycons.append(device_dict)
        print(f"✅ Joy-Con encontrado: {device_dict['product_string']}")

if not joycons:
    print("❌ No se encontraron Joy-Cons")
    sys.exit(1)

print(f"\n✅ Total: {len(joycons)} Joy-Cons\n")
print("=" * 70)

# Test cada Joy-Con
for idx, joycon_info in enumerate(joycons):
    product_name = joycon_info['product_string']
    device_path = joycon_info['path']
    product_id = joycon_info['product_id']
    
    side = "L" if product_id == JOYCON_L_PRODUCT else "R"
    
    print(f"\n🎮 Joy-Con ({side}) - {product_name}")
    print("-" * 70)
    
    try:
        device = hid.device()
        device.open_path(device_path)
        device.set_nonblocking(False)
        
        print("\n🔋 Leyendo batería con SUBCOMANDO 0x50 (método preciso)...")
        print("   ⏱️  Enviando comando y esperando respuesta...")
        
        battery_byte, reply1, reply2 = get_battery_subcmd_0x50(device)
        
        if battery_byte is not None:
            battery_percent, charging = parse_battery_byte(battery_byte)
            
            print(f"\n   📊 DATOS CRUDOS:")
            print(f"      • Battery Byte (0x2):  0x{battery_byte:02X} ({battery_byte})")
            print(f"      • Reply Byte 1 (0xF):  0x{reply1:02X} ({reply1})")
            print(f"      • Reply Byte 2 (0x10): 0x{reply2:02X} ({reply2})")
            
            print(f"\n   📊 ANÁLISIS DEL BATTERY BYTE (0x{battery_byte:02X}):")
            print(f"      • Bits 7-5 (nivel):    {(battery_byte >> 5) & 0x7} ({['Crítico', 'Bajo', 'Medio', 'Alto', 'Lleno'][(battery_byte >> 5) & 0x7] if (battery_byte >> 5) & 0x7 < 5 else 'Desconocido'})")
            print(f"      • Bit 4 (cargando):    {(battery_byte >> 4) & 0x1} ({'Sí' if (battery_byte >> 4) & 0x1 else 'No'})")
            print(f"      • Bits 3-1 (conexión): {(battery_byte >> 1) & 0x7}")
            print(f"      • Bit 0:               {battery_byte & 0x1}")
            
            print(f"\n   🔋 RESULTADO:")
            charge_status = "⚡ Cargando" if charging else "🔌 Desconectado"
            
            if battery_percent == 100:
                color_emoji = "🟢"
                level_text = "LLENO"
            elif battery_percent == 75:
                color_emoji = "🟢"
                level_text = "ALTO"
            elif battery_percent == 50:
                color_emoji = "🟡"
                level_text = "MEDIO"
            elif battery_percent == 25:
                color_emoji = "🟠"
                level_text = "BAJO"
            else:
                color_emoji = "🔴"
                level_text = "CRÍTICO"
            
            bar_length = 20
            filled = int(bar_length * battery_percent / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            print(f"      {color_emoji} Batería: {battery_percent}% ({level_text})")
            print(f"      [{bar}]")
            print(f"      {charge_status}")
            
            print(f"\n   💡 PRECISIÓN:")
            print(f"      • Este método usa el subcomando 0x50")
            print(f"      • Es el mismo que usa jc_toolkit")
            print(f"      • Devuelve niveles discretos: 0%, 25%, 50%, 75%, 100%")
            print(f"      • La batería no se lee en porcentajes continuos")
        else:
            print(f"   ❌ No se pudo leer batería después de 20 intentos")
        
        device.close()
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            device.close()
        except:
            pass

print("\n" + "=" * 70)
print("📊 CONCLUSIÓN - BATERÍA PRECISA")
print("=" * 70)
print("\n🔍 MÉTODO USADO:")
print("   • Subcomando 0x50 (Request battery level)")
print("   • Mismo método que jc_toolkit (herramienta oficial)")
print("   • Respuesta en report 0x21 con ACK 0xD0 y subcmd 0x50")
print("\n📈 NIVELES DE BATERÍA:")
print("   • Joy-Con reporta 5 niveles discretos:")
print("     - 0: Crítico (0%)")
print("     - 1: Bajo (25%)")
print("     - 2: Medio (50%)")
print("     - 3: Alto (75%)")
print("     - 4: Lleno (100%)")
print("\n💡 NOTA:")
print("   El Joy-Con NO reporta porcentajes continuos (ej: 73%, 68%)")
print("   Solo reporta estos 5 niveles discretos")
print("   Por eso jc_toolkit muestra valores exactos como 75% o 50%")
print("=" * 70)
