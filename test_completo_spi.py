"""
Test Completo - Batería, Colores y Vibración para Joy-Con y DualShock 4
Lee datos directamente de la memoria SPI del Joy-Con y vibra todos los dispositivos
"""

import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import hid

print("=" * 70)
print("🎮 TEST COMPLETO - TODOS LOS GAMEPADS")
print("=" * 70)
print()

# Device IDs
NINTENDO_VENDOR_ID = 0x057E
JOYCON_L_PRODUCT = 0x2006
JOYCON_R_PRODUCT = 0x2007

SONY_VENDOR_ID = 0x054C
DS4_V1_PRODUCT = 0x05C4
DS4_V2_PRODUCT = 0x09CC

# Variable global para packet counter
timming_byte = 0

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

def clear_buffer(device):
    """Limpiar completamente el buffer de entrada"""
    device.set_nonblocking(True)
    count = 0
    for _ in range(200):  # Leer hasta 200 paquetes
        data = device.read(64)
        if not data:
            break
        count += 1
    device.set_nonblocking(False)
    if count > 0:
        time.sleep(0.1)  # Esperar a que se estabilice

def send_subcmd(device, subcmd, data=None):
    """Enviar subcomando al Joy-Con"""
    global timming_byte
    
    report = bytearray(64)
    report[0] = 0x01  # Output report ID
    report[1] = timming_byte & 0xF  # Packet counter
    timming_byte += 1
    # Rumble data (neutral)
    report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
    report[10] = subcmd  # Subcommand
    
    if data:
        report[11:11+len(data)] = data
    
    device.write(bytes(report))

def read_spi(device, address, size):
    """Leer datos de la memoria SPI del Joy-Con"""
    # Limpiar buffer antes de enviar comando
    clear_buffer(device)
    
    # Preparar datos del comando SPI Read (subcmd 0x10)
    spi_data = bytearray(5)
    spi_data[0] = address & 0xFF
    spi_data[1] = (address >> 8) & 0xFF
    spi_data[2] = (address >> 16) & 0xFF
    spi_data[3] = (address >> 24) & 0xFF
    spi_data[4] = size
    
    send_subcmd(device, 0x10, spi_data)
    
    # Leer respuesta (intentar múltiples veces)
    for attempt in range(10):
        time.sleep(0.05)
        data = device.read(64, timeout_ms=500)
        
        if data and len(data) >= 20:
            # Respuesta válida: Report 0x21, ACK 0x90, Subcmd 0x10
            if data[0] == 0x21 and data[13] == 0x90 and data[14] == 0x10:
                # Verificar que la dirección coincide
                addr_reply = data[15] | (data[16] << 8) | (data[17] << 16) | (data[18] << 24)
                if addr_reply == address:
                    # Datos comienzan en byte 20
                    return data[20:20+size]
    
    return None

