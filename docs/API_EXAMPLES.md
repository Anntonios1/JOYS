# API Examples

## Ejemplos de uso de la API con curl y PowerShell

### 1. Escanear dispositivos

**curl:**
```bash
curl -X POST http://localhost:8000/scan
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/scan" -Method Post
```

### 2. Listar todos los dispositivos

**curl:**
```bash
curl http://localhost:8000/devices
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/devices"
```

### 3. Listar solo dispositivos conectados

**curl:**
```bash
curl http://localhost:8000/devices/connected
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/devices/connected"
```

### 4. Conectar un dispositivo

**curl:**
```bash
curl -X POST http://localhost:8000/connect \
  -H "Content-Type: application/json" \
  -d '{"mac_address":"XX:XX:XX:XX:XX:XX"}'
```

**PowerShell:**
```powershell
$body = @{
    mac_address = "XX:XX:XX:XX:XX:XX"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/connect" -Method Post -Body $body -ContentType "application/json"
```

### 5. Desconectar un dispositivo

**curl:**
```bash
curl -X POST http://localhost:8000/disconnect \
  -H "Content-Type: application/json" \
  -d '{"mac_address":"XX:XX:XX:XX:XX:XX"}'
```

**PowerShell:**
```powershell
$body = @{
    mac_address = "XX:XX:XX:XX:XX:XX"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/disconnect" -Method Post -Body $body -ContentType "application/json"
```

### 6. Obtener nivel de batería

**curl:**
```bash
curl http://localhost:8000/battery/XX:XX:XX:XX:XX:XX
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/battery/XX:XX:XX:XX:XX:XX"
```

**Respuesta:**
```json
{
  "percentage": 85,
  "level": "FULL",
  "charging": false,
  "voltage": 3.7
}
```

### 7. Obtener estadísticas de latencia

**curl:**
```bash
curl http://localhost:8000/latency/XX:XX:XX:XX:XX:XX
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/latency/XX:XX:XX:XX:XX:XX"
```

**Respuesta:**
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

### 8. Obtener intensidad de señal

**curl:**
```bash
curl http://localhost:8000/signal/XX:XX:XX:XX:XX:XX
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/signal/XX:XX:XX:XX:XX:XX"
```

**Respuesta:**
```json
{
  "rssi": -65,
  "quality": "Good"
}
```

### 9. Obtener historial completo

**curl:**
```bash
curl http://localhost:8000/history/XX:XX:XX:XX:XX:XX
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/history/XX:XX:XX:XX:XX:XX"
```

### 10. Obtener solo historial de batería

**curl:**
```bash
curl "http://localhost:8000/history/XX:XX:XX:XX:XX:XX?data_type=battery"
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/history/XX:XX:XX:XX:XX:XX?data_type=battery"
```

### 11. Reiniciar stack Bluetooth

**curl:**
```bash
curl -X POST http://localhost:8000/reset_bluetooth
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/reset_bluetooth" -Method Post
```

## Script PowerShell Completo

```powershell
# Script de ejemplo completo
$API_URL = "http://localhost:8000"

# 1. Escanear dispositivos
Write-Host "Escaneando dispositivos..." -ForegroundColor Yellow
$scanResult = Invoke-RestMethod -Uri "$API_URL/scan" -Method Post
Write-Host "Encontrados: $($scanResult.devices.Count) dispositivos" -ForegroundColor Green

# 2. Listar dispositivos
$devices = Invoke-RestMethod -Uri "$API_URL/devices"
foreach ($device in $devices) {
    Write-Host "`nDispositivo: $($device.name)" -ForegroundColor Cyan
    Write-Host "  MAC: $($device.mac_address)"
    Write-Host "  Tipo: $($device.controller_type)"
    Write-Host "  Conectado: $($device.connected)"
}

# 3. Conectar al primer Joy-Con encontrado
$joycon = $devices | Where-Object { $_.controller_type -like "*Joy-Con*" } | Select-Object -First 1

