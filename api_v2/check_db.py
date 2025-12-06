"""Script para revisar datos de la base de datos - v2"""
import sqlite3

conn = sqlite3.connect('gamepad_monitor.db')
conn.row_factory = sqlite3.Row

# Ver tablas existentes
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('=== TABLAS ===')
for row in cursor:
    print(f'  - {row[0]}')

# Ver datos de métricas
print('\n=== METRICAS (últimas 10) ===')
cursor = conn.execute('SELECT device_id, battery_level, timestamp FROM device_metrics ORDER BY timestamp DESC LIMIT 10')
for row in cursor:
    print(f'  {row["device_id"]}: {row["battery_level"]}% @ {row["timestamp"]}')

# Ver sesiones
print('\n=== DEVICE_SESSIONS (últimas 5) ===')
cursor = conn.execute('SELECT device_id, initial_battery, final_battery, connected_at, disconnected_at, duration_seconds FROM device_sessions ORDER BY connected_at DESC LIMIT 5')
for row in cursor:
    duration_h = (row["duration_seconds"] or 0) / 3600
    print(f'  {row["device_id"]}: {row["initial_battery"]}% -> {row["final_battery"]}% ({duration_h:.1f}h)')

# Ver historial de descarga
print('\n=== DISCHARGE HISTORY (últimas 10) ===')
cursor = conn.execute('SELECT device_id, start_battery, end_battery, drain_rate_per_hour, duration_hours, timestamp FROM discharge_history ORDER BY timestamp DESC LIMIT 10')
for row in cursor:
    print(f'  {row["device_id"]}: {row["start_battery"]}% -> {row["end_battery"]}% @ {row["drain_rate_per_hour"]:.1f}%/h ({row["duration_hours"]:.2f}h)')

# Ver ciclos de carga (si existe la tabla)
print('\n=== BATTERY_CYCLES (si existe) ===')
try:
    cursor = conn.execute('SELECT * FROM battery_cycles ORDER BY timestamp DESC LIMIT 5')
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f'  {dict(row)}')
    else:
        print('  (vacía)')
except Exception as e:
    print(f'  Error: {e}')

# Contar eventos de carga detectados desde métricas
print('\n=== DETECCIÓN DE CARGAS (desde métricas) ===')
for device_id in ['ds4_v2_c02acd80', 'joycon_r_3033307d', 'joycon_l_3033307d', 'dualsense_3033307d']:
    # Buscar patrones de carga (cuando la batería sube significativamente)
    cursor = conn.execute('''
        SELECT battery_level, timestamp FROM device_metrics 
        WHERE device_id = ? ORDER BY timestamp
    ''', (device_id,))
    metrics = cursor.fetchall()
    
    charge_events = []
    prev_pct = None
    prev_ts = None
    for m in metrics:
        if prev_pct is not None:
            diff = m['battery_level'] - prev_pct
            if diff > 5:  # Subida de más de 5% = probable carga
                charge_events.append({
                    'from': prev_pct,
                    'to': m['battery_level'],
                    'diff': diff,
                    'timestamp': m['timestamp']
                })
        prev_pct = m['battery_level']
        prev_ts = m['timestamp']
    
    # Contar descargas
    cursor = conn.execute('''
        SELECT COUNT(*) as count FROM discharge_history 
        WHERE device_id = ?
    ''', (device_id,))
    discharge_count = cursor.fetchone()['count']
    
    print(f'  {device_id}:')
    print(f'    - Métricas totales: {len(metrics)}')
    print(f'    - Descargas registradas: {discharge_count}')
    print(f'    - Cargas detectadas: {len(charge_events)}')
    if charge_events:
        for ce in charge_events[-3:]:  # Últimas 3
            print(f'      • {ce["from"]}% -> {ce["to"]}% (+{ce["diff"]}%) @ {ce["timestamp"]}')

# Estadísticas generales
print('\n=== ESTADÍSTICAS GENERALES ===')
cursor = conn.execute('SELECT COUNT(*) FROM device_metrics')
print(f'  Total métricas: {cursor.fetchone()[0]}')

cursor = conn.execute('SELECT COUNT(*) FROM device_sessions')
print(f'  Total sesiones: {cursor.fetchone()[0]}')

cursor = conn.execute('SELECT COUNT(*) FROM discharge_history')
print(f'  Total registros descarga: {cursor.fetchone()[0]}')

# Ver battery_specs
print('\n=== BATTERY_SPECS ===')
cursor = conn.execute('SELECT * FROM battery_specs')
for row in cursor:
    print(f'  {dict(row)}')

conn.close()
