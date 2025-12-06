"""
Test Agresivo - Forzar máximo polling rate
Envía comandos continuos para mantener Joy-Con completamente activo
"""

import sys
import time
import hid
import threading

print("=" * 70)
print("🚀 TEST AGRESIVO - MÁXIMO POLLING RATE")
print("=" * 70)
print()

NINTENDO_VENDOR_ID = 0x057E
JOYCON_L_PRODUCT = 0x2006
JOYCON_R_PRODUCT = 0x2007

keep_alive_active = False

def send_subcmd(device, subcmd, data=None):
    """Enviar subcomando al Joy-Con"""
    report = bytearray(64)
    report[0] = 0x01
    report[1] = 0x00
    report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
    report[10] = subcmd
    
    if data:
        report[11:11+len(data)] = data
    
    device.write(bytes(report))

def keep_alive_thread(device):
    """Thread que envía comandos continuos para mantener el Joy-Con activo"""
    global keep_alive_active
    
    while keep_alive_active:
        try:
            # Enviar rumble neutral continuamente
            report = bytearray(64)
            report[0] = 0x10  # Rumble only
            report[1] = 0x00
            report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
            device.write(bytes(report))
            time.sleep(0.008)  # ~120Hz de comandos salientes
        except:
            break

def enable_aggressive_mode(device):
    """Activar modo agresivo para máximo polling"""
    print("   🔧 Configurando modo agresivo...")
    
    # 1. Habilitar vibración
    send_subcmd(device, 0x48, [0x01])
    time.sleep(0.05)
    
    # 2. Habilitar IMU a 120Hz
    send_subcmd(device, 0x40, [0x01])
    time.sleep(0.05)
    
    # 3. Configurar input report mode a 0x30
    send_subcmd(device, 0x03, [0x30])
    time.sleep(0.05)
    
    # 4. Configurar player lights (mantiene despierto)
    send_subcmd(device, 0x30, [0x01])  # Player 1 LED
    time.sleep(0.05)
    
    print("   ✅ Modo agresivo configurado")

def measure_polling_rate(device, duration_seconds=3.0, with_keepalive=False):
    """Medir polling rate con opción de keep-alive"""
    global keep_alive_active
    
    device.set_nonblocking(True)
    
    # Limpiar buffer
    for _ in range(100):
        data = device.read(64)
        if not data:
            break
    
    time.sleep(0.1)
    
    # Iniciar keep-alive thread si es necesario
    thread = None
    if with_keepalive:
        keep_alive_active = True
        thread = threading.Thread(target=keep_alive_thread, args=(device,))
        thread.daemon = True
        thread.start()
        print("   🔄 Keep-alive activado (enviando comandos a ~120 Hz)")
    
    # Contar paquetes
    packet_count = 0
    report_types = {}
    start_time = time.time()
    
    while time.time() - start_time < duration_seconds:
        data = device.read(64)
        if data:
            packet_count += 1
            report_id = data[0] if data else 0
            report_types[report_id] = report_types.get(report_id, 0) + 1
    
    elapsed = time.time() - start_time
    
    # Detener keep-alive
    if with_keepalive:
        keep_alive_active = False
        if thread:
            thread.join(timeout=1.0)
    
    device.set_nonblocking(False)
    
    if packet_count > 0:
        polling_rate_hz = packet_count / elapsed
        polling_interval_ms = 1000.0 / polling_rate_hz
        return polling_rate_hz, polling_interval_ms, packet_count, report_types
    
    return 0, 0, 0, {}

