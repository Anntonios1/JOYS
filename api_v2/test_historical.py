"""Script para probar carga de datos históricos"""
from battery_intelligence_db import get_persistent_battery_manager

mgr = get_persistent_battery_manager('gamepad_monitor.db')

# Probar carga de datos históricos
for device_id in ['ds4_v2_c02acd80', 'joycon_r_3033307d', 'joycon_l_3033307d', 'dualsense_3033307d']:
    print(f'\n=== {device_id} ===')
    
    # Crear monitor (esto cargará los datos históricos)
    monitor = mgr.get_or_create_monitor(device_id, 'unknown')
    
    # Ver datos del monitor
    print(f'  Ciclos equivalentes: {monitor.equivalent_cycles:.2f}')
    print(f'  Ciclos registrados: {len(monitor.cycles)}')
    
    # Obtener salud con historial
    health_data = mgr.get_health_with_history(device_id)
    if health_data:
        current = health_data['current']
        charge_stats = health_data.get('charge_stats', {})
        print(f'  SoH: {current["soh_percent"]:.1f}%')
        print(f'  Confianza: {current["confidence"]:.1f}')
        print(f'  Total cargas: {charge_stats.get("total_charges", 0)}')
        print(f'  Cargas completas: {charge_stats.get("full_charges", 0)}')
