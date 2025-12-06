"""Script para verificar el contenido de la base de datos"""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('gamepad_monitor.db')
cursor = conn.cursor()

# Verificar tablas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f"📊 Tablas en la BD: {tables}")

# Contar registros
cursor.execute("SELECT COUNT(*) FROM devices")
devices_count = cursor.fetchone()[0]
print(f"\n📱 Dispositivos registrados: {devices_count}")

if devices_count > 0:
    cursor.execute("SELECT device_id, device_type, serial_number, firmware_version FROM devices")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]}")
        print(f"     Serial: {row[2]}, Firmware: {row[3]}")

cursor.execute("SELECT COUNT(*) FROM device_metrics")
metrics_count = cursor.fetchone()[0]
print(f"\n📈 Métricas registradas: {metrics_count}")

if metrics_count > 0:
    cursor.execute("""
        SELECT device_id, COUNT(*) as count, 
               AVG(battery_level) as avg_battery, 
               AVG(polling_rate) as avg_polling
        FROM device_metrics
        GROUP BY device_id
    """)
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]} lecturas")
        print(f"     Batería promedio: {row[2]:.1f}%, Polling promedio: {row[3]:.1f}Hz")

conn.close()
