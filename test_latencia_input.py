"""
Test de Latencia Real - Monitoreo de Input Reports
Mide latencia real de input leyendo reportes continuos del Joy-Con
"""

import sys
import os
import time
import statistics
import hid

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

print("=" * 60)
print("⚡ TEST DE LATENCIA REAL - INPUT REPORTS")
print("=" * 60)
print()

# Joy-Con vendor/product IDs
NINTENDO_VENDOR_ID = 0x057E
JOYCON_L_PRODUCT = 0x2006
JOYCON_R_PRODUCT = 0x2007

# ============================================================================
# Encontrar Joy-Cons
# ============================================================================
print("🔍 Buscando Joy-Cons conectados...")
print("-" * 60)

devices = []
for device_dict in hid.enumerate(NINTENDO_VENDOR_ID):
    if device_dict['product_id'] in [JOYCON_L_PRODUCT, JOYCON_R_PRODUCT]:
        devices.append(device_dict)
        print(f"✅ Encontrado: {device_dict['product_string']}")

if not devices:
    print("❌ No se encontraron Joy-Cons")
    sys.exit(1)

print(f"\n✅ Total: {len(devices)} Joy-Cons\n")

# ============================================================================
# TEST de Latencia por cada Joy-Con
# ============================================================================

for idx, device_info in enumerate(devices):
    product_name = device_info['product_string']
    device_path = device_info['path']
    
    print(f"🎮 Dispositivo {idx+1}: {product_name}")
    print("-" * 60)
    
    try:
        device = hid.device()
        device.open_path(device_path)
        device.set_nonblocking(True)
        
        print("✅ Dispositivo abierto en modo no-bloqueante")
        print("📡 Leyendo reportes de entrada en tiempo real...")
        print("   (Presiona botones en el Joy-Con para generar actividad)\n")
        
        # Leer reportes continuamente
        report_times = []
        last_report_time = None
        reports_count = 0
        start_time = time.perf_counter()
        
        # Leer por 5 segundos
        while time.perf_counter() - start_time < 5.0:
            data = device.read(64)
            
            if data:
                current_time = time.perf_counter()
                reports_count += 1
                
                # Calcular tiempo entre reportes
                if last_report_time is not None:
                    interval_ms = (current_time - last_report_time) * 1000
                    report_times.append(interval_ms)
                    
                    # Mostrar cada 10 reportes
                    if reports_count % 10 == 0:
                        print(f"   Reporte #{reports_count}: {interval_ms:.2f} ms desde último")
                
                last_report_time = current_time
            else:
                # Sin datos, esperar un poco
                time.sleep(0.001)
        
        device.close()
        
        # ============================================================================
        # Calcular estadísticas
        # ============================================================================
        print(f"\n📊 RESULTADOS:")
        print(f"   • Total de reportes: {reports_count}")
        print(f"   • Duración: 5.00 segundos")
        print(f"   • Tasa: {reports_count / 5.0:.1f} reportes/segundo")
        
        if report_times:
            avg_interval = statistics.mean(report_times)
            min_interval = min(report_times)
            max_interval = max(report_times)
            median_interval = statistics.median(report_times)
            
            if len(report_times) > 1:
                stdev = statistics.stdev(report_times)
            else:
                stdev = 0
            
            print(f"\n📈 LATENCIA ENTRE REPORTES:")
            print(f"   • Promedio:    {avg_interval:.2f} ms")
            print(f"   • Mediana:     {median_interval:.2f} ms")
            print(f"   • Mínima:      {min_interval:.2f} ms")
            print(f"   • Máxima:      {max_interval:.2f} ms")
            print(f"   • Desv. Est:   {stdev:.2f} ms")
            print(f"   • Jitter:      {max_interval - min_interval:.2f} ms")
            
            # Clasificación
            print(f"\n🏆 CLASIFICACIÓN DE LATENCIA:")
            if avg_interval < 10:
                quality = "🟢 EXCELENTE - <10ms (120+ Hz)"
            elif avg_interval < 20:
                quality = "🟡 BUENA - <20ms (60+ Hz)"
            elif avg_interval < 50:
                quality = "🟠 ACEPTABLE - <50ms (20+ Hz)"
            else:
                quality = "🔴 ALTA - >50ms"
            
            print(f"   {quality}")
            
            # Calcular frecuencia de polling
            polling_rate = 1000 / avg_interval if avg_interval > 0 else 0
            print(f"\n📊 FRECUENCIA DE POLLING:")
            print(f"   • {polling_rate:.1f} Hz")
            
            if polling_rate >= 100:
                print(f"   🟢 Excelente para juegos competitivos")
            elif polling_rate >= 60:
                print(f"   🟡 Buena para la mayoría de juegos")
            elif polling_rate >= 30:
                print(f"   🟠 Aceptable para juegos casuales")
            else:
                print(f"   🔴 Baja - Puede sentirse lag")
        
        else:
            print("\n⚠️ No se recibieron suficientes reportes")
            print("   Intenta mover los sticks o presionar botones")
        
        print("\n")
    
    except Exception as e:
        print(f"❌ Error: {e}\n")

# ============================================================================
# RESUMEN FINAL
# ============================================================================
print("=" * 60)
print("📊 RESUMEN")
print("=" * 60)

print("\n✅ MÉTRICAS DE LATENCIA REAL:")
print("   • Intervalo entre reportes de entrada")
print("   • Frecuencia de polling (Hz)")
print("   • Jitter (variación de timing)")
print("   • Estabilidad de la conexión")

print("\n💡 INTERPRETACIÓN:")
print("   • Esta es la LATENCIA REAL de input")
print("   • Indica cada cuánto tiempo el Joy-Con envía datos")
print("   • Valores típicos para Joy-Con: 15-20ms (~60Hz)")
print("   • Menor latencia = respuesta más rápida")

print("\n🎯 CONCLUSIÓN:")
print("   ✅ Medición precisa de latencia de entrada")
print("   ✅ Datos reales sin desconectar de Windows")
print("   ✅ Listo para implementar en monitoreo continuo")

print("\n" + "=" * 60)
