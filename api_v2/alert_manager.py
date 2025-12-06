"""
Alert Manager - Sistema de alertas para dispositivos
"""

from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum


class AlertType(str, Enum):
    """Tipos de alertas"""
    BATTERY_LOW = "battery_low"
    BATTERY_CRITICAL = "battery_critical"
    POLLING_DEGRADED = "polling_degraded"
    DEVICE_DISCONNECTED = "device_disconnected"
    DEVICE_RECONNECTED = "device_reconnected"


class AlertSeverity(str, Enum):
    """Niveles de severidad"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Alert:
    """Clase para representar una alerta"""
    def __init__(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        device_id: str,
        device_name: str,
        message: str,
        data: Optional[Dict] = None
    ):
        self.type = alert_type
        self.severity = severity
        self.device_id = device_id
        self.device_name = device_name
        self.message = message
        self.data = data or {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convertir a diccionario para JSON"""
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp
        }


class AlertManager:
    """Gestor de alertas y notificaciones"""
    
    # Umbrales de alerta
    BATTERY_WARNING = 20
    BATTERY_CRITICAL = 10
    
    # Umbrales de polling rate por tipo de dispositivo
    POLLING_THRESHOLDS = {
        "ds4": 50,      # DS4/DS5: <= 50 Hz es degradado
        "ds5": 50,
        "joycon": 25    # Joy-Con: <= 25 Hz es degradado
    }
    
    def __init__(self):
        # Estado previo de dispositivos para detectar cambios
        self.previous_state: Dict[str, Dict] = {}
        
        # Alertas recientes por dispositivo (evitar spam)
        self.recent_alerts: Dict[str, Dict[AlertType, datetime]] = {}
        
        # Tiempo mínimo entre alertas del mismo tipo (segundos)
        self.alert_cooldown = {
            AlertType.BATTERY_LOW: 300,        # 5 minutos
            AlertType.BATTERY_CRITICAL: 120,   # 2 minutos
            AlertType.POLLING_DEGRADED: 60,    # 1 minuto
            AlertType.DEVICE_DISCONNECTED: 0,  # Inmediato
            AlertType.DEVICE_RECONNECTED: 0    # Inmediato
        }
    
    def check_device_alerts(
        self,
        device_id: str,
        device_name: str,
        device_type: str,
        battery: Optional[int],
        polling_rate: Optional[float],
        is_connected: bool
    ) -> List[Alert]:
        """
        Verificar todas las condiciones de alerta para un dispositivo
        
        Args:
            device_id: ID del dispositivo
            device_name: Nombre descriptivo del dispositivo
            device_type: Tipo de dispositivo (ds4, ds5, joycon)
            battery: Nivel de batería (0-100) o None
            polling_rate: Tasa de polling en Hz o None
            is_connected: Si el dispositivo está conectado
        
        Returns:
            Lista de alertas generadas
        """
        alerts = []
        
        # Obtener estado previo
        prev_state = self.previous_state.get(device_id, {})
        
        # Verificar conexión/desconexión
        prev_connected = prev_state.get("connected", False)
        if is_connected != prev_connected:
            if not is_connected and prev_connected:
                # Dispositivo desconectado
                alert = self._create_alert(
                    device_id,
                    AlertType.DEVICE_DISCONNECTED,
                    AlertSeverity.WARNING,
                    device_name,
                    f"{device_name} se ha desconectado",
                    {}
                )
                if alert:
                    alerts.append(alert)
            elif is_connected and not prev_connected:
                # Dispositivo reconectado
                alert = self._create_alert(
                    device_id,
                    AlertType.DEVICE_RECONNECTED,
                    AlertSeverity.INFO,
                    device_name,
                    f"{device_name} se ha reconectado",
                    {}
                )
                if alert:
                    alerts.append(alert)
        
        # Solo verificar otras alertas si está conectado
        if is_connected:
            # Verificar batería baja
            if battery is not None:
                if battery <= self.BATTERY_CRITICAL:
                    alert = self._create_alert(
                        device_id,
                        AlertType.BATTERY_CRITICAL,
                        AlertSeverity.CRITICAL,
                        device_name,
                        f"⚠️ Batería crítica: {battery}%",
                        {"battery": battery}
                    )
                    if alert:
                        alerts.append(alert)
                elif battery <= self.BATTERY_WARNING:
                    alert = self._create_alert(
                        device_id,
                        AlertType.BATTERY_LOW,
                        AlertSeverity.WARNING,
                        device_name,
                        f"Batería baja: {battery}%",
                        {"battery": battery}
                    )
                    if alert:
                        alerts.append(alert)
            
            # Verificar polling rate degradado
            if polling_rate is not None:
                # Determinar umbral según tipo de dispositivo
                threshold = self.POLLING_THRESHOLDS.get(device_type.lower(), 50)
                
                if polling_rate <= threshold:
                    alert = self._create_alert(
                        device_id,
                        AlertType.POLLING_DEGRADED,
                        AlertSeverity.WARNING,
                        device_name,
                        f"Polling rate degradado: {polling_rate:.1f} Hz (esperado >{threshold} Hz)",
                        {
                            "polling_rate": polling_rate,
                            "threshold": threshold,
                            "device_type": device_type
                        }
                    )
                    if alert:
                        alerts.append(alert)
        
        # Actualizar estado previo
        self.previous_state[device_id] = {
            "connected": is_connected,
            "battery": battery,
            "polling_rate": polling_rate
        }
        
        return alerts
    
    def _create_alert(
        self,
        device_id: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        device_name: str,
        message: str,
        data: Dict
    ) -> Optional[Alert]:
        """
        Crear alerta si no está en cooldown
        
        Returns:
            Alert si se debe enviar, None si está en cooldown
        """
        # Verificar cooldown
        if not self._can_send_alert(device_id, alert_type):
            return None
        
        # Registrar envío de alerta
        if device_id not in self.recent_alerts:
            self.recent_alerts[device_id] = {}
        self.recent_alerts[device_id][alert_type] = datetime.now()
        
        # Crear alerta
        return Alert(
            alert_type=alert_type,
            severity=severity,
            device_id=device_id,
            device_name=device_name,
            message=message,
            data=data
        )
    
    def _can_send_alert(self, device_id: str, alert_type: AlertType) -> bool:
        """
        Verificar si se puede enviar alerta (cooldown)
        
        Returns:
            True si puede enviar, False si está en cooldown
        """
        if device_id not in self.recent_alerts:
            return True
        
        if alert_type not in self.recent_alerts[device_id]:
            return True
        
        last_sent = self.recent_alerts[device_id][alert_type]
        cooldown_seconds = self.alert_cooldown[alert_type]
        
        elapsed = (datetime.now() - last_sent).total_seconds()
        return elapsed >= cooldown_seconds
    
    def clear_device_alerts(self, device_id: str):
        """Limpiar alertas de un dispositivo (cuando se desconecta definitivamente)"""
        if device_id in self.previous_state:
            del self.previous_state[device_id]
        if device_id in self.recent_alerts:
            del self.recent_alerts[device_id]
    
    def get_device_type_from_id(self, device_id: str) -> str:
        """
        Extraer tipo de dispositivo desde el ID
        
        Returns:
            'ds4', 'ds5', 'joycon', o 'unknown'
        """
        device_id_lower = device_id.lower()
        
        if "ds4" in device_id_lower or "dualshock_4" in device_id_lower:
            return "ds4"
        elif "ds5" in device_id_lower or "dualsense" in device_id_lower:
            return "ds5"
        elif "joycon" in device_id_lower or "joy-con" in device_id_lower:
            return "joycon"
        else:
            return "unknown"
