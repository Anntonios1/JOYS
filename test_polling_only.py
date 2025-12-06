"""
Test Ligero - Solo Polling Rate
Sin lecturas SPI para evitar conflictos de recursos
"""

import sys
import time
import hid

print("=" * 70)
print("📊 TEST LIGERO - SOLO POLLING RATE")
print("=" * 70)
print()

# Device IDs
NINTENDO_VENDOR_ID = 0x057E
JOYCON_L_PRODUCT = 0x2006
JOYCON_R_PRODUCT = 0x2007

SONY_VENDOR_ID = 0x054C
DS4_V1_PRODUCT = 0x05C4
DS4_V2_PRODUCT = 0x09CC

def measure_polling_rate(device, duration_seconds=2.0):
    """Medir la tasa de sondeo (polling rate) del dispositivo"""
    device.set_nonblocking(True)
    
    # Limpiar buffer
    for _ in range(50):
        data = device.read(64)
        if not data:
            break
    
    time.sleep(0.1)
    
    # Contar paquetes
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

def get_quick_battery_joycon(device):
    """Obtener batería rápida sin SPI"""
    device.set_nonblocking(True)
    
    # Limpiar buffer
    for _ in range(20):
        data = device.read(64)
        if not data:
            break
    
    time.sleep(0.05)
    
    # Leer reportes
    for attempt in range(30):
        data = device.read(64)
        
        if data and len(data) >= 3:
            report_id = data[0]
            
            if report_id in [0x21, 0x30, 0x31, 0x3F]:
                battery_byte = data[2]
                
                if battery_byte != 0x00:
                    battery_level = ((battery_byte & 0xE0) >> 4) * 100 // 8
                    charging = (battery_byte & 0x10) != 0
                    device.set_nonblocking(False)
                    return min(battery_level, 100), charging
        
        time.sleep(0.01)
    
    device.set_nonblocking(False)
    return None, None

def get_quick_battery_ds4(device):
    """Obtener batería rápida DS4"""
    device.set_nonblocking(True)
    
    for attempt in range(50):
        data = device.read(64)
        if data and len(data) > 10:
            report_id = data[0]
            
            # Bluetooth
            if report_id == 0x11 and len(data) >= 33:
                battery_byte = data[32]
                battery_level = (battery_byte & 0x0f) * 100 // 8
                charging = (data[31] & 0x10) != 0
                device.set_nonblocking(False)
                return min(battery_level, 100), charging, "BT"
            
            # USB
            elif report_id == 0x01 and len(data) >= 31:
                battery_byte = data[30]
                battery_level = (battery_byte & 0x0f) * 100 // 8
                charging = (data[29] & 0x10) != 0
                device.set_nonblocking(False)
                return min(battery_level, 100), charging, "USB"
        
        time.sleep(0.01)
    
    device.set_nonblocking(False)
    return None, None, None

# Buscar dispositivos
print("🔍 Buscando gamepads...")
joycons = []
ds4_controllers = []

for device_dict in hid.enumerate(NINTENDO_VENDOR_ID):
    if device_dict['product_id'] in [JOYCON_L_PRODUCT, JOYCON_R_PRODUCT]:
        joycons.append(device_dict)
        print(f"✅ Joy-Con encontrado: {device_dict['product_string']}")

for device_dict in hid.enumerate(SONY_VENDOR_ID):
    if device_dict['product_id'] in [DS4_V1_PRODUCT, DS4_V2_PRODUCT]:
        ds4_controllers.append(device_dict)
        print(f"✅ DualShock 4 encontrado: {device_dict['product_string']}")

if not joycons and not ds4_controllers:
    print("❌ No se encontraron gamepads")
    sys.exit(1)

print(f"\n✅ Total: {len(joycons)} Joy-Cons, {len(ds4_controllers)} DualShock 4\n")
print("=" * 70)

