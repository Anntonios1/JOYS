"""
Reader para DualSense (PS5) y DualSense Edge
Basado en DS4Windows DualSenseDevice.cs

VID: 0x054C (Sony)
PID: 0x0CE6 (DualSense)
PID: 0x0DF2 (DualSense Edge)
"""

import hid
import time
from typing import Optional
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from models.device_models import BatteryInfo, PollingInfo


class DualSenseReader:
    """Lector para DualSense (PS5) y DualSense Edge"""
    
    VENDOR_ID = 0x054C
    PRODUCT_ID_DUALSENSE = 0x0CE6
    PRODUCT_ID_DUALSENSE_EDGE = 0x0DF2
    
    # Constantes de batería (de DS4Windows)
    BATTERY_MAX = 8
    
    # Report IDs
    USB_INPUT_REPORT_ID = 0x01
    BT_INPUT_REPORT_ID = 0x31
    USB_OUTPUT_REPORT_ID = 0x02
    BT_OUTPUT_REPORT_ID = 0x31
    SERIAL_FEATURE_ID = 0x09
    FIRMWARE_INFO_FEATURE_ID = 0x20
    CALIBRATION_FEATURE_ID = 0x05
    
    def __init__(self, device_path: bytes, product_id: int):
        """
        Inicializar reader de DualSense
        
        Args:
            device_path: Path del dispositivo HID
            product_id: 0x0CE6 (DualSense) o 0x0DF2 (DualSense Edge)
        """
        self.device_path = device_path
        self.product_id = product_id
        self.is_edge = product_id == self.PRODUCT_ID_DUALSENSE_EDGE
        self.model_name = "DualSense Edge" if self.is_edge else "DualSense"
        self.device = None
        self.connection_type = "Unknown"
        self.hw_version = None
        self.fw_version = None
        self.mac_address = None
    
    def connect(self) -> bool:
        """Conectar al dispositivo"""
        try:
            self.device = hid.device()
            self.device.open_path(self.device_path)
            self.device.set_nonblocking(False)
            
            # Determinar tipo de conexión basado en tamaño del reporte
            # USB = 64 bytes, BT = 78 bytes
            self._determine_connection_type()
            
            # Intentar leer MAC address
            self._read_mac_address()
            
            # Intentar leer versión de firmware
            self._read_firmware_info()
            
            return True
        except Exception as e:
            print(f"Error conectando {self.model_name}: {e}")
            return False
    
    def _determine_connection_type(self):
        """Determinar si es USB o Bluetooth basado en el tamaño del reporte"""
        try:
            self.device.set_nonblocking(True)
            
            for _ in range(20):
                data = self.device.read(128)  # Leer más de lo necesario
                if data:
                    report_id = data[0]
                    length = len(data)
                    
                    # USB: Report ID 0x01, 64 bytes
                    # BT: Report ID 0x31, 78 bytes
                    if report_id == 0x01 and length <= 64:
                        self.connection_type = "USB"
                        break
                    elif report_id == 0x31 and length >= 70:
                        self.connection_type = "Bluetooth"
                        break
                time.sleep(0.01)
            
            self.device.set_nonblocking(False)
            
            if self.connection_type == "Unknown":
                # Fallback: si no hay datos, asumimos USB por defecto
                self.connection_type = "USB"
                
        except Exception as e:
            print(f"Error determinando conexión: {e}")
            self.connection_type = "USB"
    
    def _read_mac_address(self):
        """Leer MAC address del dispositivo"""
        try:
            feature_data = bytearray(64)
            feature_data[0] = self.SERIAL_FEATURE_ID
            
            # En modo BT, la lectura de feature puede fallar
            result = self.device.get_feature_report(self.SERIAL_FEATURE_ID, 64)
            if result and len(result) > 6:
                # MAC está en bytes 1-6 (formato little endian)
                mac_bytes = result[1:7]
                self.mac_address = ':'.join(f'{b:02x}' for b in reversed(mac_bytes))
        except Exception as e:
            # No es crítico si falla
            pass
    
    def _read_firmware_info(self):
        """Leer información de firmware"""
        try:
            feature_data = bytearray(64)
            feature_data[0] = self.FIRMWARE_INFO_FEATURE_ID
            
            result = self.device.get_feature_report(self.FIRMWARE_INFO_FEATURE_ID, 64)
            if result and len(result) >= 45:
                # Hardware version: bytes 24-27
                self.hw_version = (result[24] | 
                                   (result[25] << 8) | 
                                   (result[26] << 16) | 
                                   (result[27] << 24))
                
                # Firmware version: bytes 28-31
                self.fw_version = (result[28] | 
                                   (result[29] << 8) | 
                                   (result[30] << 16) | 
                                   (result[31] << 24))
        except Exception as e:
            # No es crítico si falla
            pass
    
    def disconnect(self, power_off: bool = True):
        """
        Desconectar del dispositivo y opcionalmente apagarlo
        
        Args:
            power_off: Si True, intenta apagar el DualSense (solo Bluetooth)
        """
        if self.device:
            try:
                if power_off and self.connection_type == "Bluetooth":
                    self._send_power_off_commands()
                
                print(f"🔌 Cerrando dispositivo HID {self.model_name}...")
                self.device.close()
            except:
                pass
            self.device = None
    
    def _send_power_off_commands(self):
        """Enviar comandos para apagar el DualSense Bluetooth"""
        if not self.device:
            return
            
        import time
        print(f"🔴 Intentando apagar {self.model_name} Bluetooth...")
        
        # Método 1: Output Report con flag de Power Off
        # Basado en DS4Windows DualSenseDevice.cs
        try:
            print(f"  Método 1: Output Report 0x31 con Power Off flag...")
            # Bluetooth output report (78 bytes para DualSense)
            report = bytearray(78)
            report[0] = 0x31  # Report ID para Bluetooth
            report[1] = 0x02  # Seq tag
            report[2] = 0x03  # Flag: HID + Audio haptics 
            
            # Offset para datos en modo Bluetooth
            # Feature mask2: bit para Power Off
            report[3] = 0x14  # EnableRumbleEmulation + UseRumbleNotHaptics
            report[4] = 0x04  # Power off flag
            
            # CRC32
            crc_data = bytes([0xA2]) + bytes(report[:-4])
            crc = self._crc32_dualsense(crc_data)
            report[-4:] = crc.to_bytes(4, 'little')
            
            result = self.device.write(bytes(report))
            if result > 0:
                print(f"  ✅ Power Off enviado ({result} bytes)")
                time.sleep(0.3)
                return
        except Exception as e:
            print(f"  ⚠️ Método 1 falló: {e}")
        
        # Método 2: Output Report simplificado
        try:
            print(f"  Método 2: Output Report simplificado...")
            report = bytearray(78)
            report[0] = 0x31
            report[1] = 0x02
            report[2] = 0x08  # Solo Power control
            report[3] = 0x00
            report[4] = 0x04  # Power off
            
            crc_data = bytes([0xA2]) + bytes(report[:-4])
            crc = self._crc32_dualsense(crc_data)
            report[-4:] = crc.to_bytes(4, 'little')
            
            result = self.device.write(bytes(report))
            if result > 0:
                print(f"  ✅ Power Off simplificado enviado ({result} bytes)")
                time.sleep(0.2)
        except Exception as e:
            print(f"  ⚠️ Método 2 falló: {e}")
    
    @staticmethod
    def _crc32_dualsense(data: bytes) -> int:
        """Calcular CRC-32 para DualSense Bluetooth"""
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
            
            seen_report_ids = set()
            for attempt in range(100):
                data = self.device.read(128)
                if data and len(data) > 10:
                    report_id = data[0]
                    seen_report_ids.add(report_id)
                    
                    # Calcular offset según tipo de conexión
                    # USB: offset = 0, BT: offset = 1 (después del report ID adicional)
                    report_offset = 1 if report_id == 0x31 else 0
                    
                    # Bluetooth: Report 0x31, 78 bytes
                    if report_id == 0x31 and len(data) >= 78:
                        self.connection_type = "Bluetooth"
                        
                        # Byte 54+offset tiene info de carga
                        # Byte 53+offset tiene nivel de batería
                        charging_byte = data[54 + report_offset]
                        battery_byte = data[53 + report_offset]
                        
                        temp_charging = (charging_byte & 0x08) != 0
                        temp_full = (battery_byte & 0x20) != 0  # Full status bit
                        
                        if temp_full:
                            battery_level = 100
                        else:
                            battery_level = (battery_byte & 0x0F) * 100 // self.BATTERY_MAX
                            battery_level = min(battery_level, 100)
                        
                        level_name = self._get_level_name(battery_level)
                        
                        self.device.set_nonblocking(False)
                        return BatteryInfo(
                            percentage=battery_level,
                            voltage=None,
                            charging=temp_charging,
                            level_name=level_name
                        )
                    
                    # USB: Report 0x01, 64 bytes
                    elif report_id == 0x01 and len(data) >= 64:
                        self.connection_type = "USB"
                        
                        # En USB el offset es 0
                        # Los bytes son los mismos pero sin offset BT
                        charging_byte = data[54]
                        battery_byte = data[53]
                        
                        temp_charging = (charging_byte & 0x08) != 0
                        temp_full = (battery_byte & 0x20) != 0
                        
                        if temp_full:
                            battery_level = 100
                        else:
                            battery_level = (battery_byte & 0x0F) * 100 // self.BATTERY_MAX
                            battery_level = min(battery_level, 100)
                        
                        # Por USB siempre está cargando si no está lleno
                        if not temp_full and battery_level < 100:
                            temp_charging = True
                        
                        level_name = self._get_level_name(battery_level)
                        
                        self.device.set_nonblocking(False)
                        return BatteryInfo(
                            percentage=battery_level,
                            voltage=None,
                            charging=temp_charging,
                            level_name=level_name
                        )
            
            self.device.set_nonblocking(False)
            
            if seen_report_ids:
                print(f"Advertencia: No se pudo leer batería {self.model_name}. Report IDs vistos: {seen_report_ids}")
            
            return None
        except Exception as e:
            print(f"Error leyendo batería {self.model_name}: {e}")
            return None
    
    def _get_level_name(self, percentage: int) -> str:
        """Obtener nombre del nivel de batería"""
        if percentage >= 90:
            return "Lleno"
        elif percentage >= 60:
            return "Alto"
        elif percentage >= 40:
            return "Medio"
        elif percentage >= 20:
            return "Bajo"
        else:
            return "Crítico"
    
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
                data = self.device.read(128)
                if not data:
                    break
            
            time.sleep(0.1)
            
            # Contar paquetes
            packet_count = 0
            start_time = time.time()
            
            while time.time() - start_time < duration_seconds:
                data = self.device.read(128)
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
        Hacer vibrar el DualSense
        
        DualSense tiene haptics más avanzados que DS4, pero para compatibilidad
        usamos emulación de rumble legacy.
        """
        if not self.device:
            return
        
        try:
            intensity = max(0.0, min(1.0, intensity))
            
            left_motor = int(255 * intensity)  # Motor pesado (izquierdo)
            right_motor = int(128 * intensity)  # Motor ligero (derecho)
            
            if self.connection_type == "USB":
                self._vibrate_usb(left_motor, right_motor, duration_seconds)
            else:
                self._vibrate_bt(left_motor, right_motor, duration_seconds)
                
        except Exception as e:
            print(f"Error vibrando {self.model_name}: {e}")
    
    def _vibrate_usb(self, left_motor: int, right_motor: int, duration: float):
        """Vibrar vía USB"""
        # USB Output Report: 48 bytes útiles
        report = bytearray(48)
        report[0] = self.USB_OUTPUT_REPORT_ID  # 0x02
        
        # Byte 1: Flag de qué features aplicar
        # 0x01 = Compatibility mode (emular DS4)
        # 0x02 = Haptics (usar haptics HQ)
        # 0x04 = Right trigger effect
        # 0x08 = Left trigger effect
        report[1] = 0x01 | 0x02  # Compat mode + haptics
        
        # Byte 2: More flags
        # 0x01 = Mic mute LED
        # 0x02 = Power save control
        # 0x04 = Lightbar control
        # 0x10 = Player LEDs
        report[2] = 0x04 | 0x10  # Lightbar + Player LEDs
        
        # Byte 3-4: Rumble motors (legacy)
        report[3] = right_motor  # Motor derecho (ligero/rápido)
        report[4] = left_motor   # Motor izquierdo (pesado/lento)
        
        # Bytes 5-8: Audio (dejar en 0)
        
        # Byte 9: Mic mute LED state
        report[9] = 0x00
        
        # Bytes 10-11: Haptic power level
        report[10] = 0xFF  # Max power
        
        # Bytes 39-43: Lightbar (RGB)
        report[43] = 0x02  # Lightbar on
        report[44] = 255   # R (rojo para indicar vibración)
        report[45] = 0     # G
        report[46] = 0     # B
        
        # Enviar reporte durante la duración
        start_time = time.time()
        while time.time() - start_time < duration:
            self.device.write(bytes(report))
            time.sleep(0.01)  # 100Hz
        
        # Detener vibración y volver a azul
        report[3] = 0
        report[4] = 0
        report[44] = 0    # R
        report[45] = 0    # G
        report[46] = 255  # B (azul)
        self.device.write(bytes(report))
    
    def _vibrate_bt(self, left_motor: int, right_motor: int, duration: float):
        """Vibrar vía Bluetooth"""
        # BT Output Report: 78 bytes con CRC
        report = bytearray(78)
        report[0] = self.BT_OUTPUT_REPORT_ID  # 0x31
        report[1] = 0x02  # Sequence tag
        
        # Los datos empiezan en offset 2 en BT
        # Byte 3 (offset 2 + 1): Feature flags
        report[3] = 0x01 | 0x02  # Compat + haptics
        
        # Byte 4 (offset 2 + 2): More flags
        report[4] = 0x04 | 0x10  # Lightbar + Player LEDs
        
        # Byte 5-6: Rumble
        report[5] = right_motor
        report[6] = left_motor
        
        # Lightbar
        report[45] = 0x02  # Lightbar on
        report[46] = 255   # R
        report[47] = 0     # G
        report[48] = 0     # B
        
        # Calcular CRC-32 para BT
        crc_head = bytes([0xA2])
        crc = ~self._crc32_dualsense(crc_head)
        crc = ~self._crc32_dualsense(report[0:74]) ^ crc
        
        report[74] = crc & 0xFF
        report[75] = (crc >> 8) & 0xFF
        report[76] = (crc >> 16) & 0xFF
        report[77] = (crc >> 24) & 0xFF
        
        # Enviar durante duración
        start_time = time.time()
        while time.time() - start_time < duration:
            self.device.write(bytes(report))
            time.sleep(0.01)
        
        # Detener
        report[5] = 0
        report[6] = 0
        report[46] = 0    # R
        report[47] = 0    # G
        report[48] = 255  # B
        
        crc = ~self._crc32_dualsense(crc_head)
        crc = ~self._crc32_dualsense(report[0:74]) ^ crc
        report[74] = crc & 0xFF
        report[75] = (crc >> 8) & 0xFF
        report[76] = (crc >> 16) & 0xFF
        report[77] = (crc >> 24) & 0xFF
        
        self.device.write(bytes(report))
    
    def set_lightbar(self, r: int, g: int, b: int):
        """Establecer color del lightbar"""
        if not self.device:
            return
        
        try:
            if self.connection_type == "USB":
                self._set_lightbar_usb(r, g, b)
            else:
                self._set_lightbar_bt(r, g, b)
        except Exception as e:
            print(f"Error estableciendo lightbar: {e}")
    
    def _set_lightbar_usb(self, r: int, g: int, b: int):
        """Establecer lightbar vía USB"""
        report = bytearray(48)
        report[0] = self.USB_OUTPUT_REPORT_ID
        report[1] = 0x00
        report[2] = 0x04  # Lightbar control
        
        report[43] = 0x02  # Lightbar on
        report[44] = r & 0xFF
        report[45] = g & 0xFF
        report[46] = b & 0xFF
        
        self.device.write(bytes(report))
    
    def _set_lightbar_bt(self, r: int, g: int, b: int):
        """Establecer lightbar vía Bluetooth"""
        report = bytearray(78)
        report[0] = self.BT_OUTPUT_REPORT_ID
        report[1] = 0x02
        report[3] = 0x00
        report[4] = 0x04  # Lightbar control
        
        report[45] = 0x02
        report[46] = r & 0xFF
        report[47] = g & 0xFF
        report[48] = b & 0xFF
        
        # CRC
        crc_head = bytes([0xA2])
        crc = ~self._crc32_dualsense(crc_head)
        crc = ~self._crc32_dualsense(report[0:74]) ^ crc
        
        report[74] = crc & 0xFF
        report[75] = (crc >> 8) & 0xFF
        report[76] = (crc >> 16) & 0xFF
        report[77] = (crc >> 24) & 0xFF
        
        self.device.write(bytes(report))
    
    def get_info(self) -> dict:
        """Obtener información del dispositivo"""
        return {
            'model': self.model_name,
            'is_edge': self.is_edge,
            'connection_type': self.connection_type,
            'mac_address': self.mac_address,
            'hw_version': self.hw_version,
            'fw_version': self.fw_version
        }
