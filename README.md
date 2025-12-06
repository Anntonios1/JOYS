# 🎮 JOYS - Gamepad Monitor Pro

Sistema profesional de monitoreo y control de mandos Bluetooth con overlay QML, sistema de numeración de jugadores, efectos visuales y base de datos integrada.

## ✨ Características Principales

### 🎯 Control de Dispositivos
- ✅ **Conexión/Desconexión Programática** - Control total sobre dispositivos Bluetooth sin usar el panel de Windows
- ✅ **Sistema de Jugadores (1-8)** - Asignación automática con indicadores LED físicos en Joy-Cons
- ✅ **Vibración al Conectar** - Feedback háptico personalizado por tipo de dispositivo
- ✅ **Hasta 8 Joy-Cons** - Soporte para múltiples mandos simultáneos con patrones LED únicos

### 📊 Monitoreo Avanzado
- ✅ **Medición de Latencia Real** - Timestamps de paquetes HID, jitter, pérdida de paquetes
- ✅ **Batería Detallada** - Nivel, estado de carga, consumo en tiempo real
- ✅ **Intensidad de Señal (RSSI)** - Calidad de conexión Bluetooth
- ✅ **Historial en SQLite** - Base de datos con player_number y métricas completas

### 🎨 Interfaz y Efectos
- ✅ **Overlay QML Fluido** - Ventana transparente sin parpadeos con PyQt6
- ✅ **TopColorBar Animado** - Barra de color que se anima al conectar dispositivos
- ✅ **Notificaciones Toast** - Alertas visuales con número de jugador
- ✅ **Sonidos de Conexión** - Efectos de audio con pygame (Switch, PS4, PS5)
- ✅ **Iconos SVG Blancos** - Nintendo, PlayStation, Xbox con antialiasing
- ✅ **LED Indicators** - 4 cuadros visuales mostrando patrón de luces del mando

### 🌐 API y Web
- ✅ **API REST v2** - FastAPI con endpoints completos
- ✅ **WebSocket en Tiempo Real** - Actualizaciones instantáneas sin polling
- ✅ **Frontend Web v3** - Dashboard responsive con gráficos Chart.js
- ✅ **Servicio Web Completo** - Acceso desde cualquier dispositivo en la red  

## 🎯 Dispositivos Soportados

### Nintendo
- **Joy-Con (L/R)** - Sistema de jugadores 1-8 con patrones LED oficiales
- **Pro Controller** - Batería y latencia detallada

### Sony
- **DualShock 4 (PS4)** - Touchpad, giroscopio, barra LED
- **DualSense (PS5)** - Gatillos adaptativos, feedback háptico avanzado

### Patrones LED de Jugadores (Joy-Con)
- 🟢 **Jugador 1**: LED 1
- 🟢 **Jugador 2**: LED 1-2
- 🟢 **Jugador 3**: LED 1-2-3
- 🟢 **Jugador 4**: LED 1-2-3-4
- 🟡 **Jugador 5**: LED 1 y 4
- 🟡 **Jugador 6**: LED 1-2 parpadeando
- 🟡 **Jugador 7**: LED 1-3-4
- 🟡 **Jugador 8**: LED 2-3

## 🏗️ Arquitectura

```
gamepad-monitor/
├── api_v2/                    # Backend Principal
│   ├── main.py                # FastAPI server + WebSocket
│   ├── device_manager.py      # Gestión de dispositivos y jugadores
│   ├── db_manager.py          # SQLite con player_number
│   ├── models/
│   │   └── device_models.py   # DeviceInfo con player_number
│   └── readers/
│       ├── joycon_reader.py   # Control LED, vibración, batería Joy-Con
│       ├── dualshock4_reader.py
│       └── dualsense_reader.py
│
├── overlay/                   # Overlay QML
│   ├── gamepad_overlay_qml.py # Controller Python + WebSocket
│   ├── OverlayMain.qml        # Ventana principal transparente
│   ├── DeviceCard.qml         # Tarjeta con LED indicators
│   ├── HeaderButton.qml       # Botones del header
│   ├── TopColorBar.qml        # Animación de conexión
│   ├── NotificationToast.qml  # Notificaciones visuales
│   └── assets/
│       ├── nintendo_white.svg
│       ├── ps_icon_white.svg
│       ├── xbox_white.svg
│       ├── switch-sound.mp3
│       ├── ps4-trophy.mp3
│       └── ps5-trophy.mp3
│
├── frontend/                  # Web Dashboard v3
│   ├── index.html             # Dashboard responsive
│   ├── nintendo.png
│   ├── PlayStation-Logo.wine.png
│   ├── Xbox_one_logo.svg.png
│   └── icons/                 # Iconos adicionales
│
└── database/
    └── gamepad_monitor.db     # SQLite con player_number
```