# Test Joy-Cons (SIN LECTURAS SPI)
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
        
        print("📡 Conectado (modo ligero - sin lecturas SPI)")
        
        # 1. BATERÍA RÁPIDA (solo input reports)
        print("\n🔋 Leyendo batería (sin SPI)...")
        battery, charging = get_quick_battery_joycon(device)
        
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
        else:
            print(f"   ⚠️ No se pudo leer batería")
        
        # 2. POLLING RATE (sin lecturas previas que afecten)
        print("\n📊 Midiendo tasa de sondeo...")
        print("   💡 Mueve el Joy-Con para mantenerlo activo...")
        print("   ⏱️  Capturando paquetes durante 2 segundos...")
        
        polling_hz, polling_ms, packets = measure_polling_rate(device, duration_seconds=2.0)
        
        if packets > 0:
            print(f"   📈 Paquetes recibidos: {packets}")
            print(f"   ⚡ Polling Rate: {polling_hz:.1f} Hz")
            print(f"   ⏱️  Intervalo: {polling_ms:.2f} ms")
            
            # Comparar con lo esperado
            if polling_hz >= 100:
                print(f"   ✅ EXCELENTE - Tasa normal (~120 Hz)")
            elif polling_hz >= 50:
                print(f"   ⚠️  MODERADO - Tasa reducida")
            else:
                print(f"   ❌ BAJO - Dispositivo en modo bajo consumo")
        else:
            print(f"   ⚠️ No se recibieron paquetes (sleep mode)")
        
        device.close()
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        try:
            device.close()
        except:
            pass

# Test DualShock 4
for idx, ds4_info in enumerate(ds4_controllers):
    product_name = ds4_info['product_string']
    device_path = ds4_info['path']
    
    print(f"\n🎮 DualShock 4 - {product_name}")
    print("-" * 70)
    
    try:
        device = hid.device()
        device.open_path(device_path)
        
        print("📡 Conectado (modo ligero)")
        time.sleep(0.1)
        
        # 1. BATERÍA
        print("\n🔋 Leyendo batería...")
        battery, charging, connection_type = get_quick_battery_ds4(device)
        
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
            print(f"   ⚠️ No se pudo leer batería")
        
        # 2. POLLING RATE
        print("\n📊 Midiendo tasa de sondeo...")
        print("   💡 Mueve el control para mantenerlo activo...")
        print("   ⏱️  Capturando paquetes durante 2 segundos...")
        
        polling_hz, polling_ms, packets = measure_polling_rate(device, duration_seconds=2.0)
        
        if packets > 0:
            print(f"   📈 Paquetes recibidos: {packets}")
            print(f"   ⚡ Polling Rate: {polling_hz:.1f} Hz")
            print(f"   ⏱️  Intervalo: {polling_ms:.2f} ms")
            
            # DS4 esperado: ~250Hz BT, ~125Hz USB
            if connection_type == "BT" and polling_hz >= 180:
                print(f"   ✅ EXCELENTE - Tasa BT normal (~250 Hz)")
            elif connection_type == "USB" and polling_hz >= 100:
                print(f"   ✅ EXCELENTE - Tasa USB normal (~125 Hz)")
            elif polling_hz >= 50:
                print(f"   ⚠️  MODERADO - Tasa reducida")
            else:
                print(f"   ❌ BAJO - Dispositivo inactivo")
        else:
            print(f"   ⚠️ No se recibieron paquetes")
        
        device.close()
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        try:
            device.close()
        except:
            pass

print("\n" + "=" * 70)
print("📊 RESUMEN DEL TEST LIGERO")
print("=" * 70)
print("\n✅ TEST COMPLETADO SIN LECTURAS SPI")
print("   • Solo lectura de input reports (batería)")
print("   • Medición de polling rate sin interferencias")
print("   • Sin comandos subcomando (sin SPI)")
print("\n💡 PROPÓSITO:")
print("   Verificar si las lecturas SPI intensivas causan:")
print("   1. Conflictos de recursos (Código 10)")
print("   2. Reducción de polling rate")
print("   3. Modo bajo consumo forzado")
print("\n📈 COMPARACIÓN:")
print("   • Joy-Con esperado: ~120 Hz")
print("   • DS4 BT esperado: ~250 Hz")
print("   • DS4 USB esperado: ~125 Hz")
print("=" * 70)
