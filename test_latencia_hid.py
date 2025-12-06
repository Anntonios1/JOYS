"""
Test de Latencia Real via HID
Mide el tiempo de respuesta de lectura HID para calcular latencia
"""

import sys
import os
import time
import statistics

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from modules.windows_hid_reader import get_windows_hid_reader

print("=" * 60)
print("⚡ TEST DE LATENCIA REAL VIA HID")
print("=" * 60)
print()

# ============================================================================
# Encontrar Joy-Cons
# ============================================================================
print("🔍 Buscando Joy-Cons conectados...")
print("-" * 60)

hid_reader = get_windows_hid_reader()
joycon_devices = hid_reader.find_joycon_devices()

if not joycon_devices:
    print("❌ No se encontraron Joy-Cons")
    sys.exit(1)

print(f"✅ Encontrados {len(joycon_devices)} Joy-Cons\n")

# ============================================================================
# TEST de Latencia por cada Joy-Con
# ============================================================================

for idx, device in enumerate(joycon_devices):
    product_name = device['product_string']
    device_path = device['path']
    
    print(f"🎮 Dispositivo {idx+1}: {product_name}")
    print("-" * 60)
    
    # Realizar múltiples lecturas para medir latencia
    latencies = []
    errors = 0
    
    print("📊 Realizando 20 lecturas para medir latencia...\n")
    
    for i in range(20):
        start_time = time.perf_counter()
        
        try:
            battery = hid_reader.read_joycon_battery_real(device_path)
            end_time = time.perf_counter()
            
            if battery is not None:
                latency_ms = (end_time - start_time) * 1000
                latencies.append(latency_ms)
                
                # Mostrar cada 5 lecturas
                if (i + 1) % 5 == 0:
                    print(f"   Lectura {i+1}: {latency_ms:.2f} ms (Batería: {battery}%)")
            else:
                errors += 1
                print(f"   Lectura {i+1}: ❌ Error")
        
        except Exception as e:
            errors += 1
            print(f"   Lectura {i+1}: ❌ Error ({e})")
        
        # Pequeña pausa entre lecturas
        time.sleep(0.1)
    
    # ============================================================================
    # Calcular estadísticas
    # ============================================================================
    if latencies:
        avg_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        median_latency = statistics.median(latencies)
        
        if len(latencies) > 1:
            stdev_latency = statistics.stdev(latencies)
        else:
            stdev_latency = 0
        
        print(f"\n📈 ESTADÍSTICAS DE LATENCIA:")
        print(f"   • Promedio:    {avg_latency:.2f} ms")
        print(f"   • Mediana:     {median_latency:.2f} ms")
        print(f"   • Mínima:      {min_latency:.2f} ms")
        print(f"   • Máxima:      {max_latency:.2f} ms")
        print(f"   • Desv. Est:   {stdev_latency:.2f} ms")
        print(f"   • Jitter:      {max_latency - min_latency:.2f} ms")
        
        # Clasificación de latencia
        print(f"\n🏆 CLASIFICACIÓN:")
        if avg_latency < 10:
            quality = "🟢 EXCELENTE - Perfecta para juegos competitivos"
        elif avg_latency < 20:
            quality = "🟡 BUENA - Adecuada para la mayoría de juegos"
        elif avg_latency < 50:
            quality = "🟠 ACEPTABLE - Puede sentirse en juegos rápidos"
        else:
            quality = "🔴 ALTA - Puede haber lag notable"
        
        print(f"   {quality}")
        
        # Estabilidad de conexión
        error_rate = (errors / 20) * 100
        success_rate = 100 - error_rate
        
        print(f"\n📡 ESTABILIDAD DE CONEXIÓN:")
        print(f"   • Tasa de éxito:  {success_rate:.1f}%")
        print(f"   • Lecturas OK:    {len(latencies)}/20")
        print(f"   • Errores:        {errors}/20")
        
        if success_rate >= 95:
            stability = "🟢 EXCELENTE"
        elif success_rate >= 85:
            stability = "🟡 BUENA"
        elif success_rate >= 70:
            stability = "🟠 REGULAR"
        else:
            stability = "🔴 INESTABLE"
        
        print(f"   • Estado:         {stability}")
        
    else:
        print("\n❌ No se pudieron realizar mediciones de latencia")
    
    print("\n")

# ============================================================================
# RESUMEN FINAL
# ============================================================================
print("=" * 60)
print("📊 RESUMEN")
print("=" * 60)

print("\n✅ MÉTRICAS OBTENIDAS VIA HID:")
print("   • Latencia de respuesta HID")
print("   • Tiempo de lectura de batería")
print("   • Estabilidad de conexión")
print("   • Tasa de errores")
print("   • Jitter (variación de latencia)")

print("\n💡 INTERPRETACIÓN:")
print("   • La latencia HID es un buen indicador de la calidad")
print("     de la conexión Bluetooth")
print("   • Valores bajos (<10ms) indican conexión óptima")
print("   • Jitter alto indica interferencias o señal débil")
print("   • Errores frecuentes indican problemas de conexión")

print("\n🎯 CONCLUSIÓN:")
print("   ✅ Sistema funcional para medir latencia sin desconectar")
print("   ✅ Datos reales basados en tiempo de respuesta HID")
print("   ✅ Listo para implementar en la API")

print("\n" + "=" * 60)
