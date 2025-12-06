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
            
            # Detectar tipo de conexión inmediatamente
            self._detect_connection_type()
            
            return True
        except Exception as e:
            print(f"Error conectando DS4: {e}")
            return False
    
    def _detect_connection_type(self):
        """Detectar si es conexión USB o Bluetooth"""
        if not self.device:
            return
        
        try:
            self.device.set_nonblocking(True)
            
            # Leer algunos paquetes para determinar tipo de conexión
            for _ in range(30):
                try:
                    data = self.device.read(78)  # BT reports son más grandes
                    if data and len(data) > 0:
                        report_id = data[0]
                        if report_id == 0x11:
                            self.connection_type = "Bluetooth"
                            print(f"   🔵 DS4 detectado via Bluetooth (Report 0x11)")
                            break
                        elif report_id == 0x01:
                            self.connection_type = "USB"
                            print(f"   🔌 DS4 detectado via USB (Report 0x01)")
                            break
                except:
                    break
            
            self.device.set_nonblocking(False)
        except Exception as e:
            print(f"   ⚠️ Error detectando tipo de conexión: {e}")
            self.device.set_nonblocking(False)
    
    def disconnect(self, power_off: bool = True):
        """
        Desconectar del dispositivo y opcionalmente apagarlo
        
        Args:
            power_off: Si True, intenta apagar el DS4 (solo funciona en Bluetooth)
        """
        if self.device:
            try:
                if power_off and self.connection_type == "Bluetooth":
                    self._send_power_off_commands()
                
                # Siempre cerrar el dispositivo HID
                print(f"🔌 Cerrando dispositivo HID DS4...")
                self.device.close()
            except:
                pass
            self.device = None
    
    def _send_power_off_commands(self):
        """Enviar comandos para apagar el DS4 Bluetooth"""
        if not self.device:
            return
            
        print(f"🔴 Intentando apagar DS4 Bluetooth...")
        
        # Método 1: Output Report con flag de Power Off
        # Basado en DS4Windows PowerOff
        try:
            print(f"  Método 1: Output Report 0x11 con Power Off flag...")
            # Bluetooth output report
            report = bytearray(78)
            report[0] = 0x11  # Report ID para Bluetooth
            report[1] = 0xC0  # Flags: HID + CRC
            report[2] = 0x20  # Flags adicionales
            report[3] = 0xF3  # Feature flags: LED + Motor + PowerOff
            report[4] = 0x04  # Power Off flag (bit 2)
            
            # CRC32 en los últimos 4 bytes
            crc_data = bytes([0xA2]) + bytes(report[:-4])
            crc = self._crc32_ds4(crc_data)
            report[-4:] = crc.to_bytes(4, 'little')
            
            result = self.device.write(bytes(report))
            if result > 0:
                print(f"  ✅ Power Off enviado ({result} bytes)")
                time.sleep(0.3)
                return
        except Exception as e:
            print(f"  ⚠️ Método 1 falló: {e}")
        
        # Método 2: Feature Report 0x05 (Quick Disconnect - DS4Windows)
        try:
            print(f"  Método 2: Feature Report 0x05 Quick Disconnect...")
            disconnect_report = bytearray(37)
            disconnect_report[0] = 0x05  # Report ID
            disconnect_report[1] = 0x07  # Quick disconnect command
            
            result = self.device.send_feature_report(bytes(disconnect_report))
            if result > 0:
                print(f"  ✅ Quick Disconnect enviado ({result} bytes)")
                time.sleep(0.2)
                return
        except Exception as e:
            print(f"  ⚠️ Método 2 falló: {e}")
        
        # Método 3: SET 0xA1 - Disable Bluetooth
        try:
            print(f"  Método 3: SET 0xA1 (Disable Bluetooth)...")
            bt_disable_report = bytearray(2)
            bt_disable_report[0] = 0xA1
            bt_disable_report[1] = 0x00
            
            result = self.device.send_feature_report(bytes(bt_disable_report))
            if result > 0:
                print(f"  ✅ Bluetooth deshabilitado ({result} bytes)")
                time.sleep(0.2)
        except Exception as e:
            print(f"  ⚠️ Método 3 falló: {e}")
        
        # Método 4: Feature Report 0xE2 (Dongle disconnect)
        try:
            print(f"  Método 4: Feature 0xE2 (Dongle disconnect)...")
            disconnect_report = bytearray(64)
            disconnect_report[0] = 0xE2
            disconnect_report[1] = 0x02
            
            result = self.device.send_feature_report(bytes(disconnect_report))
            if result > 0:
                print(f"  ✅ Dongle disconnect enviado ({result} bytes)")
        except Exception as e:
            print(f"  ⚠️ Método 4 falló: {e}")
    
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
            
            seen_report_ids = set()
            empty_reads = 0
            # Más intentos y tolerancia para Bluetooth
            max_attempts = 200 if self.connection_type == "Bluetooth" else 100
            max_empty = 50 if self.connection_type == "Bluetooth" else 20
            read_size = 78 if self.connection_type == "Bluetooth" else 64
            
            for attempt in range(max_attempts):
                try:
                    data = self.device.read(read_size)
                except Exception as read_error:
                    # Error de lectura - dispositivo probablemente desconectado
                    print(f"⚠️ DS4 error de lectura: {read_error}")
                    self.device = None
                    return None
                
                if not data:
                    empty_reads += 1
                    # Si hay muchas lecturas vacías, el dispositivo está desconectado
                    if empty_reads > max_empty:
                        print(f"⚠️ DS4 sin respuesta después de {empty_reads} lecturas vacías")
                        return None
                    # Pequeña pausa para no saturar en modo no-blocking
                    time.sleep(0.001)
                    continue
                    
                if len(data) > 10:
                    report_id = data[0]
                    seen_report_ids.add(report_id)
                    
                    # Report 0x11 para Bluetooth
                    if report_id == 0x11 and len(data) >= 33:
                        battery_byte = data[32]
                        cable_state_byte = data[31]
                        battery_level = (battery_byte & 0x0f) * 100 // 8
                        
                        # Verificar múltiples bits para estado de cable/carga
                        usb_connected = (cable_state_byte & 0x01) != 0
                        usb_active = (cable_state_byte & 0x02) != 0
                        charging_bit = (cable_state_byte & 0x10) != 0
                        
                        # Si el cable USB está conectado o el bit de carga está activo
                        charging = charging_bit or usb_connected or usb_active
                        self.connection_type = "Bluetooth"
                        
                        # Debug - mostrar siempre para diagnosticar
                        print(f"DS4 BT Report 0x11: battery_byte=0x{battery_byte:02x} ({battery_level}%), cable_state=0x{cable_state_byte:02x} (USB:{usb_connected}, Active:{usb_active}, Charging:{charging_bit}), final_charging={charging}")
                        
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
                        cable_state_byte = data[29]
                        battery_level = (battery_byte & 0x0f) * 100 // 8
                        
                        # Verificar múltiples bits para estado de cable/carga
                        usb_connected = (cable_state_byte & 0x01) != 0
                        usb_active = (cable_state_byte & 0x02) != 0
                        charging_bit = (cable_state_byte & 0x10) != 0
                        
                        # Si está por USB y la batería no está llena, asumir que está cargando
                        # (algunos DS4 no reportan correctamente el bit de carga cuando están conectados por USB)
                        charging = charging_bit or usb_connected or usb_active or (battery_level < 95)
                        self.connection_type = "USB"
                        
                        # Debug - mostrar siempre para diagnosticar
                        print(f"DS4 USB Report 0x01: battery_byte=0x{battery_byte:02x} ({battery_level}%), cable_state=0x{cable_state_byte:02x} (USB:{usb_connected}, Active:{usb_active}, Charging:{charging_bit}), final_charging={charging}")
                        
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
            
            self.device.set_nonblocking(False)
            
            # Si no se encontró batería, mostrar qué report IDs se vieron
            if seen_report_ids:
                print(f"Advertencia: No se pudo leer batería DS4. Report IDs vistos: {seen_report_ids}")
            
            return None
        except OSError as e:
            # OSError típicamente indica que el dispositivo se desconectó
            print(f"⚠️ DS4 desconectado (OSError): {e}")
            self.device = None
            return None
        except Exception as e:
            print(f"Error leyendo batería DS4: {e}")
            # Si es un error severo, marcar como desconectado
            if "device" in str(e).lower() or "read" in str(e).lower():
                self.device = None
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
                try:
                    data = self.device.read(64)
                    if not data:
                        break
                except:
                    self.device = None
                    return None
            
            time.sleep(0.1)
            
            # Contar paquetes
            packet_count = 0
            empty_count = 0
            max_empty = 500 if self.connection_type == "Bluetooth" else 100  # Más tolerancia en BT
            start_time = time.time()
            
            while time.time() - start_time < duration_seconds:
                try:
                    data = self.device.read(78 if self.connection_type == "Bluetooth" else 64)
                    if data:
                        packet_count += 1
                        empty_count = 0
                    else:
                        empty_count += 1
                        if empty_count > max_empty:
                            # Demasiadas lecturas vacías
                            break
                        # Pequeña pausa para no saturar CPU en modo no-blocking
                        time.sleep(0.001)
                except Exception as e:
                    print(f"   ⚠️ DS4 polling error: {e}")
                    self.device = None
                    return None
            
            elapsed = time.time() - start_time
            try:
                self.device.set_nonblocking(False)
            except:
                pass
            
            # Evitar división por cero
            if packet_count > 0 and elapsed > 0.01:
                polling_rate_hz = packet_count / elapsed
                polling_interval_ms = 1000.0 / polling_rate_hz
                
                return PollingInfo(
                    rate_hz=round(polling_rate_hz, 1),
                    interval_ms=round(polling_interval_ms, 2),
                    packet_count=packet_count
                )
            elif packet_count == 0:
                # No se recibieron paquetes - retornar valor por defecto
                # Esto es común en Bluetooth cuando el DS4 está en reposo
                print(f"   ⚠️ DS4: No se recibieron paquetes durante medición (conexión: {self.connection_type})")
                # Si estamos en Bluetooth, usar un valor típico estimado
                if self.connection_type == "Bluetooth":
                    return PollingInfo(
                        rate_hz=250.0,  # Valor típico BT
                        interval_ms=4.0,
                        packet_count=0
                    )
                return PollingInfo(
                    rate_hz=0.0,
                    interval_ms=0.0,
                    packet_count=0
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