## 🚀 Instalación y Uso

### Requisitos Previos

- **Windows 10/11** (para overlay QML y control Bluetooth)
- **Python 3.11+**
- **Bluetooth 4.0+** habilitado

### Instalación

1. **Clonar el repositorio:**
```powershell
git clone https://github.com/Anntonios1/JOYS.git
cd JOYS
```

2. **Instalar dependencias:**
```powershell
pip install -r requirements.txt
```

Dependencias principales:
- `PyQt6` + `PyQt6-Qt6` - Overlay QML
- `fastapi` + `uvicorn` - API REST
- `aiohttp` - WebSocket
- `pygame` - Sonidos
- `bleak` - Bluetooth LE
- `hid` - Control HID

### Iniciar el Sistema

#### 1. Iniciar API (Terminal 1)
```powershell
cd api_v2
python main.py
```

Servidor corriendo en: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Frontend Web: `http://localhost:8000/`
- WebSocket: `ws://localhost:8000/api/ws`

#### 2. Iniciar Overlay QML (Terminal 2)
```powershell
cd overlay
python gamepad_overlay_qml.py
```

Ventana transparente con actualizaciones en tiempo real vía WebSocket.

### Uso Básico

#### Conectar Joy-Cons

1. **Modo Emparejamiento:**
   - Presiona el botón circular pequeño entre **SR** y **SL** por 3 segundos
   - Los 4 LEDs parpadearán rápidamente

2. **Conectar desde Overlay:**
   - Haz clic en el botón **"Scan"** del overlay
   - Espera a que aparezca el dispositivo
   - Haz clic en **"Connect"**

3. **Asignación Automática:**
   - El sistema asigna automáticamente un número de jugador (1-8)
   - Los LEDs del Joy-Con se encienden con el patrón correspondiente
   - Vibración de confirmación
   - Notificación en pantalla con número de jugador

#### Conectar DualShock 4 / DualSense

1. **Modo Emparejamiento:**
   - Mantén presionado **SHARE + PS** por 3 segundos
   - La barra LED parpadeará

2. **Conectar desde Overlay o API**

### Características del Overlay

- **Header:**
  - 🔍 **Scan**: Buscar nuevos dispositivos
  - 🔄 **Refresh**: Actualizar lista
  - ⚙️ **Settings**: Configuración (próximamente)

- **Tarjeta de Dispositivo:**
  - Icono del fabricante (Nintendo/PlayStation/Xbox)
  - Nombre del dispositivo + Tipo (L/R para Joy-Con)
  - Número de jugador (1-8)
  - Indicadores LED visuales (4 cuadros)
  - Polling rate en Hz
  - Consumo en mAh
  - Batería con indicador visual
  - Botón Connect/Disconnect

- **Efectos Visuales:**
  - TopColorBar animada según color del dispositivo
  - Notificaciones Toast al conectar/desconectar
  - Sonidos de conexión (Switch/PlayStation)

## 🔌 API REST v2

### Base URL
```
http://localhost:8000/api
```

### Endpoints de Dispositivos

#### Listar Dispositivos
```http
GET /api/devices
```
Respuesta:
```json
[
  {
    "id": "AA:BB:CC:DD:EE:FF",
    "name": "Joy-Con (L)",
    "type": "joycon_l",
    "connected": true,
    "battery_percent": 85,
    "player_number": 1,
    "polling_rate_hz": 62.5,
    "latency_ms": 8.3,
    "consumption_mah": 15.2
  }
]
```

