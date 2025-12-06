"""
Reader para Joy-Con (L y R)
Implementa lectura de batería con voltaje, colores, serial, firmware, polling rate
"""

import hid
import time
from typing import Optional, Tuple, Dict
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from models.device_models import BatteryInfo, ColorInfo, ColorsInfo, PollingInfo


# Variable global para packet counter
_timming_byte = 0


class JoyConReader:
    """Lector para Joy-Con Left y Right"""
    
    VENDOR_ID = 0x057E
    PRODUCT_ID_L = 0x2006
    PRODUCT_ID_R = 0x2007
    
    def __init__(self, device_path: bytes, product_id: int):
        """
        Inicializar reader de Joy-Con
        
        Args:
            device_path: Path del dispositivo HID
            product_id: 0x2006 (L) o 0x2007 (R)
        """
        self.device_path = device_path
        self.product_id = product_id
        self.side = "L" if product_id == self.PRODUCT_ID_L else "R"
        self.device = None
        self.bluetooth_address = self._extract_bluetooth_address()
    
    def _extract_bluetooth_address(self) -> Optional[str]:
        """
        Extraer la dirección Bluetooth desde el device_path usando la API de Windows
        
        Returns:
            Dirección MAC en formato DC68EB8346EE o None
        """
        try:
            import winreg
            path_str = self.device_path.decode('utf-8') if isinstance(self.device_path, bytes) else self.device_path
            
            # El path HID contiene información que podemos usar para buscar en el registro
            # Formato típico: \\?\hid#vid_057e&pid_2007&col01#7&36c421ca&0&0000#{...}
            
            # Intentar obtener del registro de dispositivos Bluetooth
            # Los dispositivos Bluetooth se registran con su MAC en:
            # HKLM\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices
            
            try:
                key_path = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as devices_key:
                    # Enumerar todos los dispositivos Bluetooth
                    i = 0
                    while True:
                        try:
                            device_mac = winreg.EnumKey(devices_key, i)
                            # Verificar si es un Joy-Con comparando VID/PID
                            with winreg.OpenKey(devices_key, device_mac) as device_key:
                                try:
                                    vid_pid = winreg.QueryValueEx(device_key, "VID")[0]
                                    # VID de Nintendo es 0x057E, PID es 0x2006 (L) o 0x2007 (R)
                                    if vid_pid == 0x057E:
                                        # Este es un dispositivo Nintendo, verificar PID
                                        try:
                                            pid = winreg.QueryValueEx(device_key, "PID")[0]
                                            if pid == self.product_id:
                                                return device_mac.upper()
                                        except:
                                            pass
                                except:
                                    pass
                            i += 1
                        except OSError:
                            break
            except Exception as e:
                print(f"Error buscando en registro Bluetooth: {e}")
            
            # Si no se encuentra en el registro, intentar desde el device path
            # Buscar patrón específico de Bluetooth
            import re
            # Buscar patrón como &col01#7&XXXXXXXX donde XXXXXXXX podría ser relacionado
            # Pero esto no es confiable, retornar None
            return None
            
        except Exception as e:
            print(f"Error extrayendo MAC: {e}")
            return None
        
    def connect(self) -> bool:
        """Conectar al dispositivo"""
        try:
            self.device = hid.device()
            self.device.open_path(self.device_path)
            self.device.set_nonblocking(False)
            
            # Configurar modo de input report 0x30 (una sola vez al conectar)
            time.sleep(0.05)
            self._send_subcmd(0x03, bytes([0x30]))
            time.sleep(0.05)
            
            return True
        except Exception as e:
            print(f"Error conectando Joy-Con {self.side}: {e}")
            return False
    
    def disconnect(self):
        """Desconectar del dispositivo"""
        if self.device:
            try:
                # Enviar subcomando 0x06 con 0x00 para desconectar (sleep mode)
                print(f"Enviando comando de desconexión a Joy-Con {self.side}...")
                self._send_subcmd(0x06, bytes([0x00]))
                time.sleep(0.1)
                self.device.close()
            except Exception as e:
                print(f"Error al desconectar Joy-Con {self.side}: {e}")
            self.device = None
    
    def _send_subcmd(self, subcmd: int, data: Optional[bytes] = None):
        """Enviar subcomando al Joy-Con"""
        global _timming_byte
        
        report = bytearray(49)
        report[0] = 0x01  # Output report ID
        report[1] = _timming_byte & 0xF  # Packet counter
        _timming_byte += 1
        # Rumble data (neutral)
        report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
        report[10] = subcmd  # Subcommand
        
        if data:
            report[11:11+len(data)] = data
        
        self.device.write(bytes(report))
    
    def get_battery(self) -> Optional[BatteryInfo]:
        """
        Obtener información de batería usando voltaje regulado (subcomando 0x50)
        Método exacto de jc_toolkit
        """
        if not self.device:
            return None
        
        global _timming_byte
        
        for error_reading in range(20):
            try:
                # Preparar comando
                buf = bytearray(49)
                buf[0] = 0x01
                buf[1] = _timming_byte & 0xF
                _timming_byte += 1
                buf[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
                buf[10] = 0x50  # subcmd 0x50
                
                try:
                    self.device.write(bytes(buf))
                except OSError as e:
                    print(f"⚠️ Joy-Con error de escritura: {e}")
                    self.device = None
                    return None
                
                # Leer respuesta
                for retry in range(8):
                    try:
                        reply = self.device.read(64, timeout_ms=64)
                    except OSError as e:
                        print(f"⚠️ Joy-Con error de lectura: {e}")
                        self.device = None
                        return None
                    
                    if reply and len(reply) >= 0x11:
                        if len(reply) > 0xE and reply[0x0D] == 0xD0 and reply[0x0E] == 0x50:
                            battery_byte = reply[0x2]
                            batt_volt_low = reply[0xF]
                            batt_volt_high = reply[0x10]
                            
                            # Combinar voltaje
                            battery_voltage = batt_volt_low | (batt_volt_high << 8)
                            
                            # Convertir a porcentaje con fórmulas de jc_toolkit
                            if battery_voltage < 0x560:
                                battery_percent = 1
                            elif 0x55F < battery_voltage < 0x5A0:
                                battery_percent = ((battery_voltage - 0x60) & 0xFF) / 7.0 + 1
                            elif 0x59F < battery_voltage < 0x5E0:
                                battery_percent = ((battery_voltage - 0xA0) & 0xFF) / 2.625 + 11
                            elif 0x5DF < battery_voltage < 0x618:
                                battery_percent = (battery_voltage - 0x5E0) / 1.8965 + 36
                            elif 0x617 < battery_voltage < 0x658:
                                battery_percent = ((battery_voltage - 0x18) & 0xFF) / 1.8529 + 66
                            elif battery_voltage > 0x657:
                                battery_percent = 100
                            else:
                                battery_percent = 0
                            
                            charging = bool((battery_byte >> 4) & 0x1)
                            battery_volts = (battery_voltage * 2.5) / 1000.0
                            
                            # Determinar nivel
                            if battery_percent >= 90:
                                level_name = "Lleno"
                            elif battery_percent >= 60:
                                level_name = "Alto"
                            elif battery_percent >= 40:
                                level_name = "Medio"
                            elif battery_percent >= 20:
                                level_name = "Bajo"
                            else:
                                level_name = "Crítico"
                            
                            return BatteryInfo(
                                percentage=int(battery_percent),
                                voltage=round(battery_volts, 2),
                                charging=charging,
                                level_name=level_name
                            )
            except OSError as e:
                print(f"⚠️ Joy-Con desconectado (OSError): {e}")
                self.device = None
                return None
            except Exception as e:
                print(f"Error leyendo batería: {e}")
                continue
        
        return None
    
    def _read_spi(self, address: int, size: int) -> Optional[bytes]:
        """Leer datos de la memoria SPI"""
        if not self.device:
            return None
        
        try:
            # Limpiar buffer
            self.device.set_nonblocking(True)
            for _ in range(50):
                data = self.device.read(64)
                if not data:
                    break
            self.device.set_nonblocking(False)
            
            # Preparar comando SPI Read
            spi_data = bytearray(5)
            spi_data[0] = address & 0xFF
            spi_data[1] = (address >> 8) & 0xFF
            spi_data[2] = (address >> 16) & 0xFF
            spi_data[3] = (address >> 24) & 0xFF
            spi_data[4] = size
            
            self._send_subcmd(0x10, spi_data)
            
            # Leer respuesta
            for attempt in range(10):
                time.sleep(0.05)
                data = self.device.read(64, timeout_ms=500)
                
                if data and len(data) >= 20:
                    if data[0] == 0x21 and data[13] == 0x90 and data[14] == 0x10:
                        addr_reply = data[15] | (data[16] << 8) | (data[17] << 16) | (data[18] << 24)
                        if addr_reply == address:
                            return bytes(data[20:20+size])
            
            return None
        except Exception as e:
            print(f"Error leyendo SPI: {e}")
            return None
    
    def get_colors(self) -> Optional[ColorsInfo]:
        """Leer colores desde SPI (dirección 0x6050)"""
        color_data = self._read_spi(0x6050, 12)
        
        if color_data and len(color_data) >= 12:
            try:
                return ColorsInfo(
                    body=ColorInfo(
                        r=color_data[0], g=color_data[1], b=color_data[2],
                        hex=f"#{color_data[0]:02X}{color_data[1]:02X}{color_data[2]:02X}"
                    ),
                    buttons=ColorInfo(
                        r=color_data[3], g=color_data[4], b=color_data[5],
                        hex=f"#{color_data[3]:02X}{color_data[4]:02X}{color_data[5]:02X}"
                    ),
                    left_grip=ColorInfo(
                        r=color_data[6], g=color_data[7], b=color_data[8],
                        hex=f"#{color_data[6]:02X}{color_data[7]:02X}{color_data[8]:02X}"
                    ),
                    right_grip=ColorInfo(
                        r=color_data[9], g=color_data[10], b=color_data[11],
                        hex=f"#{color_data[9]:02X}{color_data[10]:02X}{color_data[11]:02X}"
                    )
                )
            except Exception as e:
                print(f"Error parseando colores: {e}")
                return None
        
        return None
    
    def get_serial_number(self) -> Optional[str]:
        """Leer número de serie desde SPI"""
        for address in [0x6000, 0x6001]:
            serial_data = self._read_spi(address, 16)
            
            if serial_data:
                try:
                    serial = serial_data.decode('ascii', errors='ignore').strip('\x00').strip()
                    if serial and len(serial) > 5:
                        return serial
                except:
                    pass
        
        return None
    
    def get_firmware_version(self) -> Optional[str]:
        """Obtener versión de firmware (subcomando 0x02)"""
        if not self.device:
            return None
        
        try:
            # Limpiar buffer
            self.device.set_nonblocking(True)
            for _ in range(50):
                data = self.device.read(64)
                if not data:
                    break
            self.device.set_nonblocking(False)
            
            self._send_subcmd(0x02)
            
            for attempt in range(10):
                time.sleep(0.05)
                data = self.device.read(64, timeout_ms=500)
                
                if data and len(data) >= 20:
                    if data[0] == 0x21 and data[14] == 0x02:
                        fw_major = data[15]
                        fw_minor = data[16]
                        return f"{fw_major}.{fw_minor}"
            
            return None
        except Exception as e:
            print(f"Error leyendo firmware: {e}")
            return None
    
    def measure_polling_rate(self, duration_seconds: float = 2.0) -> Optional[PollingInfo]:
        """Medir polling rate"""
        if not self.device:
            return None
        
        try:
            self.device.set_nonblocking(True)
            
            # Limpiar buffer
            cleared = 0
            for _ in range(100):
                data = self.device.read(64)
                if data:
                    cleared += 1
                if not data:
                    break
            
            print(f"      Buffer limpiado: {cleared} paquetes descartados")
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
            
            print(f"      Paquetes recibidos en {elapsed:.2f}s: {packet_count}")
            
            if packet_count > 0:
                polling_rate_hz = packet_count / elapsed
                polling_interval_ms = 1000.0 / polling_rate_hz
                
                return PollingInfo(
                    rate_hz=round(polling_rate_hz, 1),
                    interval_ms=round(polling_interval_ms, 2),
                    packet_count=packet_count
                )
            
            print(f"      ❌ NO se recibieron paquetes durante {duration_seconds}s")
            return None
        except Exception as e:
            print(f"Error midiendo polling rate: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def vibrate(self, duration_seconds: float = 1.0, intensity: float = 0.6):
        """Hacer vibrar el Joy-Con"""
        if not self.device:
            return
        
        try:
            # Habilitar vibración
            self._send_subcmd(0x48, bytes([0x01]))
            time.sleep(0.05)
            
            # Encodear rumble correctamente (frecuencia 160Hz es la más perceptible)
            freq_hex = 0x5064  # 160 Hz
            freq_hf = (freq_hex >> 8) & 0xFF
            freq_lf = freq_hex & 0xFF
            
            # Amplitud basada en intensidad
            amp = int(0x64 * intensity)
            amp = max(0x00, min(0xC8, amp))  # Limitar entre 0x00 y 0xC8
            
            # Construir datos de rumble (4 bytes por motor, 8 bytes total)
            rumble_data = bytes([
                freq_lf,      # Frecuencia baja byte bajo (motor L)
                amp + freq_hf,  # Amplitud + frecuencia alta byte alto (motor L)
                freq_lf,      # Frecuencia baja byte bajo (motor R)
                amp + freq_hf,  # Amplitud + frecuencia alta byte alto (motor R)
                freq_lf,      # Frecuencia baja byte bajo (motor L)
                amp + freq_hf,  # Amplitud + frecuencia alta byte alto (motor L)
                freq_lf,      # Frecuencia baja byte bajo (motor R)
                amp + freq_hf   # Amplitud + frecuencia alta byte alto (motor R)
            ])
            
            # Enviar rumble
            global _timming_byte
            report = bytearray(49)
            report[0] = 0x10  # Rumble only report
            report[1] = _timming_byte & 0xF
            _timming_byte += 1
            report[2:10] = rumble_data
            
            self.device.write(bytes(report))
            time.sleep(duration_seconds)
            
            # Detener vibración (rumble neutral)
            report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
            self.device.write(bytes(report))
        except Exception as e:
            print(f"Error vibrando: {e}")
    
    def set_player_lights(self, player_num: int = 1, flash: bool = False):
        """
        Asignar número de jugador (1-8) al Joy-Con
        
        Args:
            player_num: Número de jugador (1-8)
            flash: Si True, las luces parpadean. Si False, están fijas
        """
        if not self.device or player_num < 1 or player_num > 8:
            return
        
        try:
            # Patrones de LED según número de jugador
            # Bits 0-3: LED 1,2,3,4 (fijos)
            # Bits 4-7: LED 1,2,3,4 (parpadeo)
            led_patterns = {
                1: 0x01,  # LED 1
                2: 0x03,  # LED 1,2
                3: 0x07,  # LED 1,2,3
                4: 0x0F,  # LED 1,2,3,4
                5: 0x09,  # LED 1,4
                6: 0x30,  # LED 1,2 parpadeando (0x03 << 4)
                7: 0x0D,  # LED 1,3,4
                8: 0x06,  # LED 2,3
            }
            
            lights_byte = led_patterns.get(player_num, 0x01)
            
            # Si se solicita flash y no es jugador 6 (que ya parpadea), mover a nibble alto
            if flash and player_num != 6:
                lights_byte = (lights_byte & 0x0F) << 4
            
            # Enviar subcommand 0x30
            self._send_subcmd(0x30, bytes([lights_byte]))
            print(f"✅ Player lights set to {player_num} (pattern: 0x{lights_byte:02X})")
        except Exception as e:
            print(f"Error setting player lights: {e}")
    
    def get_buttons(self) -> Optional[Dict[str, bool]]:
        """
        Leer el estado actual de los botones del Joy-Con
        Basado en input report 0x30 (standard full mode)
        
        Returns:
            Dict con el estado de cada botón (True=presionado, False=no presionado)
        """
        if not self.device:
            return None
        
        try:
            # Leer input report (ya debería estar en modo 0x30)
            data = self.device.read(64, timeout_ms=100)
            
            if not data or len(data) < 12:
                return None
            
            # Solo procesar reports 0x30, 0x31, 0x32, 0x33 (standard input reports)
            report_id = data[0]
            if report_id not in [0x30, 0x31, 0x32, 0x33, 0x3F]:
                return None
            
            # Para report 0x3F (simple HID), los bytes de botón son diferentes
            if report_id == 0x3F:
                # Byte 1-2: Button status para 0x3F
                byte1 = data[1]
                byte2 = data[2]
                
                buttons = {
                    # Byte 1
                    'Down': bool(byte1 & 0x01),
                    'Right': bool(byte1 & 0x02),
                    'Left': bool(byte1 & 0x04),
                    'Up': bool(byte1 & 0x08),
                    'SL (L)': bool(byte1 & 0x10) if self.side == 'L' else False,
                    'SR (L)': bool(byte1 & 0x20) if self.side == 'L' else False,
                    'SL (R)': bool(byte1 & 0x10) if self.side == 'R' else False,
                    'SR (R)': bool(byte1 & 0x20) if self.side == 'R' else False,
                    # Byte 2
                    'Minus': bool(byte2 & 0x01),
                    'Plus': bool(byte2 & 0x02),
                    'L Stick': bool(byte2 & 0x04),
                    'R Stick': bool(byte2 & 0x08),
                    'Home': bool(byte2 & 0x10),
                    'Capture': bool(byte2 & 0x20),
                    'L': bool(byte2 & 0x40) if self.side == 'L' else False,
                    'R': bool(byte2 & 0x40) if self.side == 'R' else False,
                    'ZL': bool(byte2 & 0x80) if self.side == 'L' else False,
                    'ZR': bool(byte2 & 0x80) if self.side == 'R' else False,
                }
            else:
                # Standard input report (0x30, 0x31, etc.)
                # Bytes 3, 4, 5 contienen los botones
                byte3 = data[3]  # Right Joy-Con buttons
                byte4 = data[4]  # Shared buttons
                byte5 = data[5]  # Left Joy-Con buttons
                
                buttons = {
                    # Byte 3 (Right Joy-Con)
                    'Y': bool(byte3 & 0x01),
                    'X': bool(byte3 & 0x02),
                    'B': bool(byte3 & 0x04),
                    'A': bool(byte3 & 0x08),
                    'SR (R)': bool(byte3 & 0x10),
                    'SL (R)': bool(byte3 & 0x20),
                    'R': bool(byte3 & 0x40),
                    'ZR': bool(byte3 & 0x80),
                    # Byte 4 (Shared)
                    'Minus': bool(byte4 & 0x01),
                    'Plus': bool(byte4 & 0x02),
                    'R Stick': bool(byte4 & 0x04),
                    'L Stick': bool(byte4 & 0x08),
                    'Home': bool(byte4 & 0x10),
                    'Capture': bool(byte4 & 0x20),
                    # Byte 5 (Left Joy-Con)
                    'Down': bool(byte5 & 0x01),
                    'Up': bool(byte5 & 0x02),
                    'Right': bool(byte5 & 0x04),
                    'Left': bool(byte5 & 0x08),
                    'SR (L)': bool(byte5 & 0x10),
                    'SL (L)': bool(byte5 & 0x20),
                    'L': bool(byte5 & 0x40),
                    'ZL': bool(byte5 & 0x80),
                }
            
            return buttons
            
        except Exception as e:
            return None
