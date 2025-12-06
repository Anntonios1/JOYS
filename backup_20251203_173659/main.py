"""
FastAPI Server - API REST para gamepad monitoring
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import List
import asyncio
import uvicorn
from datetime import datetime
import os

from device_manager import DeviceManager
from models.device_models import DeviceInfo, VibrateRequest, ErrorResponse


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

# Gestor de dispositivos
device_manager = DeviceManager()

# WebSocket connections activas
active_websockets: List[WebSocket] = []

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
    """Escanear dispositivos al iniciar"""
    print("Gamepad Monitor API v2.0 iniciando...")
    device_manager.scan_devices()
    print(f"{len(device_manager.devices)} dispositivo(s) detectado(s)")


@app.on_event("shutdown")
async def shutdown_event():
    """Limpiar al cerrar"""
    print("Desconectando todos los dispositivos...")
    device_manager.disconnect_all()


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
        
        print(f"✅ Info obtenida correctamente")
        return info
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
    Desconectar un dispositivo (Joy-Con)
    
    Args:
        device_id: ID del dispositivo
    
    Returns:
        Confirmación de desconexión
    """
    try:
        success = device_manager.disconnect_device_gracefully(device_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Dispositivo {device_id} no encontrado o no soporta desconexión")
        
        return {
            "success": True,
            "device_id": device_id,
            "message": "Dispositivo desconectado",
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
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


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para updates en tiempo real
    
    Envía información de todos los dispositivos cada 2 segundos
    """
    await websocket.accept()
    active_websockets.append(websocket)
    
    try:
        while True:
            # Obtener info de todos los dispositivos
            devices_data = []
            for device_id in device_manager.devices.keys():
                info = device_manager.get_device_info(device_id)
                if info:
                    devices_data.append(info.model_dump())
            
            # Enviar al cliente
            await websocket.send_json({
                "type": "devices_update",
                "timestamp": datetime.now().isoformat(),
                "devices": devices_data,
                "count": len(devices_data)
            })
            
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


@app.get("/api/debug")
async def debug_info():
    """Debug endpoint con info detallada"""
    devices_debug = {}
    for device_id, reader in device_manager.devices.items():
        devices_debug[device_id] = {
            "reader_type": type(reader).__name__,
            "device_connected": reader.device is not None if hasattr(reader, 'device') else "unknown",
            "info": device_manager.device_info.get(device_id, {})
        }
    
    return {
        "total_devices": len(device_manager.devices),
        "devices": devices_debug,
        "last_scan": device_manager.last_scan.isoformat() if device_manager.last_scan else None
    }


if __name__ == "__main__":
    print("Iniciando Gamepad Monitor API v2.0")
    print("Servidor: http://localhost:8000")
    print("Documentacion: http://localhost:8000/docs")
    print("WebSocket: ws://localhost:8000/api/ws")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
