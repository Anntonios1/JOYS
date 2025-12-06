"""
DeviceManager - Gestión automática de todos los controladores conectados
"""

import hid
import time
import asyncio
from typing import Dict, List, Optional, Union, Callable, Any
from datetime import datetime
from readers.joycon_reader import JoyConReader
from readers.ds4_reader import DS4Reader
from readers.dualsense_reader import DualSenseReader
from readers.xbox_reader import XboxReader
from models.device_models import DeviceInfo, BatteryInfo, PollingInfo, ColorsInfo
from db_manager import DatabaseManager
from cache_manager import CacheManager


class DeviceManager:
    """Gestor de dispositivos - detecta y gestiona todos los controladores"""
    
    # Tiempo de cooldown para dispositivos que fallaron (evita reconexión en bucle)
    COOLDOWN_SECONDS = 30
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """Inicializar el gestor de dispositivos"""
        self.devices: Dict[str, Union[JoyConReader, DS4Reader, DualSenseReader, XboxReader]] = {}
        self.device_info: Dict[str, dict] = {}
        self.last_scan = None
        self.db = db_manager
        self.cache = CacheManager()
        # Cooldown: dispositivos que fallaron recientemente {device_id: timestamp}
        self._cooldown_devices: Dict[str, float] = {}
        # Callbacks para eventos
        self._on_device_connected: Optional[Callable] = None
        self._on_device_disconnected: Optional[Callable] = None
        # Control de scanner
        self._scanner_running = False
        self._last_device_ids: set = set()
    
    def set_callbacks(self, on_connected: Callable = None, on_disconnected: Callable = None):
        """Configurar callbacks para eventos de dispositivos"""
        self._on_device_connected = on_connected
        self._on_device_disconnected = on_disconnected
    
    async def _emit_connected(self, device_id: str, device_info: dict):
        """Emitir evento de dispositivo conectado"""
        if self._on_device_connected:
            try:
                await self._on_device_connected({
                    'device_id': device_id,
                    'info': device_info,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                print(f"Error emitiendo evento connected: {e}")
    
    async def _emit_disconnected(self, device_id: str):
        """Emitir evento de dispositivo desconectado"""
        if self._on_device_disconnected:
            try:
                await self._on_device_disconnected({
                    'device_id': device_id,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                print(f"Error emitiendo evento disconnected: {e}")
    
    async def start_background_scanner(self, interval: float = 1.0):
        """Iniciar escaneo en background para detectar cambios"""
        self._scanner_running = True
        self._last_device_ids = set(self.devices.keys())
        print(f"🔍 Scanner de dispositivos iniciado (intervalo: {interval}s)")
        
        while self._scanner_running:
            try:
                # Escanear nuevos dispositivos
                new_ids = self.scan_devices()
                current_ids = set(self.devices.keys())
                
                # Detectar nuevos dispositivos
                for device_id in new_ids:
                    if device_id not in self._last_device_ids:
                        info = self.device_info.get(device_id, {})
                        print(f"🎮 Nuevo dispositivo detectado: {device_id}")
                        await self._emit_connected(device_id, info)
                
                # Detectar dispositivos desconectados
                disconnected = self._last_device_ids - current_ids
                for device_id in disconnected:
                    print(f"❌ Dispositivo desconectado: {device_id}")
                    await self._emit_disconnected(device_id)
                
                self._last_device_ids = current_ids
                
            except Exception as e:
                print(f"Error en scanner: {e}")
            
            await asyncio.sleep(interval)
    
    def stop_background_scanner(self):
        """Detener el scanner de background"""
        self._scanner_running = False
        print("🛑 Scanner de dispositivos detenido")
    
    def _setup_joycon_on_connect(self, reader: JoyConReader, device_id: str):
        """
        Configurar Joy-Con al conectar: asignar número de jugador + vibración
        """
        try:
            # Contar Joy-Cons conectados para asignar número de jugador
            joycon_count = sum(1 for did in self.devices.keys() if 'joycon' in did.lower())
            player_num = min(joycon_count, 8)  # 1-8
            
            # Guardar en base de datos
            if self.db:
                self.db.set_player_number(device_id, player_num)
            
            # Asignar número de jugador (luces LED)
            reader.set_player_lights(player_num, flash=False)
            time.sleep(0.1)
            
            # Vibración de bienvenida (corta y suave)
            reader.vibrate(duration_seconds=0.3, intensity=0.5)
            
            print(f"🎮 {device_id}: Player {player_num} asignado + vibración de bienvenida")
        except Exception as e:
            print(f"⚠️ Error configurando Joy-Con al conectar: {e}")
    
    def _is_in_cooldown(self, device_id: str) -> bool:
        """Verificar si un dispositivo está en cooldown después de fallar"""
        if device_id not in self._cooldown_devices:
            return False
        
        elapsed = time.time() - self._cooldown_devices[device_id]
        if elapsed >= self.COOLDOWN_SECONDS:
            # Cooldown expiró, remover de la lista
            del self._cooldown_devices[device_id]
            print(f"🔄 Cooldown expirado para {device_id}, permitiendo reconexión")
            return False
        
        return True
    
    def _add_to_cooldown(self, device_id: str):
        """Añadir dispositivo a cooldown después de fallo"""
        self._cooldown_devices[device_id] = time.time()
        print(f"⏳ {device_id} en cooldown por {self.COOLDOWN_SECONDS}s")
    
    def _verify_device_responds(self, reader, device_type: str) -> bool:
        """Verificar que un dispositivo responde antes de añadirlo"""
        try:
            battery = reader.get_battery()
            if battery is None:
                print(f"   ⚠️ {device_type} no responde a lectura inicial")
                return False
            print(f"   ✓ {device_type} respondió: {battery}%")
            return True
        except Exception as e:
            print(f"   ⚠️ {device_type} error en lectura inicial: {e}")
            return False
    
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
                            # Marcar como conectado en DB (NO borramos métricas)
                            if self.db:
                                self.db.mark_device_connected(device_id)
                                print(f"   ✅ Sesión iniciada para {device_id}")
                            
                            self.devices[device_id] = reader
                            self.device_info[device_id] = {
                                'type': 'Joy-Con',
                                'side': 'Left',
                                'model': 'Joy-Con (L)',
                                'path': path,
                                'connected_at': datetime.now()
                            }
                            found_devices.append(device_id)
                            
                            # 🎮 Efectos de conexión: asignar jugador + vibración
                            self._setup_joycon_on_connect(reader, device_id)
                
                # Joy-Con Right (0x2007)
                elif vendor_id == 0x057E and product_id == 0x2007:
                    device_id = f"joycon_r_{path.hex()[-8:]}"
                    if device_id not in self.devices:
                        reader = JoyConReader(path, product_id)
                        if reader.connect():
                            # Marcar como conectado en DB (NO borramos métricas)
                            if self.db:
                                self.db.mark_device_connected(device_id)
                                print(f"   ✅ Sesión iniciada para {device_id}")
                            
                            self.devices[device_id] = reader
                            self.device_info[device_id] = {
                                'type': 'Joy-Con',
                                'side': 'Right',
                                'model': 'Joy-Con (R)',
                                'path': path,
                                'connected_at': datetime.now()
                            }
                            found_devices.append(device_id)
                            
                            # 🎮 Efectos de conexión: asignar jugador + vibración
                            self._setup_joycon_on_connect(reader, device_id)
                
                # DualShock 4 v1 (0x05C4)
                elif vendor_id == 0x054C and product_id == 0x05C4:
                    # Filtrar solo el interface del gamepad (usage_page=1, usage=5)
                    usage_page = device.get('usage_page', 0)
                    usage = device.get('usage', 0)
                    if usage_page != 1 or usage != 5:
                        continue  # Ignorar interfaces de audio/touchpad
                    
                    device_id = f"ds4_v1_{path.hex()[-8:]}"
                    if device_id not in self.devices:
                        # Verificar cooldown
                        if self._is_in_cooldown(device_id):
                            continue
                        
                        reader = DS4Reader(path, product_id)
                        if reader.connect():
                            # Verificar que responda antes de añadir
                            if self._verify_device_responds(reader, "DS4 v1"):
                                self.devices[device_id] = reader
                                self.device_info[device_id] = {
                                    'type': 'DualShock 4',
                                    'version': 'v1',
                                    'model': 'DualShock 4 v1',
                                    'path': path,
                                    'connected_at': datetime.now()
                                }
                                found_devices.append(device_id)
                            else:
                                reader.disconnect()
                                self._add_to_cooldown(device_id)
                
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
                        # Verificar cooldown
                        if self._is_in_cooldown(device_id):
                            continue
                        
                        print(f"🎮 DS4 v2 detectado: {device_id} (Serial: {serial})")
                        reader = DS4Reader(path, product_id)
                        if reader.connect():
                            # Verificar que responda antes de añadir
                            if self._verify_device_responds(reader, "DS4 v2"):
                                print(f"✅ DS4 v2 conectado y verificado: {device_id}")
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
                                print(f"❌ DS4 v2 no responde, entrando en cooldown: {device_id}")
                                reader.disconnect()
                                self._add_to_cooldown(device_id)
                        else:
                            print(f"❌ Error conectando DS4 v2: {device_id}")
                
                # DualSense (0x0CE6)
                elif vendor_id == 0x054C and product_id == 0x0CE6:
                    # Filtrar solo el interface del gamepad (usage_page=1, usage=5)
                    usage_page = device.get('usage_page', 0)
                    usage = device.get('usage', 0)
                    if usage_page != 1 or usage != 5:
                        continue  # Ignorar interfaces de audio/touchpad
                    
                    serial = device.get('serial_number', '')
                    if serial:
                        device_id = f"dualsense_{serial[-8:]}"
                    else:
                        device_id = f"dualsense_{path.hex()[-8:]}"
                    
                    if device_id not in self.devices:
                        # Verificar cooldown
                        if self._is_in_cooldown(device_id):
                            continue
                        
                        print(f"🎮 DualSense detectado: {device_id} (Serial: {serial})")
                        reader = DualSenseReader(path, product_id)
                        if reader.connect():
                            # Verificar que responda antes de añadir
                            if self._verify_device_responds(reader, "DualSense"):
                                print(f"✅ DualSense conectado y verificado: {device_id} ({reader.connection_type})")
                                self.devices[device_id] = reader
                                self.device_info[device_id] = {
                                    'type': 'DualSense',
                                    'version': 'Standard',
                                    'model': 'DualSense',
                                    'path': path,
                                    'connected_at': datetime.now()
                                }
                                found_devices.append(device_id)
                            else:
                                print(f"❌ DualSense no responde, entrando en cooldown: {device_id}")
                                reader.disconnect()
                                self._add_to_cooldown(device_id)
                        else:
                            print(f"❌ Error conectando DualSense: {device_id}")
                
                # DualSense Edge (0x0DF2)
                elif vendor_id == 0x054C and product_id == 0x0DF2:
                    usage_page = device.get('usage_page', 0)
                    usage = device.get('usage', 0)
                    if usage_page != 1 or usage != 5:
                        continue
                    
                    serial = device.get('serial_number', '')
                    if serial:
                        device_id = f"dualsense_edge_{serial[-8:]}"
                    else:
                        device_id = f"dualsense_edge_{path.hex()[-8:]}"
                    
                    if device_id not in self.devices:
                        # Verificar cooldown
                        if self._is_in_cooldown(device_id):
                            continue
                        
                        print(f"🎮 DualSense Edge detectado: {device_id}")
                        reader = DualSenseReader(path, product_id)
                        if reader.connect():
                            # Verificar que responda antes de añadir
                            if self._verify_device_responds(reader, "DualSense Edge"):
                                print(f"✅ DualSense Edge conectado y verificado: {device_id} ({reader.connection_type})")
                                self.devices[device_id] = reader
                                self.device_info[device_id] = {
                                    'type': 'DualSense',
                                    'version': 'Edge',
                                    'model': 'DualSense Edge',
                                    'path': path,
                                    'connected_at': datetime.now()
                                }
                                found_devices.append(device_id)
                            else:
                                print(f"❌ DualSense Edge no responde, entrando en cooldown: {device_id}")
                                reader.disconnect()
                                self._add_to_cooldown(device_id)
                        else:
                            print(f"❌ Error conectando DualSense Edge: {device_id}")
                
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
            # Intentar obtener batería desde caché
            battery = self.cache.get(device_id, 'battery')
            if battery:
                print(f"   💾 Batería desde caché: {battery.percentage}%")
            else:
                print(f"   📊 Leyendo batería desde HID...")
                battery = reader.get_battery()
                if not battery:
                    print(f"   ⚠️ Batería retornó None - dispositivo posiblemente desconectado")
                    return None
                # Guardar en caché
                self.cache.set(device_id, 'battery', battery)
                print(f"   💾 Batería cacheada: {battery.percentage}%")
            
            # Intentar obtener polling desde caché
            polling = self.cache.get(device_id, 'polling')
            if polling:
                print(f"   💾 Polling desde caché: {polling.rate_hz} Hz")
            else:
                print(f"   📊 Midiendo polling rate...")
                try:
                    polling = reader.measure_polling_rate(duration_seconds=1.5)
                except Exception as e:
                    print(f"   ⚠️ Error midiendo polling: {e}")
                    polling = None
                
                if not polling:
                    # Usar valor por defecto en lugar de fallar
                    print(f"   ⚠️ Polling retornó None - usando valor por defecto")
                    from api_v2.models import PollingInfo
                    polling = PollingInfo(rate_hz=0.0, interval_ms=0.0, packet_count=0)
                
                # Guardar en caché (incluso si es el valor por defecto)
                self.cache.set(device_id, 'polling', polling)
                print(f"   💾 Polling cacheado: {polling.rate_hz} Hz")
            
            # Información específica por tipo
            extra_data = {}
            
            if isinstance(reader, JoyConReader):
                # Intentar obtener datos estáticos desde caché
                static_data = self.cache.get(device_id, 'static')
                
                if static_data:
                    print(f"   💾 Datos estáticos desde caché")
                    extra_data = static_data
                else:
                    # Verificar si ya tenemos datos estáticos en DB
                    db_static_data = None
                    if self.db:
                        db_static_data = self.db.get_device_static_data(device_id)
                    
                    if db_static_data:
                        # Ya tenemos datos estáticos en DB
                        print(f"   💾 Datos estáticos cargados desde DB")
                        extra_data = {
                            'colors': db_static_data.get('colors'),
                            'serial_number': db_static_data.get('serial_number'),
                            'firmware_version': db_static_data.get('firmware_version')
                        }
                    else:
                        # Primera vez, leer desde SPI (SOLO UNA VEZ)
                        print(f"   📊 Leyendo info de Joy-Con desde SPI (primera vez)...")
                        colors = reader.get_colors()
                        serial = reader.get_serial_number()
                        firmware = reader.get_firmware_version()
                        
                        extra_data = {
                            'colors': colors.model_dump() if colors else None,
                            'serial_number': serial,
                            'firmware_version': firmware
                        }
                        print(f"   ✅ Info Joy-Con obtenida: Serial={serial}, FW={firmware}")
                        
                        # Guardar datos estáticos en DB
                        if self.db and serial:
                            device_type = f"Joy-Con ({info.get('side', 'Unknown')})"
                            self.db.save_device_static_data(
                                device_id=device_id,
                                device_type=device_type,
                                serial_number=serial,
                                firmware_version=firmware,
                                colors=colors.model_dump() if colors else None
                            )
                            print(f"   💾 Datos estáticos guardados en DB")
                    
                    # Guardar en caché (permanente hasta desconexión)
                    self.cache.set(device_id, 'static', extra_data)
                    print(f"   💾 Datos estáticos cacheados")
            
            elif isinstance(reader, DS4Reader):
                # Intentar obtener datos estáticos desde caché
                static_data = self.cache.get(device_id, 'static')
                
                if static_data:
                    print(f"   💾 Datos estáticos desde caché")
                    extra_data = static_data
                else:
                    # Verificar si ya tenemos datos estáticos en DB
                    db_static_data = None
                    if self.db:
                        db_static_data = self.db.get_device_static_data(device_id)
                    
                    connection = reader.get_connection_type()
                    extra_data = {
                        'connection_type': connection,
                        'version': info.get('version', 'Unknown')
                    }
                    
                    # Guardar datos estáticos en DB si no existen
                    if self.db and not db_static_data:
                        device_type = f"DualShock 4 {info.get('version', '')}"
                        self.db.save_device_static_data(
                            device_id=device_id,
                            device_type=device_type,
                            serial_number=None,
                            firmware_version=None,
                            colors=None
                        )
                        print(f"   💾 Datos estáticos guardados en DB")
                    
                    # Guardar en caché
                    self.cache.set(device_id, 'static', extra_data)
                    print(f"   💾 Datos estáticos cacheados")
            
            elif isinstance(reader, DualSenseReader):
                # Intentar obtener datos estáticos desde caché
                static_data = self.cache.get(device_id, 'static')
                
                if static_data:
                    print(f"   💾 Datos estáticos desde caché")
                    extra_data = static_data
                else:
                    # Verificar si ya tenemos datos estáticos en DB
                    db_static_data = None
                    if self.db:
                        db_static_data = self.db.get_device_static_data(device_id)
                    
                    ds_info = reader.get_info()
                    connection = reader.get_connection_type()
                    extra_data = {
                        'connection_type': connection,
                        'version': 'Edge' if ds_info.get('is_edge') else 'Standard',
                        'mac_address': ds_info.get('mac_address'),
                        'hw_version': ds_info.get('hw_version'),
                        'fw_version': ds_info.get('fw_version')
                    }
                    
                    # Guardar datos estáticos en DB si no existen
                    if self.db and not db_static_data:
                        device_type = ds_info.get('model', 'DualSense')
                        self.db.save_device_static_data(
                            device_id=device_id,
                            device_type=device_type,
                            serial_number=ds_info.get('mac_address'),
                            firmware_version=str(ds_info.get('fw_version')) if ds_info.get('fw_version') else None,
                            colors=None
                        )
                        print(f"   💾 Datos estáticos guardados en DB")
                    
                    # Guardar en caché
                    self.cache.set(device_id, 'static', extra_data)
                    print(f"   💾 Datos estáticos cacheados")
            
            elif isinstance(reader, XboxReader):
                # Intentar obtener datos estáticos desde caché
                static_data = self.cache.get(device_id, 'static')
                
                if static_data:
                    print(f"   💾 Datos estáticos desde caché")
                    extra_data = static_data
                else:
                    # Verificar si ya tenemos datos estáticos en DB
                    db_static_data = None
                    if self.db:
                        db_static_data = self.db.get_device_static_data(device_id)
                    
                    extra_data = {
                        'model_name': reader.get_model_name()
                    }
                    
                    # Guardar datos estáticos en DB si no existen
                    if self.db and not db_static_data:
                        device_type = reader.get_model_name()
                        self.db.save_device_static_data(
                            device_id=device_id,
                            device_type=device_type,
                            serial_number=None,
                            firmware_version=None,
                            colors=None
                        )
                        print(f"   💾 Datos estáticos guardados en DB")
                    
                    # Guardar en caché
                    self.cache.set(device_id, 'static', extra_data)
                    print(f"   💾 Datos estáticos cacheados")
            
            # Obtener player_number de la DB si existe
            player_number = None
            if self.db:
                player_number = self.db.get_player_number(device_id)
                if player_number:
                    extra_data['player_number'] = player_number
            
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
    
    def disconnect_device_gracefully(self, device_id: str, power_off: bool = True) -> bool:
        """
        Desconectar un dispositivo enviando comando de desconexión/apagado
        
        Funciona para:
        - Joy-Con: Envía comando de apagado y desconecta
        - DS4/DS5 Bluetooth: Intenta enviar power off (puede reconectarse)
        - DS4/DS5 USB: Solo cierra HID (hay que desenchufar)
        
        Args:
            device_id: ID del dispositivo
            power_off: Si True, intenta apagar el dispositivo (Bluetooth)
            
        Returns:
            True si se desconectó exitosamente
        """
        reader = self.devices.get(device_id)
        if not reader:
            return False
        
        try:
            # Para Joy-Con
            if isinstance(reader, JoyConReader):
                reader.disconnect()
            # Para DS4 o DualSense, pasar parámetro power_off
            elif hasattr(reader, 'disconnect'):
                # Verificar si el método acepta power_off
                import inspect
                sig = inspect.signature(reader.disconnect)
                if 'power_off' in sig.parameters:
                    reader.disconnect(power_off=power_off)
                else:
                    reader.disconnect()
            
            # Remover de la lista de dispositivos
            del self.devices[device_id]
            if device_id in self.device_info:
                del self.device_info[device_id]
            return True
        except Exception as e:
            print(f"Error desconectando {device_id}: {e}")
            return False
    
    def disconnect_device(self, device_id: str, add_to_cooldown: bool = False):
        """
        Desconectar un dispositivo específico (mantiene historial)
        
        Args:
            device_id: ID del dispositivo
            add_to_cooldown: Si True, añade al cooldown para evitar reconexión inmediata
        """
        reader = self.devices.get(device_id)
        if reader:
            reader.disconnect()
            del self.devices[device_id]
            if device_id in self.device_info:
                del self.device_info[device_id]
            # Limpiar caché del dispositivo
            self.cache.clear_device(device_id)
            # Marcar como desconectado en DB (NO borramos métricas)
            if self.db:
                self.db.mark_device_disconnected(device_id)
            
            # Si se desconectó por fallo, añadir a cooldown
            if add_to_cooldown:
                self._add_to_cooldown(device_id)
            
            print(f"   🔌 {device_id} desconectado (historial preservado)")
    
    def is_device_connected(self, device_id: str) -> bool:
        """
        Verificar rápidamente si un dispositivo sigue conectado
        
        Returns:
            True si el dispositivo responde, False si no
        """
        reader = self.devices.get(device_id)
        if not reader:
            return False
        
        # Verificar si el reader interno ya está marcado como desconectado
        if hasattr(reader, 'device') and reader.device is None:
            return False
        
        try:
            # Intentar leer batería como verificación rápida
            battery = reader.get_battery()
            
            # Si después de leer, el device quedó en None, está desconectado
            if hasattr(reader, 'device') and reader.device is None:
                return False
                
            return battery is not None
        except:
            return False
    
    def check_disconnected_devices(self) -> List[str]:
        """
        Verificar y remover dispositivos desconectados
        
        Returns:
            Lista de IDs de dispositivos que fueron desconectados
        """
        disconnected = []
        
        for device_id in list(self.devices.keys()):
            if not self.is_device_connected(device_id):
                # Desconectar CON cooldown ya que fue un fallo
                self.disconnect_device(device_id, add_to_cooldown=True)
                disconnected.append(device_id)
        
        return disconnected
    
    def disconnect_all(self):
        """Desconectar todos los dispositivos (mantiene historial)"""
        for device_id in list(self.devices.keys()):
            self.disconnect_device(device_id)
        # Limpiar todo el caché
        self.cache.clear_all()
        print("   🗑️ Caché completamente limpiado")
    
    def get_all_buttons(self) -> Dict[str, Dict[str, bool]]:
        """
        Obtener el estado de los botones de todos los dispositivos que lo soporten
        
        Returns:
            Dict con {device_id: {button_name: pressed}}
        """
        result = {}
        
        for device_id, reader in self.devices.items():
            # Solo Joy-Cons soportan lectura de botones por ahora
            if isinstance(reader, JoyConReader):
                buttons = reader.get_buttons()
                if buttons:
                    result[device_id] = buttons
        
        return result
    
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