#### Conectar Dispositivo
```http
POST /api/devices/{device_id}/connect
```

#### Desconectar Dispositivo
```http
POST /api/devices/{device_id}/disconnect
```

#### Obtener/Actualizar Número de Jugador
```http
GET  /api/devices/{device_id}/player_number
POST /api/devices/{device_id}/player_number
Body: {"player_number": 1}  // 1-8
```

#### Escanear Dispositivos
```http
POST /api/scan
Query: ?duration=10  // segundos
```

### Endpoints de Monitoreo

#### Batería
```http
GET /api/devices/{device_id}/battery
```
Respuesta:
```json
{
  "percentage": 85,
  "level": "FULL",
  "charging": false,
  "voltage": 3.7
}
```

#### Latencia
```http
GET /api/devices/{device_id}/latency
```
Respuesta:
```json
{
  "current_ms": 8.5,
  "average_ms": 9.2,
  "min_ms": 7.1,
  "max_ms": 12.4,
  "jitter_ms": 1.3,
  "packet_loss": 0.5
}
```

### WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};
```

Mensajes:
- `device_connected` - Nuevo dispositivo conectado
- `device_disconnected` - Dispositivo desconectado
- `device_update` - Actualización de métricas
- `scan_complete` - Escaneo finalizado

## 🎨 Tecnologías y Stack

### Backend
- **Python 3.11+** - Lenguaje principal
- **FastAPI** - Framework API REST moderno y rápido
- **uvicorn** - Servidor ASGI de alto rendimiento
- **aiohttp** - Cliente WebSocket asíncrono
- **bleak** - Biblioteca Bluetooth LE multiplataforma
- **hidapi** - Acceso directo a dispositivos HID
- **SQLite3** - Base de datos embebida con player_number

### Frontend Overlay
- **PyQt6** - Framework Qt para Python
- **QtQuick 2.15** - Motor QML para interfaces fluidas
- **pygame** - Motor de audio para efectos de sonido
- **WebSocket** - Comunicación en tiempo real con API

### Frontend Web
- **HTML5 + TailwindCSS** - UI responsive con glassmorphism
- **JavaScript ES6+** - Lógica del cliente
- **Chart.js 4.4** - Gráficos en tiempo real
- **WebSocket API** - Actualizaciones en vivo

### Base de Datos
```sql
-- Tabla devices
CREATE TABLE devices (
    id TEXT PRIMARY KEY,
    name TEXT,
    type TEXT,
    player_number INTEGER,  -- 1-8 para Joy-Cons
    battery_percent INTEGER,
    connected BOOLEAN,
    last_seen TIMESTAMP
);
```

## 🐛 Solución de Problemas

### El overlay no aparece o se cierra inmediatamente

**Causa:** Falta PyQt6 o hay conflicto de versiones

**Solución:**
```powershell
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip
pip install PyQt6==6.6.1 PyQt6-Qt6==6.6.1
```

### Los Joy-Cons se conectan y desconectan constantemente

**Causa:** Driver de Bluetooth de Windows interfiere

**Solución:** Ejecutar como Administrador
```powershell
Start-Process powershell -Verb RunAs
cd api_v2
python main.py
```

### No se detectan dispositivos al escanear

1. **Verificar Bluetooth:**
   - Configuración de Windows → Bluetooth → Habilitado
   
2. **Verificar modo emparejamiento:**
   - Joy-Con: Presionar botón circular pequeño por 3+ segundos
   - DualShock/DualSense: SHARE + PS por 3+ segundos

3. **Reiniciar el servicio:**
```powershell
# En PowerShell Administrador
Restart-Service bthserv
```

### Las imágenes no cargan en el frontend web

**Causa:** Rutas relativas incorrectas

**Solución:** Ya están corregidas en la última versión. Si persiste:
- Acceder vía: `http://localhost:8000/` (raíz)
- NO acceder directamente a `frontend/index.html`

### El overlay parpadea o tiene lag

**Causa:** Actualizaciones muy frecuentes o problemas de red

