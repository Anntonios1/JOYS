"""
FastAPI Server - API REST para gamepad monitoring
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Dict
import asyncio
import uvicorn
from datetime import datetime
import os

from device_manager import DeviceManager
from models.device_models import DeviceInfo, VibrateRequest, ErrorResponse
from db_manager import DatabaseManager, get_battery_state, get_battery_profile, BATTERY_PROFILES
from alert_manager import AlertManager
from battery_scheduler import BatteryScheduler
from battery_intelligence_db import get_persistent_battery_manager


app = FastAPI(
    title="Gamepad Monitor API",
    description="API para monitoreo de Joy-Cons, DualShock 4 y Xbox Controllers",
    version="2.0.0"
)

# CORS para permitir acceso desde frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base de datos
db_manager = DatabaseManager("gamepad_monitor.db")

# Gestor de dispositivos
device_manager = DeviceManager(db_manager=db_manager)

# Gestor de alertas
alert_manager = AlertManager()

# Gestor de inteligencia de batería (voltaje, ciclos, SoH)
battery_intelligence = get_persistent_battery_manager("gamepad_monitor.db")

# WebSocket connections activas
active_websockets: List[WebSocket] = []

# Cache de estados de batería anteriores (para detectar cambios)
previous_battery_states: Dict[str, str] = {}

# Scheduler de batería (se inicializa en startup)
battery_scheduler: BatteryScheduler = None

# Servir frontend estático
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
print(f"Frontend path: {frontend_path}")
print(f"Frontend exists: {os.path.exists(frontend_path)}")

if os.path.exists(frontend_path):
    app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")
    print("✓ Frontend montado en /frontend")


@app.get("/")
async def root():
    """Endpoint raíz - redirige al frontend"""
    if os.path.exists(frontend_path):
        index_file = os.path.join(frontend_path, 'index_pro.html')
        if os.path.exists(index_file):
            return FileResponse(index_file)
    return {
        "message": "Gamepad Monitor API v2.0",
        "docs": "/docs",
        "devices_count": len(device_manager.devices),
        "timestamp": datetime.now().isoformat(),
        "frontend_path": frontend_path if 'frontend_path' in locals() else "Not configured"
    }


@app.on_event("startup")
async def startup_event():
    """Escanear dispositivos e iniciar scheduler al iniciar"""
    global battery_scheduler
    
    print("Gamepad Monitor API v2.0 iniciando...")
    device_manager.scan_devices()
    print(f"{len(device_manager.devices)} dispositivo(s) detectado(s)")
    
    # Callback cuando se detecta un nuevo dispositivo
    async def on_device_connected(data):
        """Callback cuando se conecta un nuevo dispositivo"""
        print(f"📡 Enviando evento device_connected: {data['device_id']}")
        for ws in active_websockets:
            try:
                await ws.send_json({
                    "type": "device_connected",
                    "data": data
                })
            except:
                pass
    
    # Callback cuando se desconecta un dispositivo (desde scanner)
    async def on_device_disconnected_scanner(data):
        """Callback cuando se desconecta un dispositivo (detector rápido)"""
        print(f"📡 Enviando evento device_disconnected: {data['device_id']}")
        for ws in active_websockets:
            try:
                await ws.send_json({
                    "type": "device_disconnected",
                    "data": data
                })
            except:
                pass
    
    # Configurar callbacks del device manager para detección rápida
    device_manager.set_callbacks(
        on_connected=on_device_connected,
        on_disconnected=on_device_disconnected_scanner
    )
    
    # Iniciar scanner de dispositivos en background (detección rápida)
    asyncio.create_task(device_manager.start_background_scanner(interval=1.0))
    print("🔍 Scanner de dispositivos iniciado (intervalo: 1s)")
    
    # Iniciar el scheduler de batería
    async def on_battery_update(data):
        """Callback cuando se actualiza la batería - notifica via WebSocket"""
        for ws in active_websockets:
            try:
                await ws.send_json({
                    "type": "battery_update",
                    "data": data
                })
            except:
                pass
    
    async def on_disconnect(data):
        """Callback cuando se desconecta un dispositivo"""
        for ws in active_websockets:
            try:
                await ws.send_json({
                    "type": "device_disconnected",
                    "data": data
                })
            except:
                pass
    
    async def on_reconnect(data):
        """Callback cuando se reconecta un dispositivo"""
        for ws in active_websockets:
            try:
                await ws.send_json({
                    "type": "device_reconnected",
                    "data": data
                })
            except:
                pass
    
    async def on_charging_change(data):
        """Callback cuando cambia el estado de carga"""
        for ws in active_websockets:
            try:
                await ws.send_json({
                    "type": "charging_change",
                    "data": data
                })
            except:
                pass
    
    battery_scheduler = BatteryScheduler(
        device_manager=device_manager,
        db_manager=db_manager,
        on_battery_update=on_battery_update,
        on_device_disconnect=on_disconnect,
        on_device_reconnect=on_reconnect
    )
    battery_scheduler.on_charging_change = on_charging_change
    await battery_scheduler.start()
    print("🔋 BatteryScheduler iniciado (intervalo: 2 minutos)")


@app.on_event("shutdown")
async def shutdown_event():
    """Limpiar al cerrar"""
    global battery_scheduler
    
    print("Cerrando servidor...")
    
    # Detener el scanner de dispositivos
    device_manager.stop_background_scanner()
    
    # Detener el scheduler
    if battery_scheduler:
        await battery_scheduler.stop()
    
    # Marcar todos los dispositivos como desconectados
    for device_id in list(device_manager.devices.keys()):
        db_manager.mark_device_disconnected(device_id)
    
    # No desconectar dispositivos al cerrar el servidor
    # Los dispositivos permanecerán conectados


@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "Gamepad Monitor API v2.0",
        "docs": "/docs",
        "devices_count": len(device_manager.devices),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/devices", response_model=List[dict])
async def get_devices():
    """
    Obtener lista de todos los dispositivos conectados
    
    Returns:
        Lista de dispositivos con información básica
    """
    try:
        # Refrescar dispositivos antes de devolver la lista (detectar nuevos, remover desconectados)
        device_manager.refresh_devices()
        devices = device_manager.get_device_list()
        return devices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/buttons")
async def get_buttons():
    """
    Obtener el estado de los botones de todos los Joy-Cons conectados
    
    Returns:
        Dict con {device_id: {button_name: pressed}}
    """
    try:
        buttons = device_manager.get_all_buttons()
        return buttons
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/device/{device_id}", response_model=DeviceInfo)
async def get_device_info(device_id: str):
    """
    Obtener información completa de un dispositivo específico
    
    Args:
        device_id: ID del dispositivo
    
    Returns:
        DeviceInfo con toda la información del dispositivo
    """
    try:
        print(f"\n📡 GET /api/device/{device_id}")
        info = device_manager.get_device_info(device_id)
        if not info:
            print(f"❌ get_device_info retornó None para {device_id}")
            raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} no encontrado")
        
        # Guardar métricas dinámicas en DB (cada 2 minutos)
        if info.battery and info.polling:
            # Verificar última métrica guardada
            last_metric = db_manager.get_latest_metrics(device_id)
            should_save = False
            
            if not last_metric:
                # Primera vez, guardar
                should_save = True
            else:
                # Verificar si han pasado 2 minutos
                from datetime import datetime
                last_time = datetime.fromisoformat(last_metric['timestamp'])
                now = datetime.now()
                minutes_elapsed = (now - last_time).total_seconds() / 60
                
                if minutes_elapsed >= 2:
                    should_save = True
            
            if should_save:
                db_manager.save_device_metrics(
                    device_id=device_id,
                    battery_level=info.battery.percentage if info.battery else None,
                    polling_rate=info.polling.rate_hz if info.polling else None
                )
                print(f"   💾 Métricas guardadas: Batería={info.battery.percentage}%, Polling={info.polling.rate_hz}Hz")
            else:
                print(f"   ⏭️ Métricas no guardadas (esperando 2 min)")
        
        # Obtener tiempo de uso para incluir en la respuesta
        usage_data = db_manager.get_usage_time(device_id)
        if usage_data:
            info.usage_time_hours = usage_data['duration_hours']
            info.usage_time_minutes = usage_data['duration_minutes']
            info.battery_consumed = usage_data['battery_consumed']
            info.estimated_autonomy_hours = usage_data['estimated_autonomy_hours']
        
        # Agregar smart_battery a la respuesta (con cache de 5 minutos)
        response_data = info.model_dump(mode='json')
        print(f"   🔋 battery.percentage: {info.battery.percentage if info.battery else 'None'}")
        if info.battery and info.battery.percentage is not None:
            try:
                print(f"   🔍 Obteniendo smart_battery...")
                # Intentar obtener desde cache primero
                smart_status = device_manager.cache.get(device_id, 'smart_battery')
                if not smart_status:
                    print(f"   💾 No hay caché, calculando...")
                    # Si no está en cache o expiró, calcular
                    smart_status = db_manager.get_smart_battery_status(
                        device_id=device_id,
                        current_battery=info.battery.percentage,
                        device_type=info.type or "unknown"
                    )
                    # Guardar en cache (TTL de 5 minutos)
                    device_manager.cache.set(device_id, 'smart_battery', smart_status)
                else:
                    print(f"   ✅ Usando caché")
                response_data['smart_battery'] = smart_status
                print(f"   ✅ smart_battery asignado: {smart_status}")
                
                # === BATTERY INTELLIGENCE: Datos avanzados ===
                try:
                    # Procesar lectura con sistema de inteligencia
                    raw_data = {
                        "voltage": info.battery.voltage,
                        "temperature": getattr(info.battery, 'temperature', None),
                        "charging": info.battery.charging,
                        "level": info.battery.percentage // 25,  # Para DS4/DS5
                        "percentage": info.battery.percentage
                    }
                    
                    bi_state = battery_intelligence.process_reading(
                        device_id, info.type or "unknown", raw_data
                    )
                    
                    # Obtener conteo de cargas desde historial
                    charge_stats = battery_intelligence.get_charge_count(device_id)
                    
                    # Agregar datos de inteligencia al smart_battery
                    response_data['smart_battery']['intelligence'] = {
                        'soc_precise': round(bi_state.current_reading.soc_percent, 1),
                        'equivalent_cycles': round(bi_state.health.equivalent_cycles, 2),
                        'soh_percent': bi_state.health.soh_percent,
                        'health_status': bi_state.health.health_status,
                        'internal_resistance_mohm': bi_state.health.internal_resistance_mohm,
                        'confidence': bi_state.health.confidence,
                        'data_points': bi_state.health.data_points,
                        'has_voltage_data': info.battery.voltage is not None,
                        'total_charges': charge_stats.get('total_charges', 0),
                        'full_charges': charge_stats.get('full_charges', 0),
                        'last_charge': charge_stats.get('last_charge')
                    }
                except Exception as bi_error:
                    print(f"⚠️ Error en battery_intelligence: {bi_error}")
                    import traceback
                    traceback.print_exc()
                    
            except Exception as e:
                print(f"⚠️ Error obteniendo smart_battery: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"✅ Info obtenida correctamente")
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Excepción: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/device/{device_id}/vibrate")
async def vibrate_device(device_id: str, request: VibrateRequest):
    """
    Hacer vibrar un dispositivo
    
    Args:
        device_id: ID del dispositivo
        request: Parámetros de vibración (duration, intensity)
    
    Returns:
        Confirmación de vibración
    """
    try:
        success = device_manager.vibrate_device(
            device_id,
            duration=request.duration,
            intensity=request.intensity
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} no encontrado")
        
        return {
            "success": True,
            "device_id": device_id,
            "duration": request.duration,
            "intensity": request.intensity,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/device/{device_id}/disconnect")
async def disconnect_device(device_id: str):
    """
    Desconectar un dispositivo (intenta apagarlo si es Bluetooth)
    
    Para Joy-Con: Envía comando de apagado → se apaga y desconecta
    Para DS4/DS5 Bluetooth: Intenta enviar power off → puede reconectarse
    Para DS4/DS5 USB: Solo cierra HID → hay que desenchufar físicamente
    
    Args:
        device_id: ID del dispositivo
    
    Returns:
        Confirmación de desconexión con notas sobre comportamiento
    """
    try:
        reader = device_manager.devices.get(device_id)
        if not reader:
            raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} no encontrado")
        
        device_type = device_manager.device_info.get(device_id, {}).get('type', 'Unknown')
        device_name = device_manager.device_info.get(device_id, {}).get('name', device_id)
        connection_type = reader.get_connection_type() if hasattr(reader, 'get_connection_type') else 'Unknown'
        
        # Determinar tipo de dispositivo
        is_joycon = 'joycon' in device_type.lower() or 'joy-con' in device_type.lower()
        is_ds4 = 'dualshock' in device_type.lower() or 'ds4' in device_id.lower()
        is_ds5 = 'dualsense' in device_type.lower() or 'ds5' in device_id.lower()
        is_ds = is_ds4 or is_ds5
        is_bluetooth = 'bluetooth' in connection_type.lower() or 'bt' in connection_type.lower()
        is_usb = 'usb' in connection_type.lower()
        
        # Preparar mensaje según tipo
        if is_usb:
            note = "Conexión HID cerrada. Para desconectar completamente, desenchufa el cable USB."
            will_reconnect = False
        elif is_bluetooth and is_ds:
            note = "Se envió comando de apagado. Si el mando sigue encendido, mantén PS+Share por 10 segundos para apagarlo manualmente, o usa Desemparejar."
            will_reconnect = True  # Puede reconectarse si no se apaga
        elif is_joycon:
            note = "Joy-Con apagado correctamente."
            will_reconnect = False
        else:
            note = "Dispositivo desconectado."
            will_reconnect = is_bluetooth
        
        # Intentar desconexión graceful (envía power off para Bluetooth)
        success = device_manager.disconnect_device_gracefully(device_id, power_off=True)
        
        if not success:
            # Fallback: desconexión directa sin power off
            device_manager.disconnect_device(device_id)
            success = True
        
        # Notificar a los clientes WebSocket sobre la desconexión manual
        print(f"📢 Notificando desconexión manual de {device_id} via WebSocket...")
        for ws in active_websockets:
            try:
                await ws.send_json({
                    "type": "device_disconnected",
                    "data": {
                        "device_id": device_id,
                        "reason": "manual_disconnect",
                        "timestamp": datetime.now().isoformat()
                    }
                })
            except Exception as e:
                print(f"Error enviando notificación WebSocket: {e}")
        
        return {
            "success": True,
            "device_id": device_id,
            "device_type": device_type,
            "device_name": device_name,
            "connection_type": connection_type,
            "message": f"{device_name} desconectado",
            "note": note,
            "will_reconnect": will_reconnect,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/device/{device_id}/bluetooth-disconnect")
async def bluetooth_disconnect_device(device_id: str):
    """
    Desconectar un dispositivo del Bluetooth de Windows (sin desemparejar)
    
    Esto fuerza la desconexión a nivel de Bluetooth, no solo HID.
    El dispositivo permanece emparejado y puede reconectarse.
    
    Args:
        device_id: ID del dispositivo
    
    Returns:
        Confirmación de desconexión Bluetooth
    """
    try:
        from bluetooth_manager import BluetoothManager
        
        reader = device_manager.devices.get(device_id)
        if not reader:
            raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} no encontrado")
        
        device_type = device_manager.device_info.get(device_id, {}).get('type', 'Unknown')
        device_name = device_manager.device_info.get(device_id, {}).get('name', device_id)
        
        # Paso 1: Desconectar del HID primero
        print(f"🔌 Desconectando {device_name} del HID...")
        device_manager.disconnect_device(device_id)
        
        await asyncio.sleep(0.5)
        
        # Paso 2: Buscar el dispositivo en Bluetooth por nombre/tipo
        print(f"🔍 Buscando {device_name} en dispositivos Bluetooth...")
        all_bt_devices = await BluetoothManager.find_all_bluetooth_devices()
        
        # Determinar el nombre Bluetooth a buscar
        bt_name_patterns = []
        if 'joycon' in device_type.lower() or 'joy-con' in device_type.lower():
            # Para Joy-Con, necesitamos el lado (L o R)
            if hasattr(reader, 'side'):
                bt_name_patterns.append(f"Joy-Con ({reader.side})")
            else:
                bt_name_patterns.extend(["Joy-Con (L)", "Joy-Con (R)"])
        elif 'dualsense' in device_type.lower():
            bt_name_patterns.append("DualSense Wireless Controller")
        elif 'dualshock' in device_type.lower() or 'ds4' in device_type.lower():
            bt_name_patterns.append("Wireless Controller")
        elif 'xbox' in device_type.lower():
            bt_name_patterns.append("Xbox Wireless Controller")
        else:
            bt_name_patterns.append(device_name)
        
        # Buscar dispositivo Bluetooth que coincida
        target_device = None
        for bt_dev in all_bt_devices:
            for pattern in bt_name_patterns:
                if pattern.lower() in bt_dev["name"].lower() and "BluetoothDevice" in bt_dev["id"]:
                    target_device = bt_dev
                    break
            if target_device:
                break
        
        if not target_device:
            return {
                "success": True,
                "device_id": device_id,
                "device_type": device_type,
                "message": f"{device_name} desconectado del HID. No se encontró en Bluetooth (puede que ya esté desconectado).",
                "bluetooth_found": False,
                "timestamp": datetime.now().isoformat()
            }
        
        # Paso 3: Obtener el BluetoothDevice para verificar estado
        print(f"📡 Dispositivo Bluetooth encontrado: {target_device['name']}")
        
        # Nota: Windows no tiene una API directa para "desconectar sin desemparejar"
        # La desconexión HID ya debería haber cerrado la conexión
        # Lo que podemos hacer es verificar el estado
        
        import re
        mac_match = re.search(r'([0-9A-Fa-f]{12})', target_device["id"])
        if mac_match:
            mac_str = mac_match.group(1)
            mac_formatted = ':'.join([mac_str[i:i+2] for i in range(0, 12, 2)])
            
            return {
                "success": True,
                "device_id": device_id,
                "device_type": device_type,
                "device_name": device_name,
                "bluetooth_name": target_device["name"],
                "bluetooth_mac": mac_formatted,
                "message": f"{device_name} desconectado. El emparejamiento se mantiene.",
                "note": "El dispositivo puede reconectarse presionando un botón.",
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "success": True,
            "device_id": device_id,
            "message": f"{device_name} desconectado",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/device/{device_id}/unpair")
async def unpair_device(device_id: str):
    """
    Desemparejar un dispositivo del Bluetooth de Windows
    
    Para Joy-Con:
    1. Envía comando de sleep/apagado (funciona perfectamente)
    2. Lo desempareja del sistema Bluetooth
    
    Para DS4/DS5:
    1. Desconecta del HID y añade cooldown
    2. Intenta desemparejar (puede requerir apagar manualmente el mando)
    
    Args:
        device_id: ID del dispositivo
    
    Returns:
        Confirmación de desemparejamiento
    """
    try:
        from bluetooth_manager import BluetoothManager
        
        reader = device_manager.devices.get(device_id)
        if not reader:
            raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} no encontrado")
        
        device_type = device_manager.device_info.get(device_id, {}).get('type', 'Unknown')
        device_name = device_manager.device_info.get(device_id, {}).get('name', device_id)
        connection_type = reader.get_connection_type() if hasattr(reader, 'get_connection_type') else 'Unknown'
        
        print(f"🔍 Unpair request - device_type: {device_type}, connection_type: {connection_type}")
        
        # Verificar que es Bluetooth
        # Joy-Cons SIEMPRE son Bluetooth, DS4/DS5 pueden ser USB
        is_joycon = 'joycon' in device_type.lower() or 'joy-con' in device_type.lower()
        is_ds = 'dual' in device_type.lower() or 'ds4' in device_id.lower() or 'ds5' in device_id.lower()
        
        # Para Joy-Con, asumir Bluetooth siempre
        # Para otros, verificar connection_type
        if is_joycon:
            is_bluetooth = True
        else:
            is_bluetooth = 'bluetooth' in connection_type.lower() or 'bt' in connection_type.lower()
        
        if not is_bluetooth:
            raise HTTPException(
                status_code=400,
                detail=f"El dispositivo está conectado por USB, no se puede desemparejar. Connection type: {connection_type}"
            )
        
        # Determinar nombre Bluetooth a buscar ANTES de desconectar
        bt_name_patterns = []
        if is_joycon and hasattr(reader, 'side'):
            bt_name_patterns.append(f"Joy-Con ({reader.side})")
        elif is_ds:
            if 'dualsense' in device_type.lower():
                bt_name_patterns.append("DualSense Wireless Controller")
            else:
                bt_name_patterns.append("Wireless Controller")
        else:
            bt_name_patterns.append(device_name)
        
        # Buscar dispositivo en Bluetooth ANTES de desconectar
        print(f"Buscando dispositivo Bluetooth con patrones: {bt_name_patterns}")
        all_bt_devices = await BluetoothManager.find_all_bluetooth_devices()
        
        target_device = None
        for bt_dev in all_bt_devices:
            for pattern in bt_name_patterns:
                if pattern.lower() in bt_dev["name"].lower() and "BluetoothDevice" in bt_dev["id"]:
                    target_device = bt_dev
                    break
            if target_device:
                break
        
        if not target_device:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró el dispositivo en el sistema Bluetooth"
            )
        
        print(f"Dispositivo encontrado: {target_device['name']} - {target_device['id']}")
        
        # Para Joy-Con: vibrar primero para identificar
        if is_joycon:
            print(f"Vibrando Joy-Con {device_id} por 2 segundos...")
            device_manager.vibrate_device(device_id, duration=2.0, intensity=0.8)
            await asyncio.sleep(2.5)
        
        # PASO CRÍTICO: Desconectar del HID y enviar power off
        print("Desconectando del HID con power off...")
        # Para Joy-Con esto envía el comando 0x06 que realmente lo apaga
        # Para DS4/DS5 intenta enviar power off (puede no funcionar)
        device_manager.disconnect_device_gracefully(device_id, power_off=True)
        
        # Añadir al cooldown para que no se reconecte
        device_manager._add_to_cooldown(device_id)
        
        # Esperar a que el dispositivo se desconecte completamente
        if is_ds:
            print("Esperando 3 segundos para que el DS4/DS5 se desconecte...")
            await asyncio.sleep(3.0)
        else:
            await asyncio.sleep(1.0)
        
        # Desemparejar
        print(f"Desemparejando: {target_device['id']}")
        unpair_result = await BluetoothManager.unpair_device(target_device['id'])
        
        # Extraer MAC para mostrar
        import re
        mac_match = re.search(r'([0-9A-Fa-f]{12})', target_device["id"])
        mac_formatted = ""
        if mac_match:
            mac_str = mac_match.group(1)
            mac_formatted = ':'.join([mac_str[i:i+2] for i in range(0, 12, 2)])
        
        # Para DS4/DS5, dar instrucciones adicionales si el unpair falló
        extra_note = ""
        if is_ds and not unpair_result["success"]:
            extra_note = " Para completar el desemparejamiento: 1) Apaga el mando (PS+Share 10s), 2) Ve a Configuración > Bluetooth y quítalo manualmente."
        
        if not unpair_result["success"]:
            return {
                "success": False,
                "device_id": device_id,
                "device_type": device_type,
                "device_name": device_name,
                "bluetooth_name": target_device["name"],
                "bluetooth_mac": mac_formatted,
                "message": f"No se pudo desemparejar completamente.{extra_note}",
                "details": unpair_result["message"],
                "requires_manual_action": is_ds,
                "timestamp": datetime.now().isoformat()
            }
        
        # Notificar a los clientes WebSocket que el dispositivo fue desemparejado
        print(f"📢 Notificando desemparejamiento de {device_id} via WebSocket...")
        for ws in active_websockets:
            try:
                await ws.send_json({
                    "type": "device_disconnected",
                    "data": {
                        "device_id": device_id,
                        "reason": "unpaired",
                        "timestamp": datetime.now().isoformat()
                    }
                })
            except Exception as e:
                print(f"Error enviando notificación WebSocket: {e}")
        
        return {
            "success": True,
            "device_id": device_id,
            "device_type": device_type,
            "device_name": device_name,
            "bluetooth_name": target_device["name"],
            "bluetooth_mac": mac_formatted,
            "message": f"{device_name} desemparejado correctamente",
            "details": unpair_result["message"],
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error inesperado: {str(e)}")


@app.post("/api/disconnect-all")
async def disconnect_all_devices():
    """
    Desconectar TODOS los dispositivos HID del stack (mantiene emparejamiento Bluetooth)
    
    Returns:
        Resumen de dispositivos desconectados
    """
    try:
        print("\n🔌 DESCONECTANDO TODOS LOS DISPOSITIVOS HID...")
        
        # Obtener todos los dispositivos conectados actualmente
        current_devices = device_manager.get_device_list()
        
        if not current_devices:
            print("   ℹ️ No hay dispositivos conectados")
            return {
                "success": True,
                "disconnected_count": 0,
                "message": "No hay dispositivos conectados",
                "timestamp": datetime.now().isoformat()
            }
        
        disconnected_count = 0
        failed_count = 0
        disconnected_list = []
        
        # Desconectar gracefully todos los dispositivos HID
        for device_info in current_devices:
            device_id = device_info.get('id')
            device_type = device_info.get('type', 'Unknown')
            device_name = f"{device_type} ({device_id})"
            
            print(f"   🔌 Desconectando {device_name}...")
            
            try:
                # Intentar desconexión graceful (Joy-Con), sino forzar desconexión
                success = device_manager.disconnect_device_gracefully(device_id)
                if not success:
                    # Para DS4/Xbox, usar desconexión directa
                    device_manager.disconnect_device(device_id)
                    success = True
                
                if success:
                    disconnected_count += 1
                    disconnected_list.append(device_name)
                    print(f"   ✅ {device_name} desconectado")
                else:
                    failed_count += 1
                    print(f"   ⚠️ No se pudo desconectar {device_name}")
            except Exception as e:
                failed_count += 1
                print(f"   ❌ Error desconectando {device_name}: {e}")
        
        await asyncio.sleep(0.5)  # Pequeña pausa para que se procesen las desconexiones
        
        print(f"\n✅ Proceso completado: {disconnected_count} desconectados, {failed_count} fallidos\n")
        
        return {
            "success": True,
            "disconnected_count": disconnected_count,
            "failed_count": failed_count,
            "disconnected_devices": disconnected_list,
            "total_found": len(current_devices),
            "message": f"Desconectados {disconnected_count} de {len(current_devices)} dispositivos",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al desconectar todos: {str(e)}")


@app.post("/api/unpair-all")
async def unpair_all_devices():
    """
    Desemparejar TODOS los dispositivos HID del Bluetooth de Windows
    
    Returns:
        Resumen de dispositivos desemparejados
    """
    try:
        from bluetooth_manager import BluetoothManager
        
        print("\n🗑️ DESEMPAREJANDO TODOS LOS DISPOSITIVOS BLUETOOTH HID...")
        
        # Paso 1: Desconectar todos los dispositivos HID activos primero
        print("   📌 Paso 1: Desconectando dispositivos activos...")
        current_devices = device_manager.get_device_list()
        
        for device_info in current_devices:
            device_id = device_info.get('id')
            device_type = device_info.get('type', 'Unknown')
            
            print(f"      🔌 Desconectando {device_type} ({device_id})...")
            try:
                # Intentar desconexión graceful (Joy-Con), sino forzar desconexión
                success = device_manager.disconnect_device_gracefully(device_id)
                if not success:
                    device_manager.disconnect_device(device_id)
            except Exception as e:
                print(f"      ⚠️ Error desconectando {device_id}: {e}")
        
        await asyncio.sleep(1.0)  # Esperar a que se desconecten
        
        # Paso 2: Buscar TODOS los dispositivos Bluetooth emparejados
        print("   🔍 Paso 2: Buscando dispositivos Bluetooth emparejados...")
        all_bt_devices = await BluetoothManager.find_all_bluetooth_devices()
        
        if not all_bt_devices:
            print("   ℹ️ No hay dispositivos Bluetooth emparejados")
            return {
                "success": True,
                "unpaired_count": 0,
                "failed_count": 0,
                "message": "No hay dispositivos Bluetooth emparejados",
                "timestamp": datetime.now().isoformat()
            }
        
        unpaired_count = 0
        failed_count = 0
        unpaired_list = []
        skipped_count = 0
        
        # Paso 3: Desemparejar cada dispositivo Bluetooth
        print(f"   🗑️ Paso 3: Desemparejando {len(all_bt_devices)} dispositivos...")
        
        for bt_device in all_bt_devices:
            device_name = bt_device.get('name', 'Unknown')
            device_id_bt = bt_device.get('id', '')
            is_paired = bt_device.get('is_paired', False)
            
            # Filtrar solo dispositivos HID (Joy-Con, DS4, Xbox, etc)
            is_hid = any(keyword in device_name.lower() for keyword in 
                        ['joy-con', 'dualshock', 'ds4', 'xbox', 'controller', 'gamepad', 'wireless controller'])
            
            if not is_hid:
                skipped_count += 1
                print(f"      ⏭️ Omitiendo: {device_name} (no es HID)")
                continue
            
            if not is_paired:
                skipped_count += 1
                print(f"      ⏭️ Omitiendo: {device_name} (no emparejado)")
                continue
            
            print(f"      🗑️ Desemparejando: {device_name}...")
            
            try:
                result = await BluetoothManager.unpair_device(device_id_bt)
                if result['success']:
                    unpaired_count += 1
                    unpaired_list.append(device_name)
                    print(f"      ✅ {device_name} desemparejado")
                else:
                    failed_count += 1
                    print(f"      ❌ Error: {result['message']}")
            except Exception as e:
                failed_count += 1
                print(f"      ❌ Excepción: {e}")
        
        print(f"\n✅ Proceso completado:")
        print(f"   • Desemparejados: {unpaired_count}")
        print(f"   • Fallidos: {failed_count}")
        print(f"   • Omitidos: {skipped_count}\n")
        
        return {
            "success": True,
            "unpaired_count": unpaired_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "unpaired_devices": unpaired_list,
            "total_found": len(all_bt_devices),
            "message": f"Desemparejados {unpaired_count} de {len(all_bt_devices)} dispositivos Bluetooth",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al desemparejar todos: {str(e)}")


@app.get("/api/device/{device_id}/history")
async def get_device_history(device_id: str, limit: int = 100):
    """
    Obtener historial de métricas de un dispositivo
    
    Args:
        device_id: ID del dispositivo
        limit: Número máximo de registros (default: 100)
    
    Returns:
        Lista de métricas históricas (batería, polling rate)
    """
    try:
        history = db_manager.get_device_metrics_history(device_id, limit)
        static_data = db_manager.get_device_static_data(device_id)
        
        return {
            "success": True,
            "device_id": device_id,
            "static_data": static_data,
            "metrics": history,
            "count": len(history),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan")
async def scan_devices():
    """
    Forzar escaneo de nuevos dispositivos
    
    Returns:
        Lista de IDs de dispositivos encontrados
    """
    try:
        found = device_manager.scan_devices()
        return {
            "success": True,
            "devices_found": found,
            "total_devices": len(device_manager.devices),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refresh")
async def refresh_devices():
    """
    Refrescar lista de dispositivos (detectar nuevos y remover desconectados)
    
    Returns:
        Lista de IDs de dispositivos actualmente conectados
    """
    try:
        current = device_manager.refresh_devices()
        return {
            "success": True,
            "connected_devices": current,
            "total_devices": len(current),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/database/purge")
async def purge_database(device_id: str = None):
    """
    Purgar métricas de la base de datos (SOLO cuando el usuario lo solicita)
    
    Args:
        device_id: (opcional) ID del dispositivo específico a purgar
    
    Returns:
        Número de registros eliminados
    """
    try:
        result = db_manager.purge_metrics_by_user_request(device_id)
        
        if device_id:
            message = f"Se eliminaron {result['metrics_deleted']} métricas y {result['sessions_deleted']} sesiones de {device_id}"
        else:
            message = f"Se eliminaron {result['metrics_deleted']} métricas y {result['sessions_deleted']} sesiones de TODOS los dispositivos"
        
        return {
            "success": True,
            "deleted_metrics": result['metrics_deleted'],
            "deleted_sessions": result['sessions_deleted'],
            "device_id": device_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/database/stats")
async def get_database_stats():
    """
    Obtener estadísticas de la base de datos
    
    Returns:
        Estadísticas de métricas, sesiones y dispositivos
    """
    try:
        stats = db_manager.get_database_stats()
        return {
            "success": True,
            **stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/device/{device_id}/graph")
async def get_device_graph_data(device_id: str, hours: int = 24):
    """
    Obtener datos optimizados para gráfica de batería
    
    Args:
        device_id: ID del dispositivo
        hours: Horas de historial (default: 24)
    
    Returns:
        Datos agrupados por intervalos de 2 minutos
    """
    try:
        graph_data = db_manager.get_metrics_for_graph(device_id, hours)
        drain_rate = db_manager.get_battery_drain_rate(device_id, min(hours, 2))
        active_session = db_manager.get_active_session(device_id)
        
        return {
            "success": True,
            "device_id": device_id,
            "hours": hours,
            "data_points": graph_data,
            "drain_rate_per_hour": drain_rate,
            "active_session": active_session,
            "count": len(graph_data),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/device/{device_id}/sessions")
async def get_device_sessions(device_id: str, limit: int = 10):
    """
    Obtener historial de sesiones de un dispositivo
    
    Args:
        device_id: ID del dispositivo
        limit: Número máximo de sesiones (default: 10)
    
    Returns:
        Lista de sesiones con duración y consumo de batería
    """
    try:
        sessions = db_manager.get_device_sessions(device_id, limit)
        active_session = db_manager.get_active_session(device_id)
        
        return {
            "success": True,
            "device_id": device_id,
            "active_session": active_session,
            "past_sessions": sessions,
            "total_sessions": len(sessions),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scheduler/stats")
async def get_scheduler_stats():
    """
    Obtener estadísticas del scheduler de batería
    
    Returns:
        Estadísticas de recolecciones, lecturas exitosas/fallidas, etc.
    """
    try:
        if not battery_scheduler:
            return {
                "success": False,
                "message": "Scheduler no iniciado",
                "timestamp": datetime.now().isoformat()
            }
        
        stats = battery_scheduler.get_stats()
        device_statuses = battery_scheduler.get_all_device_statuses()
        
        return {
            "success": True,
            "scheduler": stats,
            "devices": device_statuses,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scheduler/force")
async def force_battery_collection():
    """
    Forzar una recolección inmediata de baterías
    
    Returns:
        Confirmación de recolección
    """
    try:
        if not battery_scheduler:
            return {
                "success": False,
                "message": "Scheduler no iniciado",
                "timestamp": datetime.now().isoformat()
            }
        
        await battery_scheduler.force_collection()
        
        return {
            "success": True,
            "message": "Recolección forzada completada",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scheduler/interval")
async def set_scheduler_interval(seconds: int = 120):
    """
    Cambiar el intervalo de recolección del scheduler
    
    Args:
        seconds: Nuevo intervalo en segundos (mínimo: 30)
    
    Returns:
        Confirmación del cambio
    """
    try:
        if not battery_scheduler:
            return {
                "success": False,
                "message": "Scheduler no iniciado",
                "timestamp": datetime.now().isoformat()
            }
        
        battery_scheduler.set_interval(seconds)
        
        return {
            "success": True,
            "new_interval_seconds": battery_scheduler.COLLECTION_INTERVAL,
            "message": f"Intervalo cambiado a {battery_scheduler.COLLECTION_INTERVAL} segundos",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para updates en tiempo real y alertas
    
    Envía información de todos los dispositivos cada 2 segundos
    y notificaciones de alertas en tiempo real
    También envía datos históricos para gráficas cada 30 segundos
    Incluye estado inteligente de batería (Critical/Low/Normal/High/Full)
    """
    global previous_battery_states
    await websocket.accept()
    active_websockets.append(websocket)
    
    update_counter = 0
    
    try:
        while True:
            update_counter += 1
            
            # Obtener info de todos los dispositivos
            devices_data = []
            all_alerts = []
            battery_state_changes = []
            
            for device_id in device_manager.devices.keys():
                info = device_manager.get_device_info(device_id)
                if info:
                    device_data = info.model_dump(mode='json')
                    
                    # Agregar datos de uso desde DB (igual que el endpoint REST)
                    usage_data = db_manager.get_usage_time(device_id)
                    if usage_data:
                        device_data['usage_time_hours'] = usage_data['duration_hours']
                        device_data['usage_time_minutes'] = usage_data['duration_minutes']
                        device_data['battery_consumed'] = usage_data['battery_consumed']
                        device_data['estimated_autonomy_hours'] = usage_data['estimated_autonomy_hours']
                    
                    # === SMART BATTERY STATUS (con cache de 5 minutos) ===
                    if info.battery and info.battery.percentage is not None:
                        try:
                            # Intentar obtener desde cache primero
                            smart_status = device_manager.cache.get(device_id, 'smart_battery')
                            if not smart_status:
                                # Si no está en cache o expiró, calcular
                                smart_status = db_manager.get_smart_battery_status(
                                    device_id=device_id,
                                    current_battery=info.battery.percentage,
                                    device_type=info.type or "unknown"
                                )
                                # Guardar en cache (TTL de 5 minutos)
                                device_manager.cache.set(device_id, 'smart_battery', smart_status)
                            
                            device_data['smart_battery'] = smart_status
                            
                            # === BATTERY INTELLIGENCE: Datos avanzados ===
                            try:
                                raw_data = {
                                    "voltage": info.battery.voltage,
                                    "temperature": getattr(info.battery, 'temperature', None),
                                    "charging": info.battery.charging,
                                    "level": info.battery.percentage // 25,
                                    "percentage": info.battery.percentage
                                }
                                
                                bi_state = battery_intelligence.process_reading(
                                    device_id, info.type or "unknown", raw_data
                                )
                                
                                device_data['smart_battery']['intelligence'] = {
                                    'soc_precise': round(bi_state.current_reading.soc_percent, 1),
                                    'equivalent_cycles': round(bi_state.health.equivalent_cycles, 2),
                                    'soh_percent': bi_state.health.soh_percent,
                                    'health_status': bi_state.health.health_status,
                                    'internal_resistance_mohm': bi_state.health.internal_resistance_mohm,
                                    'confidence': bi_state.health.confidence,
                                    'data_points': bi_state.health.data_points,
                                    'has_voltage_data': info.battery.voltage is not None
                                }
                            except Exception as bi_error:
                                pass  # Silencioso en WebSocket para no saturar logs
                            
                            # Detectar cambios de estado de batería
                            current_state = smart_status['status']
                            previous_state = previous_battery_states.get(device_id)
                            
                            if previous_state and previous_state != current_state:
                                # Hubo un cambio de estado
                                battery_state_changes.append({
                                    'device_id': device_id,
                                    'device_name': info.name or device_id,
                                    'previous_state': previous_state,
                                    'current_state': current_state,
                                    'battery_level': info.battery.percentage,
                                    'health': smart_status['battery_health'],
                                    'estimated_minutes': smart_status['estimated_minutes_remaining'],
                                    'is_critical': current_state in ['Critical', 'Low']
                                })
                            
                            # Actualizar cache de estados
                            previous_battery_states[device_id] = current_state
                        except Exception as e:
                            print(f"⚠️ Error calculando smart_battery para {device_id}: {e}")
                    
                    # Agregar estado del scheduler si está disponible
                    if battery_scheduler:
                        scheduler_status = battery_scheduler.get_device_status(device_id)
                        if scheduler_status:
                            device_data['scheduler_status'] = scheduler_status
                    
                    devices_data.append(device_data)
                    
                    # Verificar alertas para este dispositivo
                    device_type = alert_manager.get_device_type_from_id(device_id)
                    battery = info.battery.percentage if info.battery else None
                    polling = info.polling.rate_hz if info.polling else None
                    
                    alerts = alert_manager.check_device_alerts(
                        device_id=device_id,
                        device_name=info.name or device_id,
                        device_type=device_type,
                        battery=battery,
                        polling_rate=polling,
                        is_connected=True
                    )
                    
                    # Agregar alertas a la lista
                    if alerts:
                        all_alerts.extend([alert.to_dict() for alert in alerts])
            
            # Preparar mensaje
            message = {
                "type": "devices_update",
                "timestamp": datetime.now().isoformat(),
                "devices": devices_data,
                "count": len(devices_data)
            }
            
            # Agregar alertas si hay
            if all_alerts:
                message["alerts"] = all_alerts
            
            # Agregar cambios de estado de batería
            if battery_state_changes:
                message["battery_state_changes"] = battery_state_changes
                # Log para debugging
                for change in battery_state_changes:
                    print(f"🔋 Estado batería: {change['device_name']}: {change['previous_state']} → {change['current_state']} ({change['battery_level']}%)")
            
            # Siempre enviar datos históricos para gráficas (con timestamps)
            graph_data = {}
            for device_id in device_manager.devices.keys():
                metrics = db_manager.get_metrics_for_graph(device_id, hours=24)
                
                # Agregar análisis de descarga inteligente
                drain_analysis = db_manager.get_battery_drain_analysis(device_id)
                
                graph_data[device_id] = {
                    'data_points': metrics,  # Cambiado de 'history' para compatibilidad con frontend
                    'points': metrics,  # Alias para compatibilidad
                    'drain_rate': db_manager.get_battery_drain_rate(device_id, hours=24),
                    'active_session': db_manager.get_active_session(device_id),
                    'drain_analysis': drain_analysis
                }
            message["graph_data"] = graph_data
            
            # Agregar stats del scheduler cada 30 updates (~1 minuto)
            if update_counter % 30 == 0 and battery_scheduler:
                message["scheduler_stats"] = battery_scheduler.get_stats()
            
            # Enviar al cliente
            await websocket.send_json(message)
            
            # Esperar 2 segundos antes del próximo update
            await asyncio.sleep(2.0)
    
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
        print("WebSocket desconectado")
    except Exception as e:
        print(f"Error en WebSocket: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "devices_connected": len(device_manager.devices),
        "websockets_active": len(active_websockets)
    }


