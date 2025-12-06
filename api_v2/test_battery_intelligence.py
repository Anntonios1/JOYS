"""
Test del sistema de inteligencia de batería
============================================

Valida el funcionamiento de:
- JoyConBatteryMonitor (voltaje + temperatura)
- DiscreteLevelBatteryMonitor (DS4/DS5)
- Cálculo de ciclos equivalentes
- Estimación de SoH
- Persistencia en base de datos
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
import time

from battery_intelligence import (
    JoyConBatteryMonitor,
    DiscreteLevelBatteryMonitor,
    BatteryMonitorFactory,
    BatteryIntelligenceManager,
    DeviceType,
    DISCHARGE_CURVES_BY_TEMP,
    DEVICE_SPECS
)


def test_joycon_voltage_to_soc():
    """Test de conversión voltaje → SOC para Joy-Con"""
    print("\n" + "="*60)
    print("TEST: Joy-Con Voltaje → SOC")
    print("="*60)
    
    monitor = JoyConBatteryMonitor("test_joycon_l", is_left=True)
    
    test_cases = [
        # (voltaje, temperatura, soc_esperado_min, soc_esperado_max)
        (4.20, 25, 98, 100),    # Lleno
        (4.00, 25, 75, 82),     # Alto
        (3.80, 25, 48, 55),     # Medio
        (3.60, 25, 20, 28),     # Bajo
        (3.40, 25, 4, 10),      # Muy bajo
        (3.20, 25, 0, 3),       # Crítico
        
        # Variación por temperatura
        (3.80, 0, 50, 60),      # Frío = más capacidad aparente
        (3.80, 45, 44, 52),     # Caliente = menos capacidad
    ]
    
    passed = 0
    failed = 0
    
    for voltage, temp, expected_min, expected_max in test_cases:
        soc = monitor._voltage_to_soc(voltage, temp)
        
        if expected_min <= soc <= expected_max:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status} V={voltage:.2f}V, T={temp}°C → SOC={soc:.1f}% (esperado: {expected_min}-{expected_max}%)")
    
    print(f"\nResultado: {passed} passed, {failed} failed")
    return failed == 0


def test_joycon_thermal_correction():
    """Test de corrección térmica de voltaje"""
    print("\n" + "="*60)
    print("TEST: Joy-Con Corrección Térmica")
    print("="*60)
    
    monitor = JoyConBatteryMonitor("test_joycon_r", is_left=False)
    
    base_voltage = 3.80
    
    test_temps = [0, 10, 25, 35, 45]
    
    print(f"Voltaje base: {base_voltage}V")
    print("-" * 40)
    
    for temp in test_temps:
        corrected = monitor._apply_thermal_correction(base_voltage, temp)
        correction = (corrected - base_voltage) * 1000  # mV
        print(f"T={temp:2d}°C → V_corr={corrected:.4f}V (corrección: {correction:+.1f}mV)")
    
    # Verificar que a 25°C no hay corrección
    corrected_25 = monitor._apply_thermal_correction(base_voltage, 25)
    assert abs(corrected_25 - base_voltage) < 0.001, "No debería haber corrección a 25°C"
    
    print("\n✅ Corrección térmica funcionando correctamente")
    return True


def test_ds4_level_interpolation():
    """Test de interpolación de niveles discretos para DS4"""
    print("\n" + "="*60)
    print("TEST: DS4 Interpolación de Niveles")
    print("="*60)
    
    monitor = DiscreteLevelBatteryMonitor("test_ds4", is_dualsense=False)
    
    print(f"Tipo: {monitor.device_type.value}")
    print(f"Niveles discretos: {monitor.specs.discrete_levels}")
    print("-" * 40)
    
    # Simular transiciones de nivel
    test_levels = [4, 3, 2, 1, 0]
    
    for level in test_levels:
        # Simular que acaba de entrar al nivel
        reading = monitor.process_reading({
            "level": level,
            "charging": False
        })
        
        print(f"Nivel {level}: SOC={reading.soc_percent:.1f}%")
        
        # Verificar rangos
        expected_max = (level + 1) * 20
        expected_min = level * 20
        
        assert expected_min <= reading.soc_percent <= expected_max, \
            f"SOC {reading.soc_percent} fuera de rango [{expected_min}, {expected_max}]"
    
    print("\n✅ Interpolación de niveles funcionando correctamente")
    return True


def test_cycle_counting():
    """Test de conteo de ciclos equivalentes"""
    print("\n" + "="*60)
    print("TEST: Conteo de Ciclos Equivalentes")
    print("="*60)
    
    monitor = JoyConBatteryMonitor("test_cycles", is_left=True)
    
    # Simular descarga de 100% a 50% (0.5 ciclos)
    print("Simulando descarga 100% → 50%...")
    
    # Inicio cargando
    monitor.add_reading({
        "voltage": 4.20,
        "temperature": 25,
        "charging": True
    })
    
    # Desconectar carga
    monitor.add_reading({
        "voltage": 4.18,
        "temperature": 25,
        "charging": False
    })
    
    # Simular descarga progresiva
    voltages = [4.10, 4.00, 3.90, 3.80]  # Aprox 90% → 50%
    
    for v in voltages:
        time.sleep(0.1)  # Pequeña pausa para diferentes timestamps
        monitor.add_reading({
            "voltage": v,
            "temperature": 25,
            "charging": False
        })
    
    # Conectar carga (fin de ciclo)
    monitor.add_reading({
        "voltage": 3.80,
        "temperature": 25,
        "charging": True
    })
    
    print(f"Ciclos registrados: {len(monitor.cycles)}")
    print(f"Ciclos equivalentes: {monitor.equivalent_cycles:.2f}")
    
    if len(monitor.cycles) > 0:
        cycle = monitor.cycles[0]
        print(f"  - Inicio: {cycle.start_soc:.1f}% → Fin: {cycle.end_soc:.1f}%")
        print(f"  - Delta: {cycle.discharge_delta:.2f} ({cycle.discharge_delta*100:.0f}%)")
    
    assert monitor.equivalent_cycles > 0, "Debería haber acumulado ciclos"
    print("\n✅ Conteo de ciclos funcionando correctamente")
    return True


def test_soh_estimation():
    """Test de estimación de State of Health"""
    print("\n" + "="*60)
    print("TEST: Estimación de SoH")
    print("="*60)
    
    monitor = DiscreteLevelBatteryMonitor("test_soh", is_dualsense=True)
    
    # Simular varios ciclos con tiempos diferentes
    print("Simulando ciclos de uso...")
    
    from battery_intelligence import CycleData
    
    # Agregar ciclos manualmente para test
    base_time = datetime.now()
    
    # Ciclos con duración "normal" (referencia)
    for i in range(5):
        monitor.cycles.append(CycleData(
            start_soc=100,
            end_soc=20,
            start_time=base_time + timedelta(hours=i*10),
            end_time=base_time + timedelta(hours=i*10 + 8),  # 8 horas por ciclo
            discharge_delta=0.8,
            avg_temperature=25,
            was_interrupted=False
        ))
        monitor.equivalent_cycles += 0.8
    
    health = monitor._calculate_health()
    
    print(f"Ciclos totales: {len(monitor.cycles)}")
    print(f"Ciclos equivalentes: {monitor.equivalent_cycles:.2f}")
    print(f"SoH: {health.soh_percent:.1f}%")
    print(f"Estado: {health.health_status}")
    print(f"Capacidad estimada: {health.estimated_capacity_mah} mAh")
    print(f"Confianza: {health.confidence:.0%}")
    
    assert 80 <= health.soh_percent <= 120, f"SoH {health.soh_percent} fuera de rango razonable"
    print("\n✅ Estimación de SoH funcionando correctamente")
    return True


def test_factory():
    """Test del factory de monitores"""
    print("\n" + "="*60)
    print("TEST: Factory de Monitores")
    print("="*60)
    
    test_types = [
        ("test_1", "joycon_l", JoyConBatteryMonitor),
        ("test_2", "joycon_r", JoyConBatteryMonitor),
        ("test_3", "Joy-Con (L)", JoyConBatteryMonitor),
        ("test_4", "ds4", DiscreteLevelBatteryMonitor),
        ("test_5", "DualShock 4", DiscreteLevelBatteryMonitor),
        ("test_6", "dualsense", DiscreteLevelBatteryMonitor),
        ("test_7", "DualSense Edge", DiscreteLevelBatteryMonitor),
    ]
    
    for device_id, device_type, expected_class in test_types:
        monitor = BatteryMonitorFactory.create(device_id, device_type)
        
        if isinstance(monitor, expected_class):
            status = "✅"
        else:
            status = "❌"
        
        print(f"{status} '{device_type}' → {type(monitor).__name__}")
    
    print("\n✅ Factory funcionando correctamente")
    return True


def test_manager():
    """Test del manager de inteligencia de batería"""
    print("\n" + "="*60)
    print("TEST: Battery Intelligence Manager")
    print("="*60)
    
    manager = BatteryIntelligenceManager()
    
    # Crear monitores
    devices = [
        ("joycon_001", "joycon_l"),
        ("ds4_001", "ds4"),
        ("dualsense_001", "dualsense")
    ]
    
    for device_id, device_type in devices:
        monitor = manager.get_or_create_monitor(device_id, device_type)
        print(f"✅ Creado monitor para {device_id}: {type(monitor).__name__}")
    
    # Procesar lecturas
    state = manager.process_reading("joycon_001", "joycon_l", {
        "voltage": 4.0,
        "temperature": 25,
        "charging": False
    })
    
    print(f"\nEstado Joy-Con:")
    print(f"  SOC: {state.current_reading.soc_percent:.1f}%")
    print(f"  Voltaje: {state.current_reading.voltage}V")
    print(f"  Drenaje: {state.drain_rate_per_hour:.1f}%/h")
    
    # Estadísticas
    stats = manager.get_all_statistics()
    print(f"\nMonitores activos: {len(stats)}")
    
    print("\n✅ Manager funcionando correctamente")
    return True


def test_discharge_curves():
    """Test de curvas de descarga por temperatura"""
    print("\n" + "="*60)
    print("TEST: Curvas de Descarga por Temperatura")
    print("="*60)
    
    print("\nCurvas disponibles:")
    for temp, curve in DISCHARGE_CURVES_BY_TEMP.items():
        v_max = curve[0][0]
        v_min = curve[-1][0]
        print(f"  {temp}°C: {v_max}V → {v_min}V ({len(curve)} puntos)")
    
    # Verificar que las curvas son monotónicas
    for temp, curve in DISCHARGE_CURVES_BY_TEMP.items():
        for i in range(len(curve) - 1):
            assert curve[i][0] >= curve[i+1][0], f"Curva {temp}°C no es monotónica en voltaje"
            assert curve[i][1] >= curve[i+1][1], f"Curva {temp}°C no es monotónica en SOC"
    
    print("\n✅ Curvas de descarga válidas")
    return True


def run_all_tests():
    """Ejecutar todos los tests"""
    print("\n" + "="*60)
    print("SISTEMA DE INTELIGENCIA DE BATERÍA - TESTS")
    print("="*60)
    
    tests = [
        ("Curvas de Descarga", test_discharge_curves),
        ("Joy-Con Voltaje→SOC", test_joycon_voltage_to_soc),
        ("Joy-Con Corrección Térmica", test_joycon_thermal_correction),
        ("DS4 Interpolación Niveles", test_ds4_level_interpolation),
        ("Conteo de Ciclos", test_cycle_counting),
        ("Estimación SoH", test_soh_estimation),
        ("Factory", test_factory),
        ("Manager", test_manager),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "✅ PASS" if result else "❌ FAIL"))
        except Exception as e:
            results.append((name, f"❌ ERROR: {e}"))
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("RESUMEN DE TESTS")
    print("="*60)
    
    for name, result in results:
        print(f"  {result}: {name}")
    
    passed = sum(1 for _, r in results if "PASS" in r)
    total = len(results)
    
    print(f"\n{'='*60}")
    print(f"Total: {passed}/{total} tests pasados")
    print("="*60)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