if ($joycon) {
    Write-Host "`nConectando a $($joycon.name)..." -ForegroundColor Yellow
    
    $connectBody = @{
        mac_address = $joycon.mac_address
    } | ConvertTo-Json
    
    $connectResult = Invoke-RestMethod -Uri "$API_URL/connect" -Method Post -Body $connectBody -ContentType "application/json"
    Write-Host "Conectado exitosamente!" -ForegroundColor Green
    
    # Esperar un poco para que se estabilice
    Start-Sleep -Seconds 3
    
    # 4. Obtener batería
    Write-Host "`nObteniendo nivel de batería..." -ForegroundColor Yellow
    try {
        $battery = Invoke-RestMethod -Uri "$API_URL/battery/$($joycon.mac_address)"
        Write-Host "  Batería: $($battery.percentage)%" -ForegroundColor Green
        Write-Host "  Nivel: $($battery.level)"
        Write-Host "  Cargando: $($battery.charging)"
    } catch {
        Write-Host "  No se pudo obtener la batería" -ForegroundColor Red
    }
    
    # 5. Obtener latencia
    Write-Host "`nObteniendo latencia..." -ForegroundColor Yellow
    try {
        $latency = Invoke-RestMethod -Uri "$API_URL/latency/$($joycon.mac_address)"
        Write-Host "  Latencia actual: $($latency.current_ms) ms" -ForegroundColor Green
        Write-Host "  Promedio: $($latency.average_ms) ms"
        Write-Host "  Jitter: $($latency.jitter_ms) ms"
        Write-Host "  Pérdida de paquetes: $($latency.packet_loss)%"
    } catch {
        Write-Host "  No se pudo obtener la latencia" -ForegroundColor Red
    }
    
    # 6. Obtener señal
    Write-Host "`nObteniendo señal..." -ForegroundColor Yellow
    try {
        $signal = Invoke-RestMethod -Uri "$API_URL/signal/$($joycon.mac_address)"
        Write-Host "  RSSI: $($signal.rssi) dBm" -ForegroundColor Green
        Write-Host "  Calidad: $($signal.quality)"
    } catch {
        Write-Host "  No se pudo obtener la señal" -ForegroundColor Red
    }
    
    # 7. Esperar y luego desconectar
    Write-Host "`nPresiona Enter para desconectar..." -ForegroundColor Yellow
    Read-Host
    
    $disconnectBody = @{
        mac_address = $joycon.mac_address
    } | ConvertTo-Json
    
    Invoke-RestMethod -Uri "$API_URL/disconnect" -Method Post -Body $disconnectBody -ContentType "application/json"
    Write-Host "Desconectado" -ForegroundColor Green
} else {
    Write-Host "`nNo se encontró ningún Joy-Con" -ForegroundColor Red
}
```

## WebSocket con JavaScript

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
    console.log('Conectado al servidor');
    ws.send('ping'); // Test de conexión
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'battery_update':
            console.log(`Batería actualizada: ${data.battery.percentage}%`);
            break;
        case 'latency_update':
            console.log(`Latencia: ${data.latency.current_ms} ms`);
            break;
        case 'device_connected':
            console.log(`Dispositivo conectado: ${data.mac_address}`);
            break;
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('Desconectado del servidor');
};
```

## Python Client Example

```python
import requests
import json

API_URL = "http://localhost:8000"

# Escanear dispositivos
response = requests.post(f"{API_URL}/scan")
devices = response.json()["devices"]

print(f"Encontrados {len(devices)} dispositivos")

# Conectar al primer dispositivo
if devices:
    mac_address = devices[0]["mac_address"]
    
    # Conectar
    response = requests.post(
        f"{API_URL}/connect",
        json={"mac_address": mac_address}
    )
    print(f"Conectado: {response.json()}")
    
    # Obtener batería
    response = requests.get(f"{API_URL}/battery/{mac_address}")
    battery = response.json()
    print(f"Batería: {battery['percentage']}%")
    
    # Obtener latencia
    response = requests.get(f"{API_URL}/latency/{mac_address}")
    latency = response.json()
    print(f"Latencia: {latency['current_ms']} ms")
```
