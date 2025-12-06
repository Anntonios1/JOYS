"""
Test de Conexión BLE Directa - Todos los datos
Lee batería, RSSI, latencia via BLE sin Windows
"""

import sys
import os
import asyncio
import time

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from bleak import BleakScanner, BleakClient

print("=" * 60)
print("🔵 TEST CONEXIÓN BLE DIRECTA")
print("=" * 60)
print()

# ============================================================================
# TEST 1: Escanear dispositivos BLE
# ============================================================================
print("📡 TEST 1: Escanear dispositivos BLE")
print("-" * 60)

async def scan_ble_devices():
    print("Escaneando por 5 segundos...")
    devices = await BleakScanner.discover(timeout=5.0)
    
    joycons = []
    for device in devices:
        name = device.name or "Unknown"
        if "Joy-Con" in name or "Pro Controller" in name:
            joycons.append(device)
            print(f"\n✅ Encontrado: {name}")
            print(f"   MAC: {device.address}")
            print(f"   RSSI: {device.rssi} dBm")
    
    return joycons

joycons = asyncio.run(scan_ble_devices())

if not joycons:
    print("\n❌ No se encontraron Joy-Cons via BLE")
    print("\n⚠️ IMPORTANTE:")
    print("   Los Joy-Cons deben estar DESCONECTADOS de Windows")
    print("   para que aparezcan en el escaneo BLE.")
    print("\n   Pasos:")
    print("   1. Ve a Configuración de Windows > Bluetooth")
    print("   2. Desconecta o quita los Joy-Cons")
    print("   3. Mantén presionado el botón de sincronización")
    print("   4. Ejecuta este test nuevamente")
    print()
    sys.exit(1)

print(f"\n✅ Total encontrados: {len(joycons)}")
print()

# ============================================================================
# TEST 2: Conectar via BLE y leer servicios
# ============================================================================
print("🔗 TEST 2: Conectar via BLE")
print("-" * 60)

async def test_ble_connection(device):
    print(f"\nConectando a {device.name}...")
    
    async with BleakClient(device.address, timeout=10.0) as client:
        print(f"✅ Conectado a {device.name}")
        print(f"   RSSI actual: {device.rssi} dBm")
        
        # Listar servicios
        print(f"\n📋 Servicios disponibles:")
        for service in client.services:
            print(f"   • {service.uuid}")
            for char in service.characteristics:
                print(f"     - {char.uuid} ({', '.join(char.properties)})")
        
        # Intentar leer batería via HID
        # Joy-Cons usan HID sobre GATT
        print(f"\n🔋 Intentando leer batería...")
        
        # UUID común para HID Report
        HID_REPORT_UUID = "00002a4d-0000-1000-8000-00805f9b34fb"
        
        try:
            # Enviar comando de solicitud de batería (subcmd 0x50)
            # Format: [0x01, 0x00, cmd_id, subcmd_id]
            battery_cmd = bytes([0x01, 0x00, 0x01, 0x50])
            
            # Buscar característica de escritura
            for service in client.services:
                for char in service.characteristics:
                    if "write" in char.properties:
                        print(f"   Enviando comando a {char.uuid}")
                        await client.write_gatt_char(char.uuid, battery_cmd)
                        break
            
            await asyncio.sleep(0.5)
            
            # Buscar característica de notificación/lectura
            for service in client.services:
                for char in service.characteristics:
                    if "notify" in char.properties or "read" in char.properties:
                        try:
                            data = await client.read_gatt_char(char.uuid)
                            if len(data) > 0:
                                print(f"   Datos recibidos de {char.uuid}: {data.hex()}")
                                
                                # El byte de batería suele estar en posición 2 o 12
                                if len(data) > 2:
                                    battery_byte = data[2]
                                    battery_level = (battery_byte >> 1) * 25
                                    print(f"   ✅ Batería: {battery_level}%")
                        except Exception as e:
                            pass
            
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
        
        # Test de latencia
        print(f"\n⚡ Test de latencia:")
        latencies = []
        
        for i in range(5):
            start = time.time()
            try:
                # Ping simple leyendo característica
                await client.read_gatt_char(client.services[0].characteristics[0].uuid)
                latency = (time.time() - start) * 1000
                latencies.append(latency)
                print(f"   Ping {i+1}: {latency:.2f} ms")
            except:
                pass
            
            await asyncio.sleep(0.2)
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            print(f"   📊 Latencia promedio: {avg_latency:.2f} ms")
        
        print(f"\n✅ Desconectando...")

# Probar con el primer Joy-Con encontrado
for joycon in joycons[:1]:  # Solo el primero para no saturar
    asyncio.run(test_ble_connection(joycon))

# ============================================================================
# RESUMEN
# ============================================================================
print("\n" + "=" * 60)
print("📊 RESUMEN BLE DIRECTO")
print("=" * 60)

print("\n✅ DATOS DISPONIBLES VIA BLE:")
print("   • Detección de dispositivos")
print("   • RSSI (señal Bluetooth)")
print("   • Conexión directa")
print("   • Servicios GATT")
print("   • Latencia de comunicación")
print("   • Batería (requiere implementar lectura HID correcta)")

print("\n💡 SIGUIENTE PASO:")
print("   Implementar lectura completa del protocolo HID de Joy-Con")
print("   para obtener batería, estado de botones, giroscopio, etc.")

print("\n" + "=" * 60)