def get_battery_voltage(device):
    """
    Obtener batería usando subcomando 0x50 con conversión de voltaje
    Método exacto de jc_toolkit para porcentajes precisos (57%, 44%, etc)
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
                # Verificar respuesta correcta: *(u16*)&buf[0xD] == 0x50D0
                if len(reply) > 0xE and reply[0x0D] == 0xD0 and reply[0x0E] == 0x50:
                    battery_byte = reply[0x2]       # Byte estándar (nivel discreto)
                    batt_volt_low = reply[0xF]      # Voltaje LSB
                    batt_volt_high = reply[0x10]    # Voltaje MSB
                    
                    # Combinar en uint16 (Little Endian)
                    battery_voltage = batt_volt_low | (batt_volt_high << 8)
                    
                    # Convertir voltaje a porcentaje usando fórmulas de jc_toolkit
                    if battery_voltage < 0x560:
                        battery_percent = 1
                    elif 0x55F < battery_voltage < 0x5A0:
                        battery_percent = ((battery_voltage - 0x60) & 0xFF) / 7.0 + 1
                    elif 0x59F < battery_voltage < 0x5E0:
                        battery_percent = ((battery_voltage - 0xA0) & 0xFF) / 2.625 + 11
                    elif 0x5DF < battery_voltage < 0x618:
                        battery_percent = (battery_voltage - 0x5E0) / 1.8965 + 36
                    elif 0x617 < battery_voltage < 0x658:
                        battery_percent = ((battery_voltage - 0x18) & 0xFF) / 1.8529 + 66
                    elif battery_voltage > 0x657:
                        battery_percent = 100
                    else:
                        battery_percent = 0
                    
                    # Estado de carga desde battery_byte
                    charging = (battery_byte >> 4) & 0x1
                    
                    # Voltaje en voltios reales
                    battery_volts = (battery_voltage * 2.5) / 1000.0
                    
                    return int(battery_percent), bool(charging), battery_volts
            
            retries += 1
        
        error_reading += 1
    
    return None, None, None

def get_battery_voltage_spi(device):
    """Obtener voltaje de batería desde SPI (método más preciso)"""
    # La batería también se puede leer de reportes, pero SPI es más confiable
    # Para Joy-Con, el byte 2 del input report tiene la batería
    # Aquí usamos el método estándar del input report
    return get_battery_from_input(device)

def read_colors_spi(device):
    """Leer colores desde SPI (dirección 0x6050)"""
    color_data = read_spi(device, 0x6050, 12)
    
    if color_data and len(color_data) >= 12:
        return {
            'body': {'r': color_data[0], 'g': color_data[1], 'b': color_data[2]},
            'buttons': {'r': color_data[3], 'g': color_data[4], 'b': color_data[5]},
            'left_grip': {'r': color_data[6], 'g': color_data[7], 'b': color_data[8]},
            'right_grip': {'r': color_data[9], 'g': color_data[10], 'b': color_data[11]},
        }
    
    return None

def read_serial_number_spi(device):
    """Leer número de serie desde SPI (dirección 0x6000)"""
    # El serial number puede estar en 0x6000 o 0x6001
    for address in [0x6000, 0x6001]:
        serial_data = read_spi(device, address, 16)
        
        if serial_data:
            try:
                # El serial es una cadena ASCII
                serial = bytes(serial_data).decode('ascii', errors='ignore').strip('\x00').strip()
                if serial and len(serial) > 5:  # Verificar que sea un serial válido
                    return serial
            except:
                pass
    
    return None

def vibrate_device(device, duration_seconds=1.0, intensity=0.5):
    """Hacer vibrar el dispositivo por un tiempo determinado"""
    # Comando de vibración: subcmd 0x48 con enable=0x01
    send_subcmd(device, 0x48, [0x01])
    time.sleep(0.05)
    
    # Calcular valores de rumble
    # Formato: [HF amp, HF freq, LF amp, LF freq] x2 (para ambos motores)
    # Valores típicos para vibración media
    rumble_data = [
        0x00, 0x01, 0x40, 0x40,  # Motor izquierdo neutral
        0x00, 0x01, 0x40, 0x40   # Motor derecho neutral
    ]
    
    if intensity > 0:
        # Vibración con intensidad
        amp = int(0x64 * intensity)  # Amplitud
        rumble_data = [
            amp, 0x80, amp, 0x80,  # Motor izquierdo
            amp, 0x80, amp, 0x80   # Motor derecho
        ]
    
    # Enviar comando de rumble
    report = bytearray(64)
    report[0] = 0x10  # Rumble only report
    report[1] = 0x00  # Packet counter
    report[2:10] = rumble_data
    
    device.write(bytes(report))
    time.sleep(duration_seconds)
    
    # Detener vibración
    report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
    device.write(bytes(report))

def request_device_info(device):
    """Solicitar información del dispositivo (subcmd 0x02)"""
    # Limpiar buffer antes de enviar comando
    clear_buffer(device)
    
    send_subcmd(device, 0x02)
    
    # Leer respuesta
    for attempt in range(10):
        time.sleep(0.05)
        data = device.read(64, timeout_ms=500)
        
        if data and len(data) >= 20:
            if data[0] == 0x21 and data[14] == 0x02:  # Reply to device info
                # Firmware version: bytes 15-16
                fw_major = data[15]
                fw_minor = data[16]
                # Device type: byte 17
                device_type = data[17]
                
                type_names = {
                    0x01: "Joy-Con (L)",
                    0x02: "Joy-Con (R)",
                    0x03: "Pro Controller"
                }
                
                return {
                    'firmware': f"{fw_major}.{fw_minor}",
                    'device_type': type_names.get(device_type, f"Unknown (0x{device_type:02X})")
                }
    
    return None

def measure_polling_rate(device, duration_seconds=1.0):
    """Medir la tasa de sondeo (polling rate) del dispositivo"""
    device.set_nonblocking(True)
    
    # Limpiar buffer completamente
    for _ in range(100):
        data = device.read(64)
        if not data:
            break
    
    # Pequeña pausa para estabilizar
    time.sleep(0.1)
    
    # Contar paquetes recibidos
    packet_count = 0
    start_time = time.time()
    
    while time.time() - start_time < duration_seconds:
        data = device.read(64)
        if data:
            packet_count += 1
    
    elapsed = time.time() - start_time
    device.set_nonblocking(False)
    
    if packet_count > 0:
        polling_rate_hz = packet_count / elapsed
        polling_interval_ms = 1000.0 / polling_rate_hz
        return polling_rate_hz, polling_interval_ms, packet_count
    
    return 0, 0, 0

def vibrate_ds4(device, duration_seconds=1.0, intensity=0.9):
    """Hacer vibrar el DualShock 4"""
    intensity = max(0.0, min(1.0, intensity))
    
    # Probar solo motor pesado (más notable)
    small_motor = 0  # Motor rápido apagado
    large_motor = int(255 * intensity)  # Solo motor pesado
    
    # Bluetooth (basado exactamente en DS4Windows PrepareOutputReportInner)
    try:
        report = bytearray(78)
        report[0] = 0x11  # Report ID
        report[1] = 0xC4  # 0x80 | btPollRate donde btPollRate=0x04
        report[2] = 0x00  
        report[3] = 0x07  # outputFeaturesByte: rumble(0x01) + lightbar(0x02) + flash(0x04)
        report[4] = 0x04  
        report[5] = 0x00  
        report[6] = small_motor  # RumbleMotorStrengthRightLightFast
        report[7] = large_motor  # RumbleMotorStrengthLeftHeavySlow
        report[8] = 255  # LED R (Rojo para indicar vibración)
        report[9] = 0    # LED G
        report[10] = 0   # LED B
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
        
        result = device.write(bytes(report))
        print(f"   📝 BT Write: {result} bytes, Heavy Motor: {large_motor}, CRC: 0x{crc:08X}")
        
        if result > 0:
            # Enviar rumble continuamente (DS4 necesita reportes repetidos)
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                device.write(bytes(report))
                time.sleep(0.01)  # 100Hz
            
            # Detener
            report[7] = 0
            report[8] = 0    # LED volver a azul
            report[9] = 0
            report[10] = 255
            crc = ~crc32_ds4(crc_head)
            crc = ~crc32_ds4(report[0:74]) ^ crc
            report[74] = crc & 0xFF
            report[75] = (crc >> 8) & 0xFF
            report[76] = (crc >> 16) & 0xFF
            report[77] = (crc >> 24) & 0xFF
            device.write(bytes(report))
            return True
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    return False

def read_ds4_battery(device):
    """Leer batería del DualShock 4"""
    device.set_nonblocking(True)
    
    # Leer varios reportes
    for attempt in range(100):  # Aumentar intentos
        data = device.read(64)
        if data and len(data) > 10:
            report_id = data[0]
            
            # Report 0x11 para Bluetooth
            if report_id == 0x11 and len(data) >= 33:
                battery_byte = data[32]
                battery_level = (battery_byte & 0x0f) * 100 // 8
                charging = (data[31] & 0x10) != 0
                device.set_nonblocking(False)
                return min(battery_level, 100), charging, "Bluetooth"
            
            # Report 0x01 para USB
            elif report_id == 0x01 and len(data) >= 31:
                battery_byte = data[30]
                battery_level = (battery_byte & 0x0f) * 100 // 8
                charging = (data[29] & 0x10) != 0
                device.set_nonblocking(False)
                return min(battery_level, 100), charging, "USB"
        
        time.sleep(0.01)
    
    device.set_nonblocking(False)
    return None, None, None

# Buscar todos los dispositivos
print("🔍 Buscando gamepads...")
joycons = []
ds4_controllers = []

# Buscar Joy-Cons
for device_dict in hid.enumerate(NINTENDO_VENDOR_ID):
    if device_dict['product_id'] in [JOYCON_L_PRODUCT, JOYCON_R_PRODUCT]:
        joycons.append(device_dict)
        print(f"✅ Joy-Con encontrado: {device_dict['product_string']}")

# Buscar DualShock 4
for device_dict in hid.enumerate(SONY_VENDOR_ID):
    if device_dict['product_id'] in [DS4_V1_PRODUCT, DS4_V2_PRODUCT]:
        ds4_controllers.append(device_dict)
        print(f"✅ DualShock 4 encontrado: {device_dict['product_string']}")

if not joycons and not ds4_controllers:
    print("❌ No se encontraron gamepads")
    sys.exit(1)

print(f"\n✅ Total: {len(joycons)} Joy-Cons, {len(ds4_controllers)} DualShock 4\n")
print("=" * 70)

# Leer datos de cada Joy-Con
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
        device.set_nonblocking(True)  # Modo no-bloqueante para configuración
        
        print("📡 Conectando y configurando dispositivo...")
        
        # Enviar comando para habilitar vibración (despierta el dispositivo)
        send_subcmd(device, 0x48, [0x01])
        time.sleep(0.1)
        
        # Limpiar buffer con límite de iteraciones
        for _ in range(50):
            data = device.read(64)
            if not data:
                break
        device.set_nonblocking(False)
        
        # 1. LEER BATERÍA PRIMERO (más confiable al inicio)
        print("🔋 Leyendo batería...")
        # 1. LEER BATERÍA PRIMERO (usando voltaje para precisión)
        print("🔋 Leyendo batería con voltaje regulado...")
        battery, charging, volts = get_battery_voltage(device)
        
        if battery is not None:
            charge_status = "⚡ Cargando" if charging else "🔌 Desconectado"
            bar_length = 20
            filled = int(bar_length * battery / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            if battery >= 75:
                color_emoji = "🟢"
            elif battery >= 50:
                color_emoji = "🟡"
            elif battery >= 25:
                color_emoji = "🟠"
            else:
                color_emoji = "🔴"
            
            print(f"   {color_emoji} Batería: {battery}% ({volts:.2f}V) [{bar}] {charge_status}")
        print("\n🎨 Leyendo colores desde SPI...")
        colors = read_colors_spi(device)
        
        if colors:
            body = colors['body']
            buttons = colors['buttons']
            left_grip = colors['left_grip']
            right_grip = colors['right_grip']
            
            print(f"   ┌{'─' * 66}┐")
            print(f"   │ {'Body (Carcasa):':<30} RGB({body['r']:3}, {body['g']:3}, {body['b']:3})  #{body['r']:02X}{body['g']:02X}{body['b']:02X} │")
            print(f"   │ {'Buttons (Botones):':<30} RGB({buttons['r']:3}, {buttons['g']:3}, {buttons['b']:3})  #{buttons['r']:02X}{buttons['g']:02X}{buttons['b']:02X} │")
            print(f"   │ {'Left Grip:':<30} RGB({left_grip['r']:3}, {left_grip['g']:3}, {left_grip['b']:3})  #{left_grip['r']:02X}{left_grip['g']:02X}{left_grip['b']:02X} │")
            print(f"   │ {'Right Grip:':<30} RGB({right_grip['r']:3}, {right_grip['g']:3}, {right_grip['b']:3})  #{right_grip['r']:02X}{right_grip['g']:02X}{right_grip['b']:02X} │")
            print(f"   └{'─' * 66}┘")
        else:
            print(f"   ❌ No se pudieron leer colores")
        
        # 3. LEER NÚMERO DE SERIE
        print("\n🔢 Leyendo número de serie desde SPI...")
        serial = read_serial_number_spi(device)
        
        if serial:
            print(f"   📋 Serial: {serial}")
        else:
            print(f"   ⚠️ No se pudo leer número de serie")
        
        # 4. LEER INFORMACIÓN DEL DISPOSITIVO
        print("\n📱 Leyendo información del dispositivo...")
        device_info = request_device_info(device)
        
        if device_info:
            print(f"   📦 Tipo: {device_info['device_type']}")
            print(f"   🔧 Firmware: {device_info['firmware']}")
        else:
            print(f"   ⚠️ No se pudo leer información del dispositivo")
        
        # 5. MEDIR TASA DE SONDEO (POLLING RATE)
        print("\n📊 Midiendo tasa de sondeo (polling rate)...")
        print("   💡 Mueve el Joy-Con para mantenerlo activo...")
        print("   ⏱️  Capturando paquetes durante 2 segundos...")
        
        # Despertar dispositivo enviando vibración muy suave
        try:
            report = bytearray(64)
            report[0] = 0x10  # Rumble only
            report[1] = 0x00
            report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]  # Neutral rumble
            device.write(bytes(report))
            time.sleep(0.1)
        except:
            pass
        
        polling_hz, polling_ms, packets = measure_polling_rate(device, duration_seconds=2.0)
        
        if packets > 0:
            print(f"   📈 Paquetes recibidos: {packets}")
            print(f"   ⚡ Polling Rate: {polling_hz:.1f} Hz")
            print(f"   ⏱️  Intervalo: {polling_ms:.2f} ms")
        else:
            print(f"   ⚠️ No se recibieron paquetes (dispositivo en sleep mode)")
        
        # 6. VIBRAR DISPOSITIVO
        print(f"\n📳 Vibrando Joy-Con ({side})...")
        for i in range(5, 0, -1):
            print(f"   ⏱️  {i} segundos...", end='\r')
            time.sleep(1)
        
        print("   🎮 Iniciando vibración por 2 segundos..." + " " * 20)
        vibrate_device(device, duration_seconds=2.0, intensity=0.6)
        print("   ✅ Vibración completada")
        
        device.close()
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        try:
            device.close()
        except:
            pass

# Leer datos de cada DualShock 4
for idx, ds4_info in enumerate(ds4_controllers):
    product_name = ds4_info['product_string']
    device_path = ds4_info['path']
    
    print(f"\n🎮 DualShock 4 - {product_name}")
    print("-" * 70)
    
    try:
        device = hid.device()
        device.open_path(device_path)
        
        print("📡 Conectando al dispositivo...")
        time.sleep(0.2)
        
        # 1. LEER BATERÍA
        print("🔋 Leyendo batería...")
        battery, charging, connection_type = read_ds4_battery(device)
        
        if battery is not None:
            charge_status = "⚡ Cargando" if charging else "🔌 Desconectado"
            bar_length = 20
            filled = int(bar_length * battery / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            if battery >= 75:
                color_emoji = "🟢"
            elif battery >= 50:
                color_emoji = "🟡"
            elif battery >= 25:
                color_emoji = "🟠"
            else:
                color_emoji = "🔴"
            
            print(f"   {color_emoji} Batería: {battery}% [{bar}] {charge_status}")
            print(f"   🔗 Conexión: {connection_type}")
        else:
            print(f"   ❌ No se pudo leer batería (dispositivo inactivo o desconectado)")
            print(f"   💡 Presiona el botón PS para despertar el control")
        
        # 2. MEDIR TASA DE SONDEO (POLLING RATE)
        print("\n📊 Midiendo tasa de sondeo (polling rate)...")
        print("   💡 Mueve el control para mantenerlo activo...")
        print("   ⏱️  Capturando paquetes durante 2 segundos...")
        
        polling_hz, polling_ms, packets = measure_polling_rate(device, duration_seconds=2.0)
        
        if packets > 0:
            print(f"   📈 Paquetes recibidos: {packets}")
            print(f"   ⚡ Polling Rate: {polling_hz:.1f} Hz")
            print(f"   ⏱️  Intervalo: {polling_ms:.2f} ms")
        else:
            print(f"   ⚠️ No se recibieron paquetes (dispositivo inactivo)")
        
        # 3. VIBRAR DISPOSITIVO
        print(f"\n📳 Vibrando DualShock 4...")
        for i in range(5, 0, -1):
            print(f"   ⏱️  {i} segundos...", end='\r')
            time.sleep(1)
        
        print("   🎮 Iniciando vibración por 2 segundos..." + " " * 20)
        vibrate_ds4(device, duration_seconds=2.0, intensity=0.7)
        print("   ✅ Vibración completada")
        
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
print("\n✅ DATOS LEÍDOS:")
print("   • Joy-Con: Batería (voltaje preciso), Colores RGB, Serial, Firmware, Polling Rate, Vibración")
print("   • DualShock 4: Batería, Polling Rate, Vibración")
print("\n💡 CAPACIDADES:")
print("   • Lectura batería con voltaje regulado (subcomando 0x50)")
print("   • Lectura directa via SPI (Joy-Con colores/serial)")
print("   • Lectura de HID reports (DS4)")
print("   • Control de vibración para ambos")
print("\n📊 DATOS DISPONIBLES PARA LA API:")
print("   1. Batería PRECISA (%) + Voltaje (V) + Estado de carga")
print("   2. Colores RGB (Joy-Con)")
print("   3. Número de serie único (Joy-Con)")
print("   4. Firmware version (Joy-Con)")
print("   5. Tipo de dispositivo")
print("   6. Polling rate (Hz) y latencia (ms)")
print("   7. Control de vibración (localize)")
print("\n✅ Método de batería actualizado al de jc_toolkit")
print("   Porcentajes precisos: 57%, 44%, etc (no solo 25%, 50%, 75%, 100%)")
print("=" * 70)
