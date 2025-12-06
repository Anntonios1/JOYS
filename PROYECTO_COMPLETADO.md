# 🎮 GAMEPAD MONITOR - SISTEMA COMPLETO

## ✅ PROYECTO COMPLETADO

Se ha creado un sistema completo de monitoreo y control de mandos Bluetooth con las siguientes características:

### 📦 Archivos Creados: 22

```
gamepad-monitor/
├── 📄 README.md                    # Documentación principal
├── 📄 start.bat                    # Inicio rápido Windows
├── 📄 start.ps1                    # Inicio rápido PowerShell
├── 📄 docker-compose.yml           # Configuración Docker
├── 📄 .gitignore                   # Git ignore
│
├── 🔧 api/
│   ├── main.py                     # FastAPI + WebSocket
│   └── requirements.txt            # Dependencias API
│
├── 🔌 backend/
│   ├── __init__.py
│   ├── overlay.py                  # Overlay Windows
│   ├── requirements.txt            # Dependencias backend
│   └── modules/
│       ├── __init__.py
│       ├── bluetooth_manager.py    # Gestión Bluetooth
│       ├── battery_monitor.py      # Monitor batería
│       ├── latency_monitor.py      # Monitor latencia
│       └── history_manager.py      # Historial SQLite
│
├── 🌐 frontend/
│   ├── index.html                  # UI web
│   └── app.js                      # Lógica frontend
│
├── 🐳 docker/
│   ├── Dockerfile.api              # Container API
│   ├── Dockerfile.frontend         # Container frontend
│   └── nginx.conf                  # Nginx config
│
└── 📚 docs/
    ├── QUICKSTART.md               # Inicio rápido
    └── ARCHITECTURE.md             # Arquitectura
```

## 🚀 CÓMO USAR

### Opción 1: Inicio Automático (Recomendado)

```powershell
cd C:\Users\teamp\Documents\joys\gamepad-monitor
.\start.ps1
```

### Opción 2: Manual

```powershell
# Terminal 1 - API
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
python -m http.server 8080 -d frontend
```

### Opción 3: Docker

```powershell
docker-compose up -d
```

## 🎯 ACCESO

- **Frontend**: http://localhost:8080
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **WebSocket**: ws://localhost:8000/ws

## 📱 FUNCIONALIDADES

### ✅ Conexión/Desconexión
- Escaneo de dispositivos Bluetooth
- Conexión programática sin panel de Windows
- Desconexión forzada cuando Windows falla
- Detección automática de Joy-Con, Pro Controller, DS4, DS5

### ✅ Monitoreo de Batería
- Porcentaje exacto (0-100%)
- Estado de carga
- Voltaje (cuando disponible)
- Historial guardado en SQLite

### ✅ Medición de Latencia
- Latencia actual en ms
- Promedio, mínimo, máximo
- Jitter (variación)
- Pérdida de paquetes
- Gráfico en tiempo real

### ✅ Intensidad de Señal
- RSSI en dBm
- Calidad: Excellent/Good/Fair/Poor
- Actualización en tiempo real

### ✅ Interfaz Web
- Dashboard responsive
- Tarjetas por dispositivo
- Gráficos interactivos
- Actualizaciones vía WebSocket
- Compatible con móviles

### ✅ Overlay Windows
- Ventana transparente
- Siempre visible
- Datos mínimos
- Arrastrable

### ✅ API REST
Endpoints completos:
- `GET /devices` - Listar dispositivos
- `POST /scan` - Escanear
- `POST /connect` - Conectar
- `POST /disconnect` - Desconectar
- `GET /battery/{mac}` - Batería
- `GET /latency/{mac}` - Latencia
- `GET /signal/{mac}` - Señal
- `GET /history/{mac}` - Historial

### ✅ Historial SQLite
- Batería vs tiempo
- Latencia vs tiempo
- Eventos de conexión
- Exportable a JSON

## 🔧 REQUISITOS

- Windows 10/11
- Python 3.11+
- Bluetooth habilitado
- Permisos de administrador (para Bluetooth)

## 📦 INSTALACIÓN DE DEPENDENCIAS

```powershell
pip install bleak fastapi uvicorn websockets pydantic
```

O usar el requirements.txt:

```powershell
pip install -r api/requirements.txt
```

## 🎮 USO BÁSICO

1. **Inicia el sistema**:
   ```powershell
   .\start.ps1
   ```

2. **Abre el navegador**: http://localhost:8080

3. **Pon tu mando en modo emparejamiento**:
   - Joy-Con: Botón SYNC por 3 segundos
   - DS4/DS5: Share + PS por 3 segundos

4. **Haz clic en "Scan Devices"**

5. **Haz clic en "Connect"** en tu dispositivo

6. **¡Disfruta del monitoreo en tiempo real!**

## 🐛 SOLUCIÓN DE PROBLEMAS

### El mando se desconecta constantemente
```powershell
# Ejecuta como Administrador:
Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File "C:\Users\teamp\Documents\joys\solucion-permanente.ps1"'
```

### No se detectan dispositivos
1. Verifica que Bluetooth esté encendido
2. Pon el mando en modo emparejamiento
3. Haz clic en "Reset Bluetooth" en el frontend

### Error de permisos
Ejecuta PowerShell como Administrador

### El overlay no aparece
```powershell
pip install tk
python backend/overlay.py
```

## 📊 CARACTERÍSTICAS TÉCNICAS

- **Latencia**: Medición real de paquetes HID
- **Batería**: Lectura directa de HID reports
- **Señal**: RSSI de stack Bluetooth
- **Actualizaciones**: WebSocket en tiempo real
- **Base de datos**: SQLite local
- **Frontend**: Vanilla JS + Tailwind + Chart.js
- **Backend**: Python + Bleak + FastAPI
- **Arquitectura**: Modular y extensible

## 🎯 PRÓXIMOS PASOS

1. **Personaliza** los intervalos de actualización en `api/main.py`
2. **Agrega** soporte para más controladores en `bluetooth_manager.py`
3. **Crea** alertas de batería baja
4. **Exporta** datos a CSV para análisis
5. **Desarrolla** una app móvil nativa

## 📞 SOPORTE

Revisa la documentación completa en:
- `README.md` - Información general
- `docs/QUICKSTART.md` - Guía rápida
- `docs/ARCHITECTURE.md` - Detalles técnicos

## 🎉 ¡LISTO PARA USAR!

El sistema está completamente funcional y listo para monitorear tus mandos en tiempo real.

**¡Disfruta del control total sobre tus Joy-Cons y otros controladores!** 🎮✨
