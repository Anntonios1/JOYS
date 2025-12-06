# Architecture Documentation

## System Overview

```
┌──────────────────┐
│   Web Browser    │
│   (Frontend)     │
└────────┬─────────┘
         │ HTTP/WS
         ▼
┌──────────────────┐
│   FastAPI        │
│   (API Layer)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│         Backend Modules                   │
│  ┌────────────┐  ┌─────────────────┐    │
│  │ Bluetooth  │  │  Battery        │    │
│  │ Manager    │  │  Monitor        │    │
│  └────────────┘  └─────────────────┘    │
│  ┌────────────┐  ┌─────────────────┐    │
│  │ Latency    │  │  History        │    │
│  │ Monitor    │  │  Manager        │    │
│  └────────────┘  └─────────────────┘    │
└───────────┬──────────────────────────────┘
            │ BLE/HID
            ▼
┌──────────────────────┐
│  Game Controllers    │
│  Joy-Con, DS4, DS5   │
└──────────────────────┘
```

## Data Flow

### 1. Device Connection

```
User → Frontend → API → Bluetooth Manager → BLE Stack → Controller
```

### 2. Data Collection

```
Controller → HID Reports → Latency Monitor → API → WebSocket → Frontend
                        ↘ Battery Monitor ↗
                        ↘ History Manager (SQLite)
```

### 3. Real-time Updates

```
WebSocket Connection:
  Frontend ←→ API ←→ Backend Modules
  
  Updates every 5 seconds:
  - Battery level
  - Latency stats
  - Signal strength
```

## Module Details

### Bluetooth Manager
- **Purpose**: Handle BLE connections
- **Dependencies**: bleak, asyncio
- **Key Methods**:
  - `scan_devices()`: Discover controllers
  - `connect()`: Establish connection
  - `disconnect()`: Clean disconnection
  - `force_disconnect()`: Windows-specific forceful disconnect

### Battery Monitor
- **Purpose**: Read battery from HID reports
- **Protocol Support**:
  - Joy-Con: 4-level indicator
  - DS4: 8-level percentage
  - DS5: 100% granular + charging state
- **Key Methods**:
  - `read_battery()`: Generic read
  - `read_joycon_battery()`: Nintendo-specific
  - `read_ds4_battery()`: PS4-specific
  - `read_ds5_battery()`: PS5-specific

### Latency Monitor
- **Purpose**: Measure input lag
- **Metrics**:
  - Current latency (ms)
  - Average, min, max
  - Jitter (standard deviation)
  - Packet loss percentage
- **Method**: Parse HID report timestamps

### History Manager
- **Purpose**: Persist data to SQLite
- **Tables**:
  - `battery_history`: timestamp, mac, %, charging
  - `latency_history`: timestamp, mac, ms, jitter
  - `connection_events`: timestamp, mac, event_type

## API Architecture

### FastAPI Application

```python
app = FastAPI()

# Middleware
- CORS (allow all origins)

# Endpoints
- REST: /devices, /connect, /battery, etc.
- WebSocket: /ws

# Background Tasks
- monitoring_loop(): Continuous data collection
```

### WebSocket Protocol

```json
// Client → Server
{
  "type": "ping"
}

// Server → Client
{
  "type": "battery_update",
  "mac_address": "XX:XX:XX:XX:XX:XX",
  "battery": {
    "percentage": 85,
    "level": "FULL",
    "charging": false
  }
}
```

## Frontend Architecture

### Technologies
- Vanilla JavaScript (no frameworks)
- Tailwind CSS
- Chart.js for graphs

### Components
- DeviceCard: Individual controller display
- LatencyChart: Real-time graph
- ConnectionStatus: WebSocket indicator
- ScanButton: Trigger device discovery

### State Management
```javascript
{
  devices: {},          // All discovered devices
  charts: {},           // Chart.js instances
  ws: WebSocket,        // WebSocket connection
  monitoringIntervals: {} // Update intervals
}
```

## Database Schema

### battery_history
```sql
CREATE TABLE battery_history (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    mac_address TEXT NOT NULL,
    percentage INTEGER NOT NULL,
    charging BOOLEAN NOT NULL,
    voltage REAL
);
```

### latency_history
```sql
CREATE TABLE latency_history (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    mac_address TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    jitter_ms REAL NOT NULL,
    packet_loss REAL NOT NULL
);
```

### connection_events
```sql
CREATE TABLE connection_events (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    mac_address TEXT NOT NULL,
    event_type TEXT NOT NULL,
    controller_name TEXT NOT NULL
);
```

## Performance Considerations

### Latency Measurement
- Ring buffer: 100 samples max
- Update frequency: Per HID report (~100Hz)
- Calculation: Rolling statistics

### Battery Polling
- Frequency: 5 seconds
- Caching: Last known value
- Write to DB: Every read

### WebSocket Broadcasting
- Fan-out to all connected clients
- Non-blocking send with error handling
- Automatic reconnection on client side

## Security Considerations

### API
- No authentication (local network only)
- CORS: Allow all (development mode)
- No rate limiting (trusted environment)

### Bluetooth
- Privileged access required
- Direct HID communication
- No encryption beyond BLE pairing

## Deployment Options

### Local (Development)
```
uvicorn + Python HTTP server
```

### Docker (Production)
```
Docker Compose:
  - API container (Python + FastAPI)
  - Frontend container (Nginx)
```

### Windows Service
```
nssm install GamepadMonitor "python.exe" "api/main.py"
```

## Extension Points

### Add New Controller
1. Add identifier in `bluetooth_manager.py`
2. Implement battery parser in `battery_monitor.py`
3. Test HID report format

### Add New Metric
1. Create monitor module in `backend/modules/`
2. Add API endpoint in `api/main.py`
3. Add display in `frontend/app.js`

### Add Notification System
1. Create `notification_manager.py`
2. Hook into battery/latency monitors
3. Send alerts via WebSocket or email
