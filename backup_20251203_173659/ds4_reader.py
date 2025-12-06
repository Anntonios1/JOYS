"""
Reader para DualShock 4 (v1 y v2)
Implementa lectura de batería, tipo de conexión, polling rate y vibración
"""

import hid
import time
from typing import Optional
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from models.device_models import BatteryInfo, PollingInfo


class DS4Reader:
    """Lector para DualShock 4"""
    
    VENDOR_ID = 0x054C
    PRODUCT_ID_V1 = 0x05C4
    PRODUCT_ID_V2 = 0x09CC
    
    def __init__(self, device_path: bytes, product_id: int):
        """
        Inicializar reader de DS4
        
        Args:
            device_path: Path del dispositivo HID
            product_id: 0x05C4 (v1) o 0x09CC (v2)
        """
        self.device_path = device_path
        self.product_id = product_id
        self.version = "v1" if product_id == self.PRODUCT_ID_V1 else "v2"
        self.device = None
        self.connection_type = "Unknown"
    
    def connect(self) -> bool:
        """Conectar al dispositivo"""
        try:
            self.device = hid.device()
            self.device.open_path(self.device_path)
            self.device.set_nonblocking(False)
            return True
        except Exception as e:
            print(f"Error conectando DS4: {e}")
            return False
    
    def disconnect(self):
        """Desconectar del dispositivo"""
        if self.device:
            try:
                self.device.close()
            except:
                pass
            self.device = None
    
    @staticmethod
    def _crc32_ds4(data: bytes) -> int:
        """Calcular CRC-32 para DualShock 4 Bluetooth"""
        crc = 0xFFFFFFFF
        polynomial = 0xEDB88320
        
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ polynomial
                else:
                    crc >>= 1
        
        return ~crc & 0xFFFFFFFF
    
    def get_battery(self) -> Optional[BatteryInfo]:
        """Obtener información de batería"""
        if not self.device:
            return None
        
        try:
            self.device.set_nonblocking(True)
            
            for attempt in range(100):
                data = self.device.read(64)
                if data and len(data) > 10:
                    report_id = data[0]
                    
                    # Report 0x11 para Bluetooth
                    if report_id == 0x11 and len(data) >= 33:
                        battery_byte = data[32]
                        battery_level = (battery_byte & 0x0f) * 100 // 8
                        charging = (data[31] & 0x10) != 0
                        self.connection_type = "Bluetooth"
                        
                        level_name = "Lleno" if battery_level >= 90 else \
                                   "Alto" if battery_level >= 60 else \
                                   "Medio" if battery_level >= 40 else \
                                   "Bajo" if battery_level >= 20 else "Crítico"
                        
                        self.device.set_nonblocking(False)
                        return BatteryInfo(
                            percentage=min(battery_level, 100),
                            voltage=None,
                            charging=charging,
                            level_name=level_name
                        )
                    
                    # Report 0x01 para USB
                    elif report_id == 0x01 and len(data) >= 31:
                        battery_byte = data[30]
                        battery_level = (battery_byte & 0x0f) * 100 // 8
                        charging = (data[29] & 0x10) != 0
                        self.connection_type = "USB"
                        
                        level_name = "Lleno" if battery_level >= 90 else \
                                   "Alto" if battery_level >= 60 else \
                                   "Medio" if battery_level >= 40 else \
                                   "Bajo" if battery_level >= 20 else "Crítico"
                        
                        self.device.set_nonblocking(False)
                        return BatteryInfo(
                            percentage=min(battery_level, 100),
                            voltage=None,
                            charging=charging,
                            level_name=level_name
                        )
                
                time.sleep(0.01)
            
            self.device.set_nonblocking(False)
            return None
        except Exception as e:
            print(f"Error leyendo batería DS4: {e}")
            return None
    
    def get_connection_type(self) -> str:
        """Obtener tipo de conexión (Bluetooth o USB)"""
        return self.connection_type
    
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
        """Hacer vibrar el DS4"""
        if not self.device:
            return
        
        try:
            intensity = max(0.0, min(1.0, intensity))
            
            # Solo motor pesado (más notable)
            small_motor = 0
            large_motor = int(255 * intensity)
            
            # Bluetooth
            report = bytearray(78)
            report[0] = 0x11  # Report ID
            report[1] = 0xC4  # 0x80 | btPollRate donde btPollRate=0x04
            report[2] = 0x00  
            report[3] = 0x07  # outputFeaturesByte: rumble(0x01) + lightbar(0x02) + flash(0x04)
            report[4] = 0x04  
            report[5] = 0x00  
            report[6] = small_motor  # Motor rápido
            report[7] = large_motor  # Motor pesado
            report[8] = 255  # LED R (Rojo para indicar vibración)
            report[9] = 0    # LED G
            report[10] = 0   # LED B
            report[11] = 0   # Flash on
            report[12] = 0   # Flash off
            
            # Calcular CRC-32
            crc_head = bytes([0xA2])
            crc = ~self._crc32_ds4(crc_head)
            crc = ~self._crc32_ds4(report[0:74]) ^ crc
            
            report[74] = crc & 0xFF
            report[75] = (crc >> 8) & 0xFF
            report[76] = (crc >> 16) & 0xFF
            report[77] = (crc >> 24) & 0xFF
            
            result = self.device.write(bytes(report))
            
            if result > 0:
                # Enviar rumble continuamente (DS4 necesita reportes repetidos)
                start_time = time.time()
                while time.time() - start_time < duration_seconds:
                    self.device.write(bytes(report))
                    time.sleep(0.01)  # 100Hz
                
                # Detener
                report[7] = 0
                report[8] = 0    # LED volver a azul
                report[9] = 0
                report[10] = 255
                crc = ~self._crc32_ds4(crc_head)
                crc = ~self._crc32_ds4(report[0:74]) ^ crc
                report[74] = crc & 0xFF
                report[75] = (crc >> 8) & 0xFF
                report[76] = (crc >> 16) & 0xFF
                report[77] = (crc >> 24) & 0xFF
                self.device.write(bytes(report))
        except Exception as e:
            print(f"Error vibrando DS4: {e}")