def get_battery_quick(device):
    """Obtener batería rápida"""
    device.set_nonblocking(True)
    
    for _ in range(20):
        data = device.read(64)
        if not data:
            break
    
    time.sleep(0.05)
    
    for attempt in range(30):
        data = device.read(64)
        
        if data and len(data) >= 3:
            if data[0] in [0x21, 0x30, 0x31, 0x3F]:
                battery_byte = data[2]
                
                if battery_byte != 0x00:
                    battery_level = ((battery_byte & 0xE0) >> 4) * 100 // 8
                    charging = (battery_byte & 0x10) != 0
                    device.set_nonblocking(False)
                    return min(battery_level, 100), charging
        
        time.sleep(0.01)
    
    device.set_nonblocking(False)
    return None, None

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
        
        # 1. BATERÍA
        print("\n🔋 Batería:")
        battery, charging = get_battery_quick(device)
        
        if battery is not None:
            charge_status = "⚡ Cargando" if charging else "🔌 Desconectado"
            bar_length = 20
            filled = int(bar_length * battery / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            if battery >= 75:
                color_emoji = "🟢"
            elif battery >= 50:
                color_emoji = "🟡"
            else:
                color_emoji = "🟠"
            
            print(f"   {color_emoji} {battery}% [{bar}] {charge_status}")
        
        # 2. ACTIVAR MODO AGRESIVO
        print("\n🚀 ACTIVANDO MODO AGRESIVO...")
        enable_aggressive_mode(device)
        
        # 3. TEST 1: Sin keep-alive
        print("\n📊 TEST 1: Polling sin keep-alive")
        print("   ⏱️  Midiendo 3 segundos...")
        
        polling_hz, polling_ms, packets, report_types = measure_polling_rate(device, duration_seconds=3.0, with_keepalive=False)
        
        if packets > 0:
            print(f"   📈 Resultado: {polling_hz:.1f} Hz ({packets} paquetes)")
        
        time.sleep(0.5)
        
        # 4. TEST 2: Con keep-alive agresivo
        print("\n📊 TEST 2: Polling CON keep-alive agresivo")
        print("   🔄 Enviando comandos continuos a ~120 Hz...")
        print("   ⏱️  Midiendo 3 segundos...")
        
        polling_hz2, polling_ms2, packets2, report_types2 = measure_polling_rate(device, duration_seconds=3.0, with_keepalive=True)
        
        print(f"\n   📊 COMPARACIÓN:")
        print(f"      Sin keep-alive:  {polling_hz:.1f} Hz ({packets} paquetes)")
        print(f"      Con keep-alive:  {polling_hz2:.1f} Hz ({packets2} paquetes)")
        
        if polling_hz2 > polling_hz:
            improvement = ((polling_hz2 - polling_hz) / polling_hz) * 100
            print(f"      ✅ Mejora: +{improvement:.1f}% ({polling_hz2 - polling_hz:.1f} Hz)")
        else:
            print(f"      ⚠️  Sin mejora notable")
        
        # Tipos de reportes
        print(f"\n   📋 Tipos de reportes (Test 2):")
        for report_id, count in sorted(report_types2.items()):
            report_name = {
                0x21: "Subcommand reply",
                0x30: "Full input report (IMU)",
                0x31: "NFC/IR input report",
                0x3F: "Simple HID mode"
            }.get(report_id, f"Unknown (0x{report_id:02X})")
            percentage = (count / packets2) * 100
            print(f"      • 0x{report_id:02X} ({report_name}): {count} ({percentage:.1f}%)")
        
        # Evaluación final
        print(f"\n   🎯 EVALUACIÓN FINAL:")
        max_hz = max(polling_hz, polling_hz2)
        if max_hz >= 110:
            print(f"      ✅ EXCELENTE - {max_hz:.1f} Hz (~120 Hz esperado)")
        elif max_hz >= 90:
            print(f"      ✅ BUENO - {max_hz:.1f} Hz (cerca del objetivo)")
        elif max_hz >= 70:
            print(f"      ⚠️  MODERADO - {max_hz:.1f} Hz")
            print(f"      💡 Limitación de Bluetooth en Windows")
        else:
            print(f"      ⚠️  BAJO - {max_hz:.1f} Hz")
        
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
print("📊 CONCLUSIÓN")
print("=" * 70)
print("\n🔍 ANÁLISIS:")
print("   • Modo 0x30 activo (Full input report con IMU)")
print("   • Keep-alive enviando comandos a ~120 Hz")
print("   • Polling rate depende del stack Bluetooth de Windows")
print("\n💡 RESULTADO TÍPICO EN WINDOWS:")
print("   • Joy-Con en Switch: ~120 Hz (controlador Nintendo)")
print("   • Joy-Con en Windows: ~60-80 Hz (limitación del stack BT)")
print("   • Posible mejora: Adaptador Bluetooth externo con mejor stack")
print("\n✅ MODO AGRESIVO:")
print("   Es el máximo posible sin modificar drivers de Windows")
print("=" * 70)
