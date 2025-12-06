"""
DeviceManager - Gestión automática de todos los controladores conectados
"""

import hid
import time
from typing import Dict, List, Optional, Union
from datetime import datetime
from readers.joycon_reader import JoyConReader
from readers.ds4_reader import DS4Reader
from readers.xbox_reader import XboxReader
from models.device_models import DeviceInfo, BatteryInfo, PollingInfo, ColorsInfo


class DeviceManager:
    """Gestor de dispositivos - detecta y gestiona todos los controladores"""
    
    def __init__(self):
        """Inicializar el gestor de dispositivos"""
        self.devices: Dict[str, Union[JoyConReader, DS4Reader, XboxReader]] = {}
        self.device_info: Dict[str, dict] = {}
        self.last_scan = None
    
    def scan_devices(self) -> List[str]:
        """
        Escanear todos los dispositivos conectados
        
        Returns:
            Lista de IDs de dispositivos encontrados
        """
        found_devices = []
        
        try:
            all_devices = hid.enumerate()
            
            for device in all_devices:
                vendor_id = device['vendor_id']
                product_id = device['product_id']
                path = device['path']
                
                # Joy-Con Left (0x2006)
                if vendor_id == 0x057E and product_id == 0x2006:
                    device_id = f"joycon_l_{path.hex()[-8:]}"
                    if device_id not in self.devices:
                        reader = JoyConReader(path, product_id)
                        if reader.connect():
                            self.devices[device_id] = reader
                            self.device_info[device_id] = {
                                'type': 'Joy-Con',
                                'side': 'Left',
                                'model': 'Joy-Con (L)',
                                'path': path,
                                'connected_at': datetime.now()
                            }
                            found_devices.append(device_id)
                
                # Joy-Con Right (0x2007)
                elif vendor_id == 0x057E and product_id == 0x2007:
                    device_id = f"joycon_r_{path.hex()[-8:]}"
                    if device_id not in self.devices:
                        reader = JoyConReader(path, product_id)
                        if reader.connect():
                            self.devices[device_id] = reader
                            self.device_info[device_id] = {
                                'type': 'Joy-Con',
                                'side': 'Right',
                                'model': 'Joy-Con (R)',
                                'path': path,
                                'connected_at': datetime.now()
                            }
                            found_devices.append(device_id)
                
                # DualShock 4 v1 (0x05C4)
                elif vendor_id == 0x054C and product_id == 0x05C4:
                    # Filtrar solo el interface del gamepad (usage_page=1, usage=5)
                    usage_page = device.get('usage_page', 0)
                    usage = device.get('usage', 0)
                    if usage_page != 1 or usage != 5:
                        continue  # Ignorar interfaces de audio/touchpad
                    
                    device_id = f"ds4_v1_{path.hex()[-8:]}"
                    if device_id not in self.devices:
                        reader = DS4Reader(path, product_id)
                        if reader.connect():
                            self.devices[device_id] = reader
                            self.device_info[device_id] = {
                                'type': 'DualShock 4',
                                'version': 'v1',
                                'model': 'DualShock 4 v1',
                                'path': path,
                                'connected_at': datetime.now()
                            }
                            found_devices.append(device_id)
                
                # DualShock 4 v2 (0x09CC)
                elif vendor_id == 0x054C and product_id == 0x09CC:
                    # Filtrar solo el interface del gamepad (usage_page=1, usage=5)
                    usage_page = device.get('usage_page', 0)
                    usage = device.get('usage', 0)
                    if usage_page != 1 or usage != 5:
                        continue  # Ignorar interfaces de audio/touchpad
                    
                    # Usar serial number para ID único (más confiable que path)
                    serial = device.get('serial_number', '')
                    if serial:
                        device_id = f"ds4_v2_{serial[-8:]}"
                    else:
                        device_id = f"ds4_v2_{path.hex()[-8:]}"
                    
                    if device_id not in self.devices:
                        print(f"🎮 DS4 v2 detectado: {device_id} (Serial: {serial})")
                        reader = DS4Reader(path, product_id)
                        if reader.connect():
                            print(f"✅ DS4 v2 conectado: {device_id}")
                            self.devices[device_id] = reader
                            self.device_info[device_id] = {
                                'type': 'DualShock 4',
                                'version': 'v2',
                                'model': 'DualShock 4 v2',
                                'path': path,
                                'connected_at': datetime.now()
                            }
                            found_devices.append(device_id)
                        else:
                            print(f"❌ Error conectando DS4 v2: {device_id}")
                
                # Xbox Controllers
                elif vendor_id == 0x045E and product_id in XboxReader.KNOWN_PRODUCT_IDS:
                    device_id = f"xbox_{path.hex()[-8:]}"
                    if device_id not in self.devices:
                        reader = XboxReader(path, product_id)
                        if reader.connect():
                            self.devices[device_id] = reader
                            self.device_info[device_id] = {
                                'type': 'Xbox Controller',
                                'model': reader.get_model_name(),
                                'path': path,
                                'connected_at': datetime.now()
                            }
                            found_devices.append(device_id)
            
            self.last_scan = datetime.now()
            
        except Exception as e:
            print(f"Error escaneando dispositivos: {e}")
        
        return found_devices
    
    def get_device_list(self) -> List[dict]:
        """Obtener lista de todos los dispositivos conectados con información básica"""
        devices_list = []
        
        for device_id, reader in self.devices.items():
            info = self.device_info.get(device_id, {})
            device_data = {
                'id': device_id,
                'type': info.get('type', 'Unknown'),
                'model': info.get('model', 'Unknown'),
                'connected_at': info.get('connected_at'),
            }
            
            # Agregar info específica por tipo
            if 'side' in info:
                device_data['side'] = info['side']
            if 'version' in info:
                device_data['version'] = info['version']
            
            devices_list.append(device_data)
        
        return devices_list
    
    def get_device_info(self, device_id: str) -> Optional[DeviceInfo]:
        """Obtener información completa de un dispositivo específico"""
        reader = self.devices.get(device_id)
        if not reader:
            print(f"❌ Device {device_id} no encontrado en self.devices")
            print(f"   Devices disponibles: {list(self.devices.keys())}")
            return None
        
        info = self.device_info.get(device_id, {})
        print(f"✅ Device {device_id} encontrado, obteniendo info...")
        
        try:
            # Polling rate PRIMERO (antes de hacer subcomandos)
            print(f"   📊 Midiendo polling rate...")
            polling = reader.measure_polling_rate(duration_seconds=1.5)
            if not polling:
                print(f"   ⚠️ Polling retornó None - dispositivo posiblemente desconectado")
                # Si no hay polling, verificar si está realmente conectado
                return None
            
            # Batería DESPUÉS (usa subcomandos que pueden interferir)
            print(f"   📊 Leyendo batería...")
            battery = reader.get_battery()
            if not battery:
                print(f"   ⚠️ Batería retornó None - dispositivo posiblemente desconectado")
                return None
            
            # Información específica por tipo
            extra_data = {}
            
            if isinstance(reader, JoyConReader):
                print(f"   📊 Leyendo info de Joy-Con...")
                colors = reader.get_colors()
                serial = reader.get_serial_number()
                firmware = reader.get_firmware_version()
                
                extra_data = {
                    'colors': colors.model_dump() if colors else None,
                    'serial_number': serial,
                    'firmware_version': firmware
                }
                print(f"   ✅ Info Joy-Con obtenida: Serial={serial}, FW={firmware}")
            
            elif isinstance(reader, DS4Reader):
                connection = reader.get_connection_type()
                extra_data = {
                    'connection_type': connection,
                    'version': info.get('version', 'Unknown')
                }
            
            elif isinstance(reader, XboxReader):
                extra_data = {
                    'model_name': reader.get_model_name()
                }
            
            return DeviceInfo(
                id=device_id,
                type=info.get('type', 'Unknown'),
                name=info.get('model', 'Unknown'),
                connected=True,
                battery=battery,
                polling=polling,
                last_update=datetime.now(),
                **extra_data
            )
        
        except Exception as e:
            print(f"❌ Error obteniendo info de {device_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def vibrate_device(self, device_id: str, duration: float = 1.0, intensity: float = 0.7) -> bool:
        """Hacer vibrar un dispositivo específico"""
        reader = self.devices.get(device_id)
        if not reader:
            return False
        
        try:
            reader.vibrate(duration, intensity)
            return True
        except Exception as e:
            print(f"Error vibrando {device_id}: {e}")
            return False
    
    def disconnect_device_gracefully(self, device_id: str) -> bool:
        """Desconectar un dispositivo enviando comando de desconexión (solo Joy-Con)"""
        reader = self.devices.get(device_id)
        if not reader:
            return False
        
        # Solo Joy-Cons soportan desconexión por comando
        if not isinstance(reader, JoyConReader):
            return False
        
        try:
            reader.disconnect()
            # Remover de la lista de dispositivos
            del self.devices[device_id]
            if device_id in self.device_info:
                del self.device_info[device_id]
            return True
        except Exception as e:
            print(f"Error desconectando {device_id}: {e}")
            return False
    
    def disconnect_device(self, device_id: str):
        """Desconectar un dispositivo específico"""
        reader = self.devices.get(device_id)
        if reader:
            reader.disconnect()
            del self.devices[device_id]
            if device_id in self.device_info:
                del self.device_info[device_id]
    
    def disconnect_all(self):
        """Desconectar todos los dispositivos"""
        for device_id in list(self.devices.keys()):
            self.disconnect_device(device_id)
    
    def refresh_devices(self) -> List[str]:
        """
        Refrescar lista de dispositivos (detectar nuevos, remover desconectados)
        
        Returns:
            Lista de IDs de dispositivos actualmente conectados
        """
        # Escanear nuevos dispositivos
        current_devices = self.scan_devices()
        
        # Remover dispositivos desconectados
        for device_id in list(self.devices.keys()):
            if device_id not in current_devices:
                try:
                    # Verificar si sigue conectado intentando leer
                    reader = self.devices[device_id]
                    if isinstance(reader, (JoyConReader, DS4Reader)):
                        battery = reader.get_battery()
                        if battery is None:
                            self.disconnect_device(device_id)
                except:
                    self.disconnect_device(device_id)
        
        return list(self.devices.keys())
