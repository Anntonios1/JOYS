"""Script para probar conteo de cargas"""
from battery_intelligence_db import get_persistent_battery_manager

mgr = get_persistent_battery_manager('gamepad_monitor.db')

# Probar conteo de cargas
for device_id in ['ds4_v2_c02acd80', 'joycon_r_3033307d', 'joycon_l_3033307d', 'dualsense_3033307d']:
    charges = mgr.get_charge_count(device_id)
    print(f'{device_id}:')
    print(f'  Total cargas: {charges.get("total_charges", 0)}')
    print(f'  Cargas completas: {charges.get("full_charges", 0)}')
    if charges.get('last_charge'):
        lc = charges['last_charge']
        print(f'  Última carga: {lc["from_level"]}% -> {lc["to_level"]}% @ {lc["timestamp"]}')
    print()
