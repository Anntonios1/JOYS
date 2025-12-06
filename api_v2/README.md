# Gamepad Monitor API v2

API modular para monitoreo de controladores de videojuegos:
- Nintendo Switch Joy-Cons
- Sony DualShock 4
- Microsoft Xbox Controllers

## Características

### Joy-Cons
- ✅ Batería con voltaje preciso (método de jc_toolkit)
- ✅ Colores del cuerpo, botones y grips
- ✅ Número de serie
- ✅ Versión de firmware
- ✅ Polling rate (~67Hz en Windows)
- ✅ Vibración

### DualShock 4
- ✅ Batería con estado de carga
- ✅ Detección de tipo de conexión (Bluetooth/USB)
- ✅ Polling rate
- ✅ Vibración con LED

### Xbox Controllers
- ✅ Detección de modelos (One, Elite, Series X|S)
- ✅ Polling rate
- ⚠️ Batería limitada (requiere XInput)
- ⚠️ Vibración limitada (requiere XInput)

## Arquitectura Modular

```
api_v2/
├── main.py              # FastAPI server
├── device_manager.py    # Gestor de dispositivos
├── models/              # Modelos Pydantic
│   ├── device_models.py
│   └── __init__.py
└── readers/             # Lectores por tipo de controlador
    ├── joycon_reader.py
    ├── ds4_reader.py
    ├── xbox_reader.py
    └── __init__.py
```

### Ventajas de la Separación
- 🔧 **Modular**: Cada controlador tiene código aislado
- 🛡️ **Resiliente**: Fallo en un tipo no afecta a otros
- 📦 **Extensible**: Agregar nuevos controladores fácilmente
- 🧪 **Testeable**: Probar cada reader independientemente

## Instalación

```powershell
# Instalar dependencias
pip install fastapi uvicorn hidapi pydantic websockets

# Ejecutar API
cd api_v2
python main.py
```

## API Endpoints

### REST
- `GET /api/devices` - Lista de dispositivos conectados
- `GET /api/device/{id}` - Info completa de un dispositivo
- `POST /api/device/{id}/vibrate` - Hacer vibrar dispositivo
- `POST /api/scan` - Escanear nuevos dispositivos
- `POST /api/refresh` - Refrescar lista (detectar/remover)
- `GET /api/health` - Health check

### WebSocket
- `ws://localhost:8000/api/ws` - Updates en tiempo real cada 2s

## Documentación Interactiva

Una vez ejecutando:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Ejemplos de Uso

### Python
```python
import requests

# Obtener todos los dispositivos
response = requests.get("http://localhost:8000/api/devices")
devices = response.json()

# Obtener info de Joy-Con específico
response = requests.get("http://localhost:8000/api/device/joycon_l_12345678")
info = response.json()
print(f"Batería: {info['battery']['percentage']}% ({info['battery']['voltage']}V)")

# Vibrar
requests.post(
    "http://localhost:8000/api/device/joycon_l_12345678/vibrate",
    json={"duration": 1.5, "intensity": 0.8}
)
```

### JavaScript (Frontend)
```javascript
// WebSocket para updates en tiempo real
const ws = new WebSocket('ws://localhost:8000/api/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`${data.count} dispositivos conectados`);
  
  data.devices.forEach(device => {
    console.log(`${device.model}: ${device.battery.percentage}%`);
  });
};

// Vibrar con fetch
fetch('http://localhost:8000/api/device/joycon_l_12345678/vibrate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ duration: 1.0, intensity: 0.7 })
});
```

## Batería Precisa en Joy-Cons

Usa el método de **jc_toolkit** con conversión de voltaje:
- Subcomando 0x50 retorna voltaje en bytes 0xF + 0x10
- Fórmulas no lineales mapean voltaje a porcentaje
- Resultado: **56%** (3.86V) en vez de solo "50%" o "75%"

## Limitaciones Windows

- **Joy-Cons**: Polling rate limitado a ~67Hz (vs ~120Hz en Switch)
- **Xbox**: Batería y vibración requieren XInput API (no disponible vía HID)

## Frontend

El frontend existente (`frontend/index_pro.html`) será actualizado para consumir esta API.
