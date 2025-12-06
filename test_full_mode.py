"""
Test con Full Input Report Mode (0x30)
Activa el modo completo para obtener ~120 Hz
"""

import sys
import time
import hid

print("=" * 70)
print("⚡ TEST - FULL INPUT REPORT MODE (120 Hz)")
print("=" * 70)
print()

# Device IDs
NINTENDO_VENDOR_ID = 0x057E
JOYCON_L_PRODUCT = 0x2006
JOYCON_R_PRODUCT = 0x2007

def send_subcmd(device, subcmd, data=None):
    """Enviar subcomando al Joy-Con"""
    report = bytearray(64)
    report[0] = 0x01  # Output report ID
    report[1] = 0x00  # Packet counter
    # Rumble data (neutral)
    report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
    report[10] = subcmd  # Subcommand
    
    if data:
        report[11:11+len(data)] = data
    
    device.write(bytes(report))
    time.sleep(0.05)

def enable_full_mode(device):
    """Activar Full Input Report Mode (0x30) para máximo polling rate"""
    print("   🔧 Activando Full Input Report Mode...")
    
    # 1. Habilitar vibración
    send_subcmd(device, 0x48, [0x01])
    print("   ✅ Vibración habilitada")
    
    # 2. Habilitar IMU (necesario para modo 0x30)
    send_subcmd(device, 0x40, [0x01])
    print("   ✅ IMU habilitado")
    
    # 3. Configurar input report mode a 0x30 (Full mode)
    send_subcmd(device, 0x03, [0x30])
    print("   ✅ Input Report Mode configurado a 0x30")
    
    # 4. Enviar comando de "keep alive" para mantener activo
    send_subcmd(device, 0x48, [0x01])
    
    time.sleep(0.1)
    print("   ⚡ Modo completo activado - esperando ~120 Hz")

def measure_polling_rate(device, duration_seconds=3.0):
    """Medir la tasa de sondeo"""
    device.set_nonblocking(True)
    
    # Limpiar buffer
    for _ in range(100):
        data = device.read(64)
        if not data:
            break
    
    time.sleep(0.1)
    
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
        print("\n🔋 Leyendo batería...")
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
            elif battery >= 25:
                color_emoji = "🟠"
            else:
                color_emoji = "🔴"
            
            print(f"   {color_emoji} Batería: {battery}% [{bar}] {charge_status}")
        
        # 2. ACTIVAR MODO COMPLETO
        print("\n⚡ ACTIVANDO MODO COMPLETO (0x30)...")
        enable_full_mode(device)
        
        # 3. POLLING RATE ANTES
        print("\n📊 Midiendo polling rate EN MODO COMPLETO...")
        print("   💡 Mueve el Joy-Con para mantenerlo activo...")
        print("   ⏱️  Capturando paquetes durante 3 segundos...")
        
        polling_hz, polling_ms, packets, report_types = measure_polling_rate(device, duration_seconds=3.0)
        
        if packets > 0:
            print(f"\n   📈 RESULTADOS:")
            print(f"      • Paquetes recibidos: {packets}")
            print(f"      • Polling Rate: {polling_hz:.1f} Hz")
            print(f"      • Intervalo: {polling_ms:.2f} ms")
            
            # Mostrar tipos de reportes
            print(f"\n   📋 Tipos de reportes recibidos:")
            for report_id, count in sorted(report_types.items()):
                report_name = {
                    0x21: "Subcommand reply",
                    0x30: "Full input report (IMU)",
                    0x31: "NFC/IR input report",
                    0x3F: "Simple HID mode"
                }.get(report_id, f"Unknown (0x{report_id:02X})")
                percentage = (count / packets) * 100
                print(f"      • 0x{report_id:02X} ({report_name}): {count} ({percentage:.1f}%)")
            
            # Evaluación
            print(f"\n   🎯 EVALUACIÓN:")
            if 0x30 in report_types and polling_hz >= 100:
                print(f"      ✅ EXCELENTE - Modo 0x30 activo con {polling_hz:.1f} Hz")
                print(f"      ✅ Joy-Con funcionando a velocidad máxima")
            elif 0x30 in report_types and polling_hz >= 60:
                print(f"      ⚠️  MODERADO - Modo 0x30 activo pero a {polling_hz:.1f} Hz")
                print(f"      💡 Mueve más el Joy-Con para activar frecuencia máxima")
            elif polling_hz >= 100:
                print(f"      ✅ BUENO - {polling_hz:.1f} Hz alcanzado")
            else:
                print(f"      ⚠️  BAJO - Solo {polling_hz:.1f} Hz")
                print(f"      💡 Intenta mover el Joy-Con durante la medición")
        else:
            print(f"   ⚠️ No se recibieron paquetes")
        
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
print("📊 RESUMEN - MODO COMPLETO")
print("=" * 70)
print("\n✅ CONFIGURACIÓN APLICADA:")
print("   • Vibración habilitada (subcmd 0x48)")
print("   • IMU habilitado (subcmd 0x40)")
print("   • Input Report Mode 0x30 (subcmd 0x03)")
print("\n📈 POLLING RATE ESPERADO:")
print("   • Modo estándar (0x3F): ~60-70 Hz")
print("   • Modo completo (0x30): ~120 Hz")
print("\n💡 NOTA:")
print("   El modo 0x30 incluye datos del IMU (acelerómetro + giroscopio)")
print("   Esto permite detectar movimiento y orientación en tiempo real")
print("=" * 70)