**Solución:**
1. Verificar conexión WebSocket en overlay:
```python
# En gamepad_overlay_qml.py
print(f"📡 WebSocket conectado")  # Debe aparecer
```

2. Reducir frecuencia de actualización en `api_v2/main.py`:
```python
await asyncio.sleep(1)  # Cambiar a 2 o 3 segundos
```

### Los LEDs del Joy-Con no se encienden correctamente

**Causa:** Subcomando 0x30 no enviado correctamente

**Solución:** 
- Verificar que el Joy-Con esté completamente conectado
- El sistema reintenta automáticamente 3 veces
- Logs en terminal deben mostrar: `✓ Player lights set successfully`

### pygame.error: No audio device

**Causa:** pygame no encuentra dispositivo de audio

**Solución:**
```powershell
# Deshabilitar sonidos temporalmente comentando en gamepad_overlay_qml.py:
# pygame.mixer.music.load(...)
# pygame.mixer.music.play()
```

O instalar drivers de audio actualizados.

### Error "Database is locked"

**Causa:** Múltiples instancias accediendo a la base de datos

**Solución:**
- Cerrar todas las instancias de `main.py`
- Eliminar archivo `database/gamepad_monitor.db-lock` si existe
- Reiniciar solo una instancia

### Errores de permisos

Ejecuta como Administrador:

```powershell
Start-Process powershell -Verb RunAs
```

## 🔧 Configuración Avanzada

### Personalizar Patrones LED

Editar `api_v2/readers/joycon_reader.py`:

```python
async def set_player_lights(self, player_num: int):
    patterns = {
        1: 0x01,  # LED 1
        2: 0x03,  # LED 1-2
        # ... personalizar aquí
    }
```

### Cambiar Sonidos de Conexión

Reemplazar archivos en `overlay/assets/`:
- `switch-sound.mp3` - Joy-Con
- `ps4-trophy.mp3` - DualShock 4
- `ps5-trophy.mp3` - DualSense

Formato: MP3, máx 3 segundos, volumen normalizado

### Ajustar Frecuencia de Polling

En `api_v2/device_manager.py`:

```python
await asyncio.sleep(0.016)  # 60 Hz (16ms)
await asyncio.sleep(0.008)  # 125 Hz (8ms)
```

### Cambiar Puerto del Servidor

En `api_v2/main.py`:

```python
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
```

### Personalizar Overlay

Editar `overlay/OverlayMain.qml`:

```qml
width: 350  // Ancho de ventana
height: 600 // Alto de ventana
color: "#1a1a2e80"  // Color de fondo (RGBA)
```

### Base de Datos Personalizada

En `api_v2/main.py`:

```python
db_manager = DatabaseManager(db_path="custom_path.db")
```

## 🛠️ Desarrollo y Arquitectura Interna

### Flujo de Conexión de Joy-Con

1. **Escaneo BLE** (`device_manager.py`)
   - Busca dispositivos con nombre "Joy-Con"
   - Almacena dirección MAC y nombre

2. **Conexión HID** (`joycon_reader.py`)
   - Abre dispositivo HID con `hid.device()`
   - Detecta tipo (L/R) por product_id

3. **Asignación de Jugador** (`device_manager.py`)
   ```python
   player_num = len([d for d in devices if "Joy-Con" in d.name]) + 1
   if player_num <= 8:
       await reader.set_player_lights(player_num)
   ```

4. **Configuración Inicial**
   - Enviar subcomando 0x30 (Set Player Lights)
   - Enviar subcomando 0x48 (Enable Vibration)
   - Vibración de confirmación

5. **Bucle de Lectura**
   - Lectura continua de HID input reports
   - Parseo de batería, botones, sticks
   - Cálculo de latencia y polling rate

### Estructura de HID Reports (Joy-Con)

**Input Report (0x30 - Standard Full Mode):**
```
Byte 0: Report ID (0x30)
Byte 1: Timer (8-bit counter, increments each packet)
Byte 2: Battery + Connection info
  - Bits 0-3: Battery level (0-8)
  - Bit 4: Charging flag
Byte 3-5: Button status
Byte 6-8: Left stick data (12-bit X, 12-bit Y)
Byte 9-11: Right stick data
Byte 12+: IMU data (6-axis sensor)
```

