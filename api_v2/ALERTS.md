# Sistema de Alertas - Gamepad Monitor

Sistema de notificaciones en tiempo real mediante WebSocket para monitoreo de dispositivos.

## Características

### Tipos de Alertas

1. **Batería Baja** (`battery_low`)
   - Se activa cuando: batería ≤ 20%
   - Severidad: `warning`
   - Cooldown: 5 minutos

2. **Batería Crítica** (`battery_critical`)
   - Se activa cuando: batería ≤ 10%
   - Severidad: `critical`
   - Cooldown: 2 minutos
   - Incluye sonido de alerta

3. **Polling Degradado** (`polling_degraded`)
   - Se activa cuando:
     - DS4/DS5: polling ≤ 50 Hz
     - Joy-Con: polling ≤ 25 Hz
   - Severidad: `warning`
   - Cooldown: 1 minuto

4. **Dispositivo Desconectado** (`device_disconnected`)
   - Se activa cuando: dispositivo pierde conexión
   - Severidad: `warning`
   - Cooldown: ninguno (inmediato)

5. **Dispositivo Reconectado** (`device_reconnected`)
   - Se activa cuando: dispositivo se reconecta
   - Severidad: `info`
   - Cooldown: ninguno (inmediato)

## Arquitectura

### Backend

- **`alert_manager.py`**: Lógica de detección y generación de alertas
  - `AlertManager`: Clase principal que gestiona alertas
  - `Alert`: Modelo de datos para alertas
  - `AlertType`: Enum con tipos de alertas
  - `AlertSeverity`: Enum con niveles de severidad

- **`main.py`**: WebSocket endpoint (`/api/ws`)
  - Envía updates cada 2 segundos
  - Verifica alertas en cada ciclo
  - Broadcast a todos los clientes conectados

### Frontend

- **WebSocket Connection**: Conecta automáticamente al iniciar
- **Auto-reconnect**: Reintenta conexión cada 5s si se pierde
- **Notificaciones Toast**: Aparecen en esquina superior derecha
- **Sonido de Alerta**: Para alertas críticas
- **Auto-dismiss**: 5s (warning/info), 10s (critical)

## Formato de Mensaje WebSocket

```json
{
  "type": "devices_update",
  "timestamp": "2025-12-03T15:30:00.123456",
  "devices": [...],
  "count": 2,
  "alerts": [
    {
      "type": "battery_low",
      "severity": "warning",
      "device_id": "ds4_v2_5f70861d",
      "device_name": "DualShock 4 (5f70)",
      "message": "Batería baja: 18%",
      "data": {
        "battery": 18
      },
      "timestamp": "2025-12-03T15:30:00.123456"
    }
  ]
}
```

## Sistema de Cooldown

Para evitar spam de notificaciones, cada tipo de alerta tiene un cooldown:

- El mismo dispositivo no puede generar la misma alerta hasta que pase el cooldown
- Los cooldowns se resetean cuando el dispositivo se desconecta completamente
- Las alertas de conexión/desconexión no tienen cooldown

## Umbrales Configurables

En `alert_manager.py`:

```python
# Batería
BATTERY_WARNING = 20    # %
BATTERY_CRITICAL = 10   # %

# Polling rate por dispositivo
POLLING_THRESHOLDS = {
    "ds4": 50,      # Hz
    "ds5": 50,      # Hz
    "joycon": 25    # Hz
}
```

## Uso

### Conectar desde Frontend

```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.alerts && data.alerts.length > 0) {
        data.alerts.forEach(alert => {
            console.log('Alert:', alert);
            // Mostrar notificación
        });
    }
};
```

### Verificar Alertas Manualmente

```python
from alert_manager import AlertManager

alert_mgr = AlertManager()

alerts = alert_mgr.check_device_alerts(
    device_id="ds4_v2_5f70861d",
    device_name="DualShock 4",
    device_type="ds4",
    battery=15,
    polling_rate=45.5,
    is_connected=True
)

for alert in alerts:
    print(alert.to_dict())
```

## Extensibilidad

### Agregar Nuevo Tipo de Alerta

1. Agregar en `AlertType` enum:
```python
class AlertType(str, Enum):
    NEW_ALERT = "new_alert"
```

2. Definir cooldown:
```python
self.alert_cooldown = {
    AlertType.NEW_ALERT: 60  # segundos
}
```

3. Implementar lógica en `check_device_alerts()`:
```python
if some_condition:
    alert = self._create_alert(
        device_id,
        AlertType.NEW_ALERT,
        AlertSeverity.WARNING,
        device_name,
        "Mensaje descriptivo",
        {"extra": "data"}
    )
    if alert:
        alerts.append(alert)
```

## Testing

Para probar alertas sin dispositivos reales:

```python
# En main.py, agregar endpoint de prueba
@app.post("/api/test-alert")
async def test_alert():
    test_alert = Alert(
        alert_type=AlertType.BATTERY_LOW,
        severity=AlertSeverity.WARNING,
        device_id="test_device",
        device_name="Test Device",
        message="Esta es una prueba",
        data={"battery": 15}
    )
    
    # Broadcast a todos los WebSockets
    for ws in active_websockets:
        await ws.send_json({
            "type": "test_alert",
            "alerts": [test_alert.to_dict()]
        })
    
    return {"success": True}
```

## Troubleshooting

### WebSocket no conecta
- Verificar que el servidor esté corriendo en `http://localhost:8000`
- Revisar consola del navegador para errores
- Comprobar CORS si se accede desde otro dominio

### Alertas no aparecen
- Verificar que los umbrales estén correctamente configurados
- Comprobar cooldowns en `alert_manager.py`
- Revisar logs del servidor para ver si se generan alertas

### Alertas duplicadas
- Ajustar cooldowns en `alert_cooldown` dict
- Verificar que el frontend no tenga múltiples WebSockets abiertos

## Futuras Mejoras

- [ ] Persistir alertas en base de datos
- [ ] Historial de alertas en el frontend
- [ ] Configuración de umbrales desde el frontend
- [ ] Notificaciones del sistema operativo
- [ ] Envío de alertas por email/Telegram
- [ ] Estadísticas de alertas por dispositivo
