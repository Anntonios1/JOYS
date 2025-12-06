"""
Test Batería REAL - Usando voltaje regulado
Método exacto de jc_toolkit con conversión de voltaje a porcentaje
"""

import sys
import time
import hid

print("=" * 70)
print("🔋 TEST BATERÍA REAL - CONVERSIÓN DE VOLTAJE")
print("=" * 70)
print()

NINTENDO_VENDOR_ID = 0x057E
JOYCON_L_PRODUCT = 0x2006
JOYCON_R_PRODUCT = 0x2007

timming_byte = 0

def get_battery_voltage(device):
    """
    Obtener batería usando subcomando 0x50 (método jc_toolkit)
    
    Retorna:
        - battery_byte: Byte de batería del input report (nivel discreto 0-4)
        - battery_voltage: Voltaje regulado de la batería (valor crudo)
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
                    battery_byte = reply[0x2]      # Byte estándar de batería (nivel discreto 0-4)
                    batt_volt_low = reply[0xF]     # Voltaje LSB
                    batt_volt_high = reply[0x10]   # Voltaje MSB
                    
                    # Combinar en uint16 (Little Endian)
                    battery_voltage = batt_volt_low | (batt_volt_high << 8)
                    
                    return battery_byte, battery_voltage
            
            retries += 1
        
        error_reading += 1
    
    return None, None

def voltage_to_percent(batt_volt):
    """
    Convertir voltaje regulado a porcentaje de batería
    Fórmula exacta de jc_toolkit (líneas 4430-4451 de FormJoy.h)
    """
    if batt_volt < 0x560:
        return 1
    elif 0x55F < batt_volt < 0x5A0:
        return ((batt_volt - 0x60) & 0xFF) / 7.0 + 1
    elif 0x59F < batt_volt < 0x5E0:
        return ((batt_volt - 0xA0) & 0xFF) / 2.625 + 11
    elif 0x5DF < batt_volt < 0x618:
        return (batt_volt - 0x5E0) / 1.8965 + 36
    elif 0x617 < batt_volt < 0x658:
        return ((batt_volt - 0x18) & 0xFF) / 1.8529 + 66
    elif batt_volt > 0x657:
        return 100
    else:
        return 0

def voltage_to_volts(batt_volt):
    """Convertir valor crudo a voltios reales"""
    return (batt_volt * 2.5) / 1000.0

def parse_battery_level(battery_byte):
    """Parsear el nivel discreto de batería (0-4)"""
    if battery_byte is None:
        return None, None
    
    # Nivel de batería en los 3 bits superiores (bits 5-7)
    battery_level = (battery_byte >> 5) & 0x7
    
    # Estado de carga en bit 4
    charging = (battery_byte >> 4) & 0x1
    
    return battery_level, bool(charging)

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
        
        print("\n🔋 Leyendo batería con VOLTAJE REGULADO...")
        print("   ⏱️  Enviando subcomando 0x50...")
        
        battery_byte, battery_voltage = get_battery_voltage(device)
        
        if battery_byte is not None and battery_voltage is not None:
            # Convertir voltaje a porcentaje
            battery_percent = voltage_to_percent(battery_voltage)
            battery_volts = voltage_to_volts(battery_voltage)
            
            # Obtener nivel discreto y estado de carga
            battery_level, charging = parse_battery_level(battery_byte)
            
            print(f"\n   📊 DATOS CRUDOS:")
            print(f"      • Battery Byte (0x2):  0x{battery_byte:02X} (nivel discreto: {battery_level})")
            print(f"      • Voltage Raw (0xF+0x10): 0x{battery_voltage:04X} ({battery_voltage})")
            print(f"      • Voltage Real: {battery_volts:.3f}V")
            
            print(f"\n   🔬 CONVERSIÓN DE VOLTAJE:")
            print(f"      • Rango de voltaje: 0x{battery_voltage:04X}")
            if battery_voltage < 0x560:
                print(f"      • Fórmula: Crítico (<0x560) → 1%")
            elif 0x55F < battery_voltage < 0x5A0:
                print(f"      • Fórmula: ((0x{battery_voltage:04X} - 0x60) & 0xFF) / 7.0 + 1")
            elif 0x59F < battery_voltage < 0x5E0:
                print(f"      • Fórmula: ((0x{battery_voltage:04X} - 0xA0) & 0xFF) / 2.625 + 11")
            elif 0x5DF < battery_voltage < 0x618:
                print(f"      • Fórmula: (0x{battery_voltage:04X} - 0x5E0) / 1.8965 + 36")
            elif 0x617 < battery_voltage < 0x658:
                print(f"      • Fórmula: ((0x{battery_voltage:04X} - 0x18) & 0xFF) / 1.8529 + 66")
            elif battery_voltage > 0x657:
                print(f"      • Fórmula: Lleno (>0x657) → 100%")
            
            print(f"\n   🔋 RESULTADO FINAL:")
            charge_status = "⚡ Cargando" if charging else "🔌 Desconectado"
            
            if battery_percent >= 90:
                color_emoji = "🟢"
            elif battery_percent >= 60:
                color_emoji = "🟢"
            elif battery_percent >= 40:
                color_emoji = "🟡"
            elif battery_percent >= 20:
                color_emoji = "🟠"
            else:
                color_emoji = "🔴"
            
            bar_length = 20
            filled = int(bar_length * battery_percent / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            print(f"      {color_emoji} Batería: {battery_percent:.0f}% ({battery_volts:.2f}V)")
            print(f"      [{bar}]")
            print(f"      {charge_status}")
            print(f"      Nivel discreto: {battery_level}/4")
            
            print(f"\n   💡 PRECISIÓN:")
            print(f"      • Voltaje regulado convertido a porcentaje continuo")
            print(f"      • Método exacto de jc_toolkit")
            print(f"      • Rango típico: 1.3V (vacío) a 1.6V (lleno)")
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
print("📊 CONCLUSIÓN - BATERÍA REAL CON VOLTAJE")
print("=" * 70)
print("\n🔍 MÉTODO USADO:")
print("   • Subcomando 0x50 (Request battery level)")
print("   • Lee voltaje regulado de bytes 0xF y 0x10")
print("   • Aplica fórmulas de conversión no lineales")
print("\n📈 FÓRMULAS DE CONVERSIÓN:")
print("   • < 0x560:              1% (Crítico)")
print("   • 0x560 - 0x59F:        ((volt-0x60)&0xFF)/7.0 + 1")
print("   • 0x5A0 - 0x5DF:        ((volt-0xA0)&0xFF)/2.625 + 11")
print("   • 0x5E0 - 0x617:        (volt-0x5E0)/1.8965 + 36")
print("   • 0x618 - 0x657:        ((volt-0x18)&0xFF)/1.8529 + 66")
print("   • > 0x657:              100% (Lleno)")
print("\n💡 NOTA:")
print("   Este método permite obtener porcentajes continuos (78%, 61%, etc)")
print("   en lugar de solo 5 niveles discretos (0%, 25%, 50%, 75%, 100%)")
print("=" * 70)
