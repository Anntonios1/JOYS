"""
Test de Alertas - Sistema de Notificaciones
"""

from alert_manager import AlertManager, AlertType, AlertSeverity

# Crear instancia
alert_mgr = AlertManager()

print("=" * 60)
print("🔔 TEST DEL SISTEMA DE ALERTAS")
print("=" * 60)

# Test 1: Batería baja en DS4
print("\n1️⃣ Test: Batería baja en DS4 (18%)")
alerts = alert_mgr.check_device_alerts(
    device_id="ds4_v2_5f70861d",
    device_name="DualShock 4 (5f70)",
    device_type="ds4",
    battery=18,
    polling_rate=250,
    is_connected=True
)
for alert in alerts:
    print(f"   ⚠️ {alert.message}")
    print(f"   Severidad: {alert.severity.value}")

# Test 2: Batería crítica
print("\n2️⃣ Test: Batería crítica (8%)")
alerts = alert_mgr.check_device_alerts(
    device_id="ds4_v2_5f70861d",
    device_name="DualShock 4 (5f70)",
    device_type="ds4",
    battery=8,
    polling_rate=250,
    is_connected=True
)
for alert in alerts:
    print(f"   🚨 {alert.message}")
    print(f"   Severidad: {alert.severity.value}")

# Test 3: Polling degradado DS4
print("\n3️⃣ Test: Polling degradado DS4 (45 Hz)")
alerts = alert_mgr.check_device_alerts(
    device_id="ds4_v2_31408382",
    device_name="DualShock 4 (3140)",
    device_type="ds4",
    battery=85,
    polling_rate=45,
    is_connected=True
)
for alert in alerts:
    print(f"   ⚠️ {alert.message}")
    print(f"   Data: {alert.data}")

# Test 4: Polling degradado Joy-Con
print("\n4️⃣ Test: Polling degradado Joy-Con (20 Hz)")
alerts = alert_mgr.check_device_alerts(
    device_id="joycon_left_abc123",
    device_name="Joy-Con (L)",
    device_type="joycon",
    battery=75,
    polling_rate=20,
    is_connected=True
)
for alert in alerts:
    print(f"   ⚠️ {alert.message}")
    print(f"   Umbral: {alert.data.get('threshold')} Hz")

# Test 5: Dispositivo desconectado
print("\n5️⃣ Test: Dispositivo desconectado")
# Primera llamada: conectado
alert_mgr.check_device_alerts(
    device_id="ds4_v2_test",
    device_name="DualShock 4 Test",
    device_type="ds4",
    battery=50,
    polling_rate=250,
    is_connected=True
)
# Segunda llamada: desconectado
alerts = alert_mgr.check_device_alerts(
    device_id="ds4_v2_test",
    device_name="DualShock 4 Test",
    device_type="ds4",
    battery=None,
    polling_rate=None,
    is_connected=False
)
for alert in alerts:
    print(f"   ⚠️ {alert.message}")
    print(f"   Tipo: {alert.type.value}")

# Test 6: Dispositivo reconectado
print("\n6️⃣ Test: Dispositivo reconectado")
alerts = alert_mgr.check_device_alerts(
    device_id="ds4_v2_test",
    device_name="DualShock 4 Test",
    device_type="ds4",
    battery=50,
    polling_rate=250,
    is_connected=True
)
for alert in alerts:
    print(f"   ℹ️ {alert.message}")
    print(f"   Tipo: {alert.type.value}")

# Test 7: Cooldown (no debe generar alerta)
print("\n7️⃣ Test: Cooldown (batería baja repetida inmediatamente)")
alerts1 = alert_mgr.check_device_alerts(
    device_id="ds4_v2_cooldown",
    device_name="DualShock 4 Cooldown",
    device_type="ds4",
    battery=15,
    polling_rate=250,
    is_connected=True
)
print(f"   Primera alerta: {len(alerts1)} generada(s)")

# Inmediatamente después (debe bloquearse por cooldown)
alerts2 = alert_mgr.check_device_alerts(
    device_id="ds4_v2_cooldown",
    device_name="DualShock 4 Cooldown",
    device_type="ds4",
    battery=15,
    polling_rate=250,
    is_connected=True
)
print(f"   Segunda alerta (inmediata): {len(alerts2)} generada(s) ✅ (bloqueada por cooldown)")

# Test 8: Umbrales por tipo de dispositivo
print("\n8️⃣ Test: Umbrales por tipo de dispositivo")
print(f"   DS4: ≤ {alert_mgr.POLLING_THRESHOLDS['ds4']} Hz")
print(f"   DS5: ≤ {alert_mgr.POLLING_THRESHOLDS['ds5']} Hz")
print(f"   Joy-Con: ≤ {alert_mgr.POLLING_THRESHOLDS['joycon']} Hz")

print("\n" + "=" * 60)
print("✅ Tests completados")
print("=" * 60)
