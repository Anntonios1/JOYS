"""
Modelos de datos para dispositivos
Pydantic models para validación y serialización
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime


class BatteryInfo(BaseModel):
    """Información de batería"""
    percentage: int = Field(..., ge=0, le=100, description="Porcentaje de batería (0-100)")
    voltage: Optional[float] = Field(None, description="Voltaje en voltios")
    charging: bool = Field(..., description="Si está cargando")
    level_name: Optional[str] = Field(None, description="Nombre del nivel (Crítico, Bajo, Medio, Alto, Lleno)")


class ColorInfo(BaseModel):
    """Información de color RGB"""
    r: int = Field(..., ge=0, le=255)
    g: int = Field(..., ge=0, le=255)
    b: int = Field(..., ge=0, le=255)
    hex: str = Field(..., description="Valor hexadecimal #RRGGBB")


class ColorsInfo(BaseModel):
    """Colores del Joy-Con"""
    body: ColorInfo
    buttons: ColorInfo
    left_grip: Optional[ColorInfo] = None
    right_grip: Optional[ColorInfo] = None


class SmartBatteryInfo(BaseModel):
    """Información inteligente de batería"""
    status: str = Field(..., description="Estado: Critical, Low, Normal, High, Full")
    battery_health: float = Field(..., description="Salud de la batería (0-100)")
    health_reliable: bool = Field(..., description="Si hay suficientes datos para confiar en la salud")
    health_samples: int = Field(..., description="Número de muestras para calcular salud")
    drain_rate_per_hour: float = Field(..., description="Tasa de descarga por hora")
    estimated_minutes_remaining: float = Field(..., description="Minutos estimados restantes")
    capacity_mah: int = Field(..., description="Capacidad en mAh")
    intelligence: Optional[Dict] = Field(None, description="Datos de Battery Intelligence")


class PollingInfo(BaseModel):
    """Información de polling rate"""
    rate_hz: float = Field(..., description="Frecuencia en Hz")
    interval_ms: float = Field(..., description="Intervalo en milisegundos")
    packet_count: int = Field(..., description="Número de paquetes capturados")


class DeviceInfo(BaseModel):
    """Información completa del dispositivo"""
    # Identificación
    id: str = Field(..., description="ID único del dispositivo")
    type: str = Field(..., description="Tipo: joycon-l, joycon-r, ds4, xbox")
    name: str = Field(..., description="Nombre del dispositivo")
    connected: bool = Field(..., description="Si está conectado")
    
    # Batería (siempre presente)
    battery: BatteryInfo
    
    # Conexión
    connection_type: Optional[str] = Field(None, description="Bluetooth, USB, etc")
    
    # Específico de Joy-Con
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    colors: Optional[ColorsInfo] = None
    player_number: Optional[int] = Field(None, ge=1, le=8, description="Número de jugador (1-8)")
    
    # Polling rate
    polling: Optional[PollingInfo] = None
    
    # Tiempo de uso y autonomía
    usage_time_hours: Optional[float] = Field(None, description="Horas de uso desde primer registro")
    usage_time_minutes: Optional[float] = Field(None, description="Minutos de uso desde primer registro")
    battery_consumed: Optional[float] = Field(None, description="Batería consumida desde inicio (%)")
    estimated_autonomy_hours: Optional[float] = Field(None, description="Autonomía estimada (horas)")
    
    # Smart Battery (datos inteligentes de batería)
    smart_battery: Optional[SmartBatteryInfo] = Field(None, description="Estado inteligente de batería")
    
    # Timestamps
    last_update: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DeviceListResponse(BaseModel):
    """Respuesta con lista de dispositivos"""
    devices: List[DeviceInfo]
    total: int
    timestamp: datetime = Field(default_factory=datetime.now)


class VibrateRequest(BaseModel):
    """Solicitud de vibración"""
    duration: float = Field(1.0, ge=0.1, le=5.0, description="Duración en segundos")
    intensity: float = Field(0.5, ge=0.0, le=1.0, description="Intensidad 0.0-1.0")


class ErrorResponse(BaseModel):
    """Respuesta de error"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
