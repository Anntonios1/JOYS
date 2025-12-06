"""
Reader para Xbox Controllers (básico)
Detección y funcionalidad básica
"""

import hid
import time
from typing import Optional
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from models.device_models import BatteryInfo, PollingInfo


class XboxReader:
    """Lector básico para Xbox Controllers"""
    
    VENDOR_ID = 0x045E  # Microsoft
    KNOWN_PRODUCT_IDS = [
        0x02DD,  # Xbox One Controller (2015)
        0x02E0,  # Xbox One S Controller (Bluetooth)
        0x02EA,  # Xbox One S Controller
        0x0B00,  # Xbox Elite Controller
        0x0B05,  # Xbox Elite Controller Series 2
        0x0B12,  # Xbox Series X|S Controller
        0x0B13,  # Xbox Series X|S Controller (Bluetooth)
    ]
    
    def __init__(self, device_path: bytes, product_id: int):
        """
        Inicializar reader de Xbox
        
        Args:
            device_path: Path del dispositivo HID
            product_id: Product ID del controlador Xbox
        """
        self.device_path = device_path
        self.product_id = product_id
        self.device = None
        self.model = self._detect_model(product_id)
    
    @staticmethod
    def _detect_model(product_id: int) -> str:
        """Detectar modelo de Xbox controller"""
        models = {
            0x02DD: "Xbox One (2015)",
            0x02E0: "Xbox One S (Bluetooth)",
            0x02EA: "Xbox One S",
            0x0B00: "Xbox Elite",
            0x0B05: "Xbox Elite Series 2",
            0x0B12: "Xbox Series X|S",
            0x0B13: "Xbox Series X|S (Bluetooth)",
        }
        return models.get(product_id, f"Xbox Controller (0x{product_id:04X})")
    
    def connect(self) -> bool:
        """Conectar al dispositivo"""
        try:
            self.device = hid.device()
            self.device.open_path(self.device_path)
            self.device.set_nonblocking(False)
            return True
        except Exception as e:
            print(f"Error conectando Xbox Controller: {e}")
            return False
    
    def disconnect(self):
        """Desconectar del dispositivo"""
        if self.device:
            try:
                self.device.close()
            except:
                pass
            self.device = None
    
    def get_battery(self) -> Optional[BatteryInfo]:
        """
        Obtener información de batería
        Nota: Xbox controllers vía Bluetooth tienen reporte limitado de batería
        """
        if not self.device:
            return None
        
        try:
            # Los Xbox controllers no reportan batería detallada vía HID en Windows
            # Requieren XInput API o acceso especial
            # Por ahora retornamos información básica
            return BatteryInfo(
                percentage=None,  # No disponible vía HID estándar
                voltage=None,
                charging=False,
                level_name="No disponible"
            )
        except Exception as e:
            print(f"Error leyendo batería Xbox: {e}")
            return None
    
    def measure_polling_rate(self, duration_seconds: float = 2.0) -> Optional[PollingInfo]:
        """Medir polling rate"""
        if not self.device:
            return None
        
        try:
            self.device.set_nonblocking(True)
            
            # Limpiar buffer
            for _ in range(50):
                data = self.device.read(64)
                if not data:
                    break
            
            time.sleep(0.1)
            
            # Contar paquetes
            packet_count = 0
            start_time = time.time()
            
            while time.time() - start_time < duration_seconds:
                data = self.device.read(64)
                if data:
                    packet_count += 1
            
            elapsed = time.time() - start_time
            self.device.set_nonblocking(False)
            
            if packet_count > 0:
                polling_rate_hz = packet_count / elapsed
                polling_interval_ms = 1000.0 / polling_rate_hz
                
                return PollingInfo(
                    rate_hz=round(polling_rate_hz, 1),
                    interval_ms=round(polling_interval_ms, 2),
                    packet_count=packet_count
                )
            
            return None
        except Exception as e:
            print(f"Error midiendo polling rate: {e}")
            return None
    
    def vibrate(self, duration_seconds: float = 1.0, intensity: float = 0.7):
        """
        Hacer vibrar el Xbox controller
        Nota: Vibración requiere XInput API en Windows, no disponible vía HID estándar
        """
        print("Vibración Xbox no disponible vía HID - requiere XInput API")
        # Los Xbox controllers en Windows requieren XInput para rumble
        # hidapi solo permite lectura de inputs, no control de salida estándar
        pass
    
    def get_model_name(self) -> str:
        """Obtener nombre del modelo"""
        return self.model
