# 🎮 Gamepad Monitor

Sistema completo de monitoreo y control de mandos Bluetooth (Joy-Con, Pro Controller, DualShock 4, DualSense) con medición de latencia, batería, y señal en tiempo real.

## 📋 Características

✅ **Conexión/Desconexión Programática** - Control total sobre dispositivos Bluetooth sin usar el panel de Windows  
✅ **Medición de Latencia Real** - Timestamps de paquetes HID, jitter, pérdida de paquetes  
✅ **Monitoreo de Batería** - Nivel, estado de carga, voltaje (cuando está disponible)  
✅ **Intensidad de Señal (RSSI)** - Calidad de conexión Bluetooth  
✅ **Historial en SQLite** - Guarda todos los datos para análisis  
✅ **API REST** - Accesible desde cualquier dispositivo en la red local  
✅ **Frontend Web** - Dashboard responsive con gráficos en tiempo real  
✅ **WebSocket** - Actualizaciones en vivo sin polling  
✅ **Overlay Windows** - Ventana transparente always-on-top  
✅ **Docker Support** - Despliegue con un solo comando  

## 🎯 Dispositivos Soportados

- Nintendo Joy-Con (L/R)
- Nintendo Pro Controller
- Sony DualShock 4 (PS4)
- Sony DualSense (PS5)

## 🏗️ Arquitectura

```
gamepad-monitor/
├── backend/          # Core Bluetooth/HID
│   ├── modules/
│   │   ├── bluetooth_manager.py   # Conexión/desconexión
│   │   ├── battery_monitor.py     # Lectura de batería
│   │   ├── latency_monitor.py     # Medición de latencia
│   │   └── history_manager.py     # Persistencia SQLite
│   └── overlay.py    # Overlay Windows
├── api/              # FastAPI REST + WebSocket
│   └── main.py
├── frontend/         # Web UI
│   ├── index.html
│   └── app.js
├── docker/           # Contenedores
│   ├── Dockerfile.api
│   ├── Dockerfile.frontend
│   └── nginx.conf
└── docker-compose.yml
```

## 🚀 Instalación

### Opción 1: Instalación Local (Windows)

1. **Instalar Python 3.11+**

2. **Instalar dependencias:**
```powershell
cd gamepad-monitor
pip install -r api/requirements.txt
```

3. **Iniciar el servidor:**
```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

4. **Abrir el frontend:**
```powershell
# Abrir frontend/index.html en un navegador
# O usar un servidor simple:
python -m http.server 8080 -d frontend
```

Accede a: `http://localhost:8080`

### Opción 2: Docker (Recomendado)

```powershell
docker-compose up -d
```

Accede a: `http://localhost:8080`  
API: `http://localhost:8000`

## 📖 Uso

### 1. Escanear Dispositivos

Haz clic en "🔍 Scan Devices" en el frontend o:

```powershell
curl -X POST http://localhost:8000/scan
```

### 2. Conectar un Mando

- Pon el mando en modo emparejamiento (botón SYNC por 3 segundos)
- En el frontend, haz clic en "Connect" en la tarjeta del dispositivo

O via API:

```powershell
curl -X POST http://localhost:8000/connect -H "Content-Type: application/json" -d '{"mac_address":"XX:XX:XX:XX:XX:XX"}'
```

### 3. Monitorear en Tiempo Real

El frontend actualiza automáticamente:
- 🔋 Batería (porcentaje, estado de carga)
- ⚡ Latencia (ms, jitter, packet loss)
- 📶 Señal (RSSI, calidad)
- 📊 Gráficos de historial

### 4. Overlay Windows (Opcional)

```powershell
python backend/overlay.py
```

Ventana transparente siempre visible con datos básicos.

## 🔌 API Endpoints

### Dispositivos

```http
GET  /devices                  # Todos los dispositivos
GET  /devices/connected         # Solo conectados
POST /scan                      # Escanear nuevos
POST /connect                   # Conectar
POST /disconnect                # Desconectar
POST /disconnect/force          # Forzar desconexión
```

### Monitoreo

```http
GET /battery/{mac_address}      # Nivel de batería
GET /latency/{mac_address}      # Estadísticas de latencia
GET /signal/{mac_address}       # RSSI y calidad
GET /history/{mac_address}      # Historial completo
```

### Sistema

```http
POST /reset_bluetooth           # Reiniciar stack BT
```

### WebSocket

```http
WS /ws                          # Actualizaciones en vivo
```

## 📊 Ejemplo de Respuesta

### Battery

```json
{
  "percentage": 85,
  "level": "FULL",
  "charging": false,
  "voltage": 3.7
}
```

### Latency

```json
{
  "current_ms": 8.5,
  "average_ms": 9.2,
  "min_ms": 7.1,
  "max_ms": 12.4,
  "jitter_ms": 1.3,
  "packet_loss": 0.5,
  "total_packets": 1000,
  "dropped_packets": 5
}
```

## 🐛 Solución de Problemas

### El mando se conecta y desconecta

Ejecuta el script de reparación:

```powershell
Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File "solucion-permanente.ps1"'
```

### No se detectan dispositivos

1. Verifica que Bluetooth esté habilitado
2. Pon el mando en modo emparejamiento
3. Ejecuta: `POST /reset_bluetooth`

### Errores de permisos

Ejecuta como Administrador:

```powershell
Start-Process powershell -Verb RunAs
```

### El overlay no aparece

Instala tkinter:

```powershell
pip install tk
```

## 🔧 Configuración Avanzada

### Cambiar intervalo de actualización

En `frontend/app.js`:

```javascript
const UPDATE_INTERVAL = 5000; // ms
```

En `api/main.py`:

```python
await asyncio.sleep(5)  # seconds
```

### Base de datos personalizada

En `backend/modules/history_manager.py`:

```python
HistoryManager(db_path="custom_path.db")
```

### Puerto del servidor

```powershell
uvicorn api.main:app --host 0.0.0.0 --port 9000
```

## 🛠️ Desarrollo

### Estructura de Módulos

- **bluetooth_manager.py**: Maneja conexiones BLE usando `bleak`
- **battery_monitor.py**: Parsea HID reports para batería
- **latency_monitor.py**: Calcula latencia de paquetes HID
- **history_manager.py**: SQLite para persistencia
- **main.py**: FastAPI + WebSocket server
- **overlay.py**: Tkinter transparent window

### Agregar soporte para nuevo dispositivo

1. Añade identificador en `bluetooth_manager.py`:
```python
CONTROLLER_IDENTIFIERS = {
    "New Controller": ["Device Name"]
}
```

2. Implementa parser de batería en `battery_monitor.py`:
```python
async def read_new_controller_battery(self, client):
    # Implementar lógica específica
    pass
```

## 📝 Licencia

MIT License - Úsalo libremente

## 🤝 Contribuciones

Pull requests bienvenidos. Para cambios grandes, abre un issue primero.

## 📞 Soporte

Si tienes problemas:
1. Revisa la sección de troubleshooting
2. Ejecuta el script de diagnóstico
3. Abre un issue con los logs

## 🎯 Roadmap

- [ ] Soporte para más controladores (Xbox, 8BitDo)
- [ ] Modo headless para servidores
- [ ] Perfiles de configuración
- [ ] Alertas de batería baja
- [ ] Exportar datos a CSV
- [ ] App móvil nativa

---

Made with 💚 for gamers who want to know EVERYTHING about their controllers