### Cálculo de Métricas

**Polling Rate:**
```python
packets_received_in_1s / 1.0 = Hz
```

**Latencia:**
```python
time.time() - last_packet_time = latency_ms
```

**Consumo (estimado):**
```python
base_current_mah * (1 + (polling_hz / 125)) = consumption_mah
```

### Patrones LED (Subcomando 0x30)

Formato del subcomando:
```python
[0x01, 0x30, led_byte]
# led_byte bits:
# 0x01 = LED 1
# 0x02 = LED 2
# 0x04 = LED 3
# 0x08 = LED 4
# 0x10-0x80 = Flash patterns
```

### WebSocket Protocol

**Cliente → Servidor:**
```json
{"action": "scan", "duration": 10}
{"action": "connect", "device_id": "..."}
{"action": "disconnect", "device_id": "..."}
```

**Servidor → Cliente:**
```json
{
  "type": "device_update",
  "devices": [...]
}
```

## 📝 Licencia

MIT License - Úsalo libremente

## 🤝 Contribuciones

Pull requests bienvenidos. Para cambios grandes, abre un issue primero.

### Áreas de Contribución
- 🎮 Soporte para nuevos controladores (Xbox, 8BitDo)
- 🌐 Traducción a otros idiomas
- 📊 Nuevas métricas de monitoreo
- 🎨 Temas personalizables para overlay
- 📱 App móvil (Android/iOS)

## 📞 Soporte

Si tienes problemas:
1. Revisa la sección **🐛 Solución de Problemas**
2. Verifica los logs en la terminal donde corre `main.py`
3. Abre un issue en GitHub con:
   - Versión de Windows
   - Logs completos de error
   - Tipo de dispositivo
   - Pasos para reproducir

## 🎯 Roadmap

### ✅ Completado
- ✅ Sistema de jugadores (1-8) con LEDs físicos
- ✅ Overlay QML fluido sin parpadeos
- ✅ Efectos visuales y sonoros de conexión
- ✅ WebSocket en tiempo real
- ✅ Base de datos con player_number
- ✅ Frontend web v3 responsive
- ✅ Soporte para 8 Joy-Cons simultáneos

### 🚧 En Progreso
- [ ] Mapeo de botones personalizable
- [ ] Grabación de sesiones de juego
- [ ] Estadísticas de uso por dispositivo

### 📅 Futuro
- [ ] Soporte Xbox Elite Controller
- [ ] Soporte 8BitDo Pro 2
- [ ] Modo headless (sin GUI)
- [ ] Alertas de batería baja configurables
- [ ] Exportar métricas a CSV/JSON
- [ ] App móvil (React Native)
- [ ] Temas oscuro/claro para overlay
- [ ] Perfiles de vibración personalizados
- [ ] Análisis de input lag detallado
- [ ] Cloud sync de configuraciones

---

## 🏆 Características Destacadas

### Sistema de Jugadores Único
Este es el **único proyecto open-source** que implementa el sistema completo de jugadores de Nintendo Switch con control directo de LEDs físicos en Joy-Cons.

### Overlay Sin Parpadeos
Usando **PyQt6 + QML** conseguimos un overlay más fluido que las implementaciones con Tkinter o PyQt5, con actualizaciones solo cuando hay cambios reales.

### Control HID Directo
Acceso **directo a hidapi** permite control total sobre subcomandos de Joy-Con, incluyendo vibración HD y lectura de giroscopio.

---

Made with 💙 by [Anntonios1](https://github.com/Anntonios1) para la comunidad gamer que quiere **control total** sobre sus mandos

## 📊 Estadísticas del Proyecto

- **Lenguaje Principal:** Python 3.11+
- **Líneas de Código:** ~8,000+
- **Dispositivos Soportados:** 4 tipos (Joy-Con L/R, Pro, DS4, DS5)
- **APIs:** REST + WebSocket
- **Interfaces:** Overlay QML + Web Dashboard
- **Base de Datos:** SQLite con migraciones automáticas