@app.get("/api/cache/stats")
async def cache_stats():
    """Obtener estadísticas del sistema de caché"""
    return device_manager.cache.get_stats()


@app.get("/api/cache/{device_id}")
async def cache_device_info(device_id: str):
    """Obtener información de caché de un dispositivo específico"""
    info = device_manager.cache.get_cache_info(device_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"No hay caché para dispositivo {device_id}")
    return {
        "device_id": device_id,
        "cache": info,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/cache/clear/{device_id}")
async def clear_device_cache(device_id: str):
    """Limpiar caché de un dispositivo específico"""
    device_manager.cache.clear_device(device_id)
    return {
        "success": True,
        "message": f"Caché limpiado para dispositivo {device_id}",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/cache/clear")
async def clear_all_cache():
    """Limpiar todo el caché"""
    device_manager.cache.clear_all()
    return {
        "success": True,
        "message": "Todo el caché ha sido limpiado",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/battery-intelligence/{device_id}")
async def get_battery_intelligence_endpoint(device_id: str):
    """Obtener datos completos de Battery Intelligence para un dispositivo"""
    health_data = battery_intelligence.get_health_with_history(device_id)
    if not health_data:
        # Si no hay estado, intentar crear un monitor si el dispositivo está conectado
        info = device_manager.device_info.get(device_id)
        if info:
            device_type = info.type if hasattr(info, 'type') else info.get('type', 'unknown')
            battery_intelligence.get_or_create_monitor(device_id, device_type)
            return {
                "device_id": device_id,
                "status": "initialized",
                "message": "Monitor creado, esperando datos de batería",
                "data": None
            }
        raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} no encontrado")
    
    return {
        "device_id": device_id,
        "status": "active",
        "data": health_data,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/battery-intelligence")
async def get_all_battery_intelligence_endpoint():
    """Obtener datos de Battery Intelligence para todos los dispositivos"""
    all_states = {}
    for device_id in device_manager.devices.keys():
        health_data = battery_intelligence.get_health_with_history(device_id)
        if health_data:
            all_states[device_id] = health_data
    
    return {
        "devices": all_states,
        "count": len(all_states),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/battery-intelligence/{device_id}/charges")
async def get_device_charges(device_id: str):
    """Obtener historial de cargas de un dispositivo"""
    charge_stats = battery_intelligence.get_charge_count(device_id)
    return {
        "device_id": device_id,
        "charge_stats": charge_stats,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/debug")
async def debug_info():
    """Debug endpoint con info detallada"""
    devices_debug = {}
    for device_id, reader in device_manager.devices.items():
        devices_debug[device_id] = {
            "reader_type": type(reader).__name__,
            "device_connected": reader.device is not None if hasattr(reader, 'device') else "unknown",
            "info": device_manager.device_info.get(device_id, {}),
            "cache": device_manager.cache.get_cache_info(device_id),
            "battery_intelligence": battery_intelligence.get_health_with_history(device_id)
        }
    
    return {
        "total_devices": len(device_manager.devices),
        "devices": devices_debug,
        "last_scan": device_manager.last_scan.isoformat() if device_manager.last_scan else None,
        "cache_stats": device_manager.cache.get_stats()
    }


if __name__ == "__main__":
    import socket
    
    # Obtener IP local
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("Iniciando Gamepad Monitor API v2.0")
    print(f"Servidor Local: http://localhost:8000")
    print(f"Servidor Red Local: http://{local_ip}:8000")
    print(f"Documentacion: http://localhost:8000/docs")
    print(f"WebSocket: ws://localhost:8000/api/ws")
    print(f"\n📱 Acceso desde celular: http://{local_ip}:8000")
    print("⚠️ Asegúrate que el firewall permita el puerto 8000\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
