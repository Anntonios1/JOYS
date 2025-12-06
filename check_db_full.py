import sqlite3
from datetime import datetime

# Conectar a la base de datos correcta (en api_v2/)
conn = sqlite3.connect('api_v2/gamepad_monitor.db')
cursor = conn.cursor()

print("=" * 60)
print("DISPOSITIVOS REGISTRADOS (Datos Estáticos)")
print("=" * 60)
cursor.execute("SELECT * FROM devices ORDER BY last_seen DESC")
devices = cursor.fetchall()
for dev in devices:
    print(f"\nDevice ID: {dev[0]}")
    print(f"  Tipo: {dev[1]}")
    print(f"  Serial: {dev[2]}")
    print(f"  Firmware: {dev[3]}")
    print(f"  Colors: {dev[4]}")
    print(f"  First Seen: {dev[5]}")
    print(f"  Last Seen: {dev[6]}")

print("\n" + "=" * 60)
print("MÉTRICAS REGISTRADAS (Últimas 10 por dispositivo)")
print("=" * 60)
cursor.execute("""
    SELECT device_id, COUNT(*) as total
    FROM device_metrics
    GROUP BY device_id
    ORDER BY total DESC
""")
metrics_summary = cursor.fetchall()
for device_id, count in metrics_summary:
    print(f"\n{device_id}: {count} registros")
    cursor.execute("""
        SELECT timestamp, battery_level, polling_rate
        FROM device_metrics
        WHERE device_id = ?
        ORDER BY timestamp DESC
        LIMIT 5
    """, (device_id,))
    recent = cursor.fetchall()
    for ts, battery, polling in recent:
        print(f"  {ts} - Batería: {battery}% | Polling: {polling:.1f}Hz")

print("\n" + "=" * 60)
print(f"Total dispositivos: {len(devices)}")
print(f"Total métricas: {sum(c for _, c in metrics_summary)}")
print("=" * 60)

conn.close()
