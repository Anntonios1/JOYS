# Quick Start Guide

## Windows (Local)

### 1. Instalar Dependencias

```powershell
cd C:\Users\teamp\Documents\joys\gamepad-monitor
pip install -r api/requirements.txt
```

### 2. Iniciar API

```powershell
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Abrir Frontend

```powershell
# Opción A: Servidor Python simple
python -m http.server 8080 -d frontend

# Opción B: Abrir index.html directamente en navegador
start frontend/index.html
```

### 4. Conectar Mandos

1. Pon tu Joy-Con/mando en modo emparejamiento
2. En el navegador ve a `http://localhost:8080`
3. Haz clic en "Scan Devices"
4. Haz clic en "Connect" en tu dispositivo

## Docker

```powershell
cd C:\Users\teamp\Documents\joys\gamepad-monitor
docker-compose up -d
```

Accede a `http://localhost:8080`

## Overlay Windows

```powershell
python backend/overlay.py
```

## URLs

- Frontend: `http://localhost:8080`
- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- WebSocket: `ws://localhost:8000/ws`

## Comandos Útiles

### Ver dispositivos conectados
```powershell
curl http://localhost:8000/devices/connected
```

### Escanear nuevos dispositivos
```powershell
curl -X POST http://localhost:8000/scan
```

### Ver batería de un dispositivo
```powershell
curl http://localhost:8000/battery/XX:XX:XX:XX:XX:XX
```

### Reiniciar Bluetooth
```powershell
curl -X POST http://localhost:8000/reset_bluetooth
```

## Troubleshooting Rápido

### Error: ModuleNotFoundError
```powershell
pip install bleak fastapi uvicorn websockets
```

### Error: Bluetooth no funciona
```powershell
# Como Administrador:
Restart-Service bthserv
```

### Mando se desconecta
```powershell
# Ejecuta como Admin:
.\solucion-permanente.ps1
```
