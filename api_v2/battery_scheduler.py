"""
Battery Scheduler - Sistema inteligente de monitoreo de batería

Este módulo implementa un scheduler que:
1. Solicita batería a los dispositivos cada 2 minutos
2. Guarda automáticamente en la base de datos
3. Detecta desconexiones y las marca apropiadamente
4. Envía actualizaciones via WebSocket
5. Mantiene historial completo (sin purga automática)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
import threading


@dataclass
class DeviceStatus:
    """Estado de conexión de un dispositivo"""
    device_id: str
    is_connected: bool = True
    is_charging: bool = False  # Nuevo: estado de carga
    last_seen: datetime = field(default_factory=datetime.now)
    last_battery: Optional[int] = None
    last_polling: Optional[float] = None
    disconnect_time: Optional[datetime] = None
    reconnect_count: int = 0


class BatteryScheduler:
    """
    Scheduler inteligente para monitoreo de batería
    
    Características:
    - Health check rápido cada 5 segundos para detectar desconexiones
    - Recolecta y guarda batería cada 2 minutos
    - Detecta desconexiones automáticamente
    - Guarda historial en DB sin purga automática
    - Notifica cambios via callbacks
    """
    
    # Intervalo de recolección/guardado en segundos
    COLLECTION_INTERVAL = 120  # 2 minutos para guardar en DB
    
    # Intervalo de health check rápido (detección de desconexiones)
    HEALTH_CHECK_INTERVAL = 5  # 5 segundos
    
    # Tiempo antes de marcar dispositivo como desconectado (segundos)
    DISCONNECT_TIMEOUT = 6  # 6 segundos (un poco más que el health check)
    
    def __init__(self, 
                 device_manager=None, 
                 db_manager=None,
                 on_battery_update: Optional[Callable] = None,
                 on_device_disconnect: Optional[Callable] = None,
                 on_device_reconnect: Optional[Callable] = None):
        """
        Inicializar el scheduler
        
        Args:
            device_manager: Gestor de dispositivos
            db_manager: Gestor de base de datos
            on_battery_update: Callback cuando se actualiza batería
            on_device_disconnect: Callback cuando se desconecta dispositivo
            on_device_reconnect: Callback cuando se reconecta dispositivo
        """
        self.device_manager = device_manager
        self.db_manager = db_manager
        
        # Callbacks
        self.on_battery_update = on_battery_update
        self.on_device_disconnect = on_device_disconnect
        self.on_device_reconnect = on_device_reconnect
        self.on_charging_change = None  # Nuevo callback para cambio de carga
        
        # Estado de dispositivos
        self._device_status: Dict[str, DeviceStatus] = {}
        
        # Anti-duplicados para eventos
        self._last_charging_event: Dict[str, float] = {}  # device_id -> timestamp
        self._charging_event_cooldown = 3.0  # segundos
        
        # Control del scheduler
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Estadísticas
        self.stats = {
            'total_collections': 0,
            'successful_reads': 0,
            'failed_reads': 0,
            'disconnections_detected': 0,
            'reconnections_detected': 0,
            'last_collection': None,
            'started_at': None
        }
    
    async def start(self):
        """Iniciar el scheduler"""
        if self._running:
            print("⚠️ BatteryScheduler ya está ejecutándose")
            return
        
        self._running = True
        self.stats['started_at'] = datetime.now()
        
        # Iniciar ambos loops
        self._task = asyncio.create_task(self._collection_loop())
        self._health_task = asyncio.create_task(self._health_check_loop())
        
        print(f"🔋 BatteryScheduler iniciado")
        print(f"   📊 Guardado DB: cada {self.COLLECTION_INTERVAL}s")
        print(f"   🔍 Health check: cada {self.HEALTH_CHECK_INTERVAL}s")
    
    async def stop(self):
        """Detener el scheduler"""
        self._running = False
        
        # Cancelar ambas tareas
        for task in [self._task, getattr(self, '_health_task', None)]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        print("🔋 BatteryScheduler detenido")
    
    async def _emit_charging_change(self, device_id: str, charging: bool, battery: int):
        """Emitir evento de cambio de carga con debounce anti-duplicados"""
        import time
        now = time.time()
        
        # Verificar si es duplicado
        if device_id in self._last_charging_event:
            elapsed = now - self._last_charging_event[device_id]
            if elapsed < self._charging_event_cooldown:
                print(f"   ⚠️ Evento charging_change ignorado (duplicado, hace {elapsed:.1f}s)")
                return
        
        self._last_charging_event[device_id] = now
        
        if self.on_charging_change:
            await self._safe_callback(self.on_charging_change, {
                'device_id': device_id,
                'charging': charging,
                'battery': battery,
                'timestamp': datetime.now().isoformat()
            })
            print(f"   ⚡ {device_id[:20]}...: {'Cargando' if charging else 'No cargando'}")
    
    async def _collection_loop(self):
        """Loop principal de recolección (guarda en DB)"""
        # Primera recolección inmediata
        await self._collect_all_batteries()
        
        while self._running:
            try:
                # Esperar el intervalo
                await asyncio.sleep(self.COLLECTION_INTERVAL)
                
                if self._running:
                    await self._collect_all_batteries()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Error en collection loop: {e}")
                import traceback
                traceback.print_exc()
    
    async def _health_check_loop(self):
        """Loop rápido para detectar desconexiones"""
        while self._running:
            try:
                await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
                
                if self._running:
                    await self._quick_health_check()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Error en health check loop: {e}")
    
    async def _quick_health_check(self):
        """Verificación rápida de dispositivos conectados"""
        if not self.device_manager:
            return
        
        # Primero, pedir al device_manager que verifique desconexiones
        disconnected = self.device_manager.check_disconnected_devices()
        
        # Notificar desconexiones detectadas
        for device_id in disconnected:
            status = self._device_status.get(device_id)
            if status and status.is_connected:
                await self._handle_device_disconnect(device_id)
        
        # Obtener dispositivos actuales del device_manager
        current_device_ids = set(self.device_manager.devices.keys())
        known_device_ids = set(self._device_status.keys())
        
        # Detectar nuevos dispositivos
        new_devices = current_device_ids - known_device_ids
        for device_id in new_devices:
            await self._handle_device_connect(device_id)
            
            # También leer batería inicial y detectar estado de carga
            reader = self.device_manager.devices.get(device_id)
            if reader:
                try:
                    battery = reader.get_battery()
                    if battery:
                        self._device_status[device_id].last_battery = battery.percentage
                        self._device_status[device_id].is_charging = getattr(battery, 'charging', False)
                except:
                    pass
        
        # Verificar cambios en dispositivos existentes
        for device_id in current_device_ids:
            status = self._device_status.get(device_id)
            if not status:
                continue
                
            reader = self.device_manager.devices.get(device_id)
            if reader:
                try:
                    battery = reader.get_battery()
                    if battery:
                        # Actualizar last_seen
                        status.last_seen = datetime.now()
                        
                        # Detectar reconexión si estaba marcado como desconectado
                        if not status.is_connected:
                            await self._handle_device_reconnect(device_id)
                        
                        # Detectar cambio de carga
                        current_charging = getattr(battery, 'charging', False)
                        if current_charging != status.is_charging:
                            status.is_charging = current_charging
                            await self._emit_charging_change(device_id, current_charging, battery.percentage)
                except Exception:
                    pass
    
    async def _collect_all_batteries(self):
        """Recolectar batería de todos los dispositivos"""
        async with self._lock:
            self.stats['total_collections'] += 1
            self.stats['last_collection'] = datetime.now()
            
            if not self.device_manager:
                return
            
            print(f"\n🔋 [Scheduler] Recolectando baterías... ({datetime.now().strftime('%H:%M:%S')})")
            
            # Obtener dispositivos actuales
            current_device_ids = set(self.device_manager.devices.keys())
            known_device_ids = set(self._device_status.keys())
            
            # Detectar nuevos dispositivos (reconexiones)
            new_devices = current_device_ids - known_device_ids
            for device_id in new_devices:
                await self._handle_device_connect(device_id)
            
            # Detectar dispositivos desconectados
            missing_devices = known_device_ids - current_device_ids
            for device_id in missing_devices:
                status = self._device_status.get(device_id)
                if status and status.is_connected:
                    await self._handle_device_disconnect(device_id)
            
            # Recolectar batería de dispositivos conectados
            for device_id in current_device_ids:
                await self._collect_device_battery(device_id)
            
            print(f"   ✅ Recolección completada - {len(current_device_ids)} dispositivos")
    
    async def _collect_device_battery(self, device_id: str):
        """Recolectar batería de un dispositivo específico"""
        try:
            reader = self.device_manager.devices.get(device_id)
            if not reader:
                return
            
            # Leer batería directamente (sin caché)
            battery = reader.get_battery()
            
            if battery is None:
                # Falló la lectura - posible desconexión
                self.stats['failed_reads'] += 1
                status = self._device_status.get(device_id)
                
                if status:
                    # Verificar timeout de desconexión
                    time_since_last = (datetime.now() - status.last_seen).total_seconds()
                    if time_since_last > self.DISCONNECT_TIMEOUT:
                        await self._handle_device_disconnect(device_id)
                return
            
            # Lectura exitosa
            self.stats['successful_reads'] += 1
            battery_level = battery.percentage
            
            # Medir polling rate también
            polling = reader.measure_polling_rate(duration_seconds=1.0)
            polling_rate = polling.rate_hz if polling else None
            
            # Actualizar estado
            if device_id not in self._device_status:
                self._device_status[device_id] = DeviceStatus(device_id=device_id)
            
            status = self._device_status[device_id]
            
            # Detectar reconexión
            if not status.is_connected:
                await self._handle_device_reconnect(device_id)
            
            # Calcular tasa de descarga si hay batería anterior
            drain_rate = None
            if status.last_battery is not None and battery_level < status.last_battery:
                # Hubo descarga
                time_diff_hours = (datetime.now() - status.last_seen).total_seconds() / 3600
                if time_diff_hours > 0.01:  # Al menos ~36 segundos
                    battery_diff = status.last_battery - battery_level
                    drain_rate = battery_diff / time_diff_hours
            
            # Detectar carga completa
            full_charge = battery_level >= 100
            
            status.last_seen = datetime.now()
            status.last_battery = battery_level
            status.last_polling = polling_rate
            status.is_connected = True
            
            # Detectar cambio de estado de carga
            current_charging = battery.charging if hasattr(battery, 'charging') else False
            if current_charging != status.is_charging:
                status.is_charging = current_charging
                await self._emit_charging_change(device_id, current_charging, battery_level)
            
            # Guardar en base de datos
            if self.db_manager:
                self.db_manager.save_device_metrics(
                    device_id=device_id,
                    battery_level=battery_level,
                    polling_rate=polling_rate
                )
                
                # Actualizar especificaciones de batería con datos reales
                device_info = reader.get_info() if hasattr(reader, 'get_info') else None
                if device_info:
                    # Puede ser dict o objeto, manejar ambos casos
                    if isinstance(device_info, dict):
                        device_type = device_info.get('type', 'Unknown')
                    else:
                        device_type = getattr(device_info, 'type', 'Unknown')
                else:
                    device_type = "Unknown"
                self.db_manager.update_battery_specs(
                    device_id=device_id,
                    device_type=device_type,
                    drain_rate=drain_rate,
                    full_charge_detected=full_charge
                )
            
            # Actualizar caché
            if hasattr(self.device_manager, 'cache'):
                self.device_manager.cache.set(device_id, 'battery', battery)
                if polling:
                    self.device_manager.cache.set(device_id, 'polling', polling)
            
            print(f"   📊 {device_id}: {battery_level}% | {polling_rate:.1f}Hz")
            
            # Callback
            if self.on_battery_update:
                await self._safe_callback(self.on_battery_update, {
                    'device_id': device_id,
                    'battery': battery_level,
                    'polling': polling_rate,
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            self.stats['failed_reads'] += 1
            print(f"   ❌ Error leyendo {device_id}: {e}")
    
    async def _handle_device_connect(self, device_id: str):
        """Manejar conexión de nuevo dispositivo"""
        print(f"   🆕 Nuevo dispositivo detectado: {device_id}")
        
        self._device_status[device_id] = DeviceStatus(
            device_id=device_id,
            is_connected=True,
            last_seen=datetime.now()
        )
    
    async def _handle_device_disconnect(self, device_id: str):
        """Manejar desconexión de dispositivo"""
        status = self._device_status.get(device_id)
        if not status:
            return
        
        # Guard: si ya está marcado como desconectado, no hacer nada
        if not status.is_connected:
            return
        
        # Evitar eventos duplicados en un periodo corto (2 segundos)
        if status.disconnect_time:
            time_since_disconnect = (datetime.now() - status.disconnect_time).total_seconds()
            if time_since_disconnect < 2.0:
                return
        
        self.stats['disconnections_detected'] += 1
        
        # Marcar como desconectado INMEDIATAMENTE para evitar múltiples llamadas
        status.is_connected = False
        status.disconnect_time = datetime.now()
        
        print(f"   ⚠️ Dispositivo desconectado: {device_id}")
        
        # NO borramos las métricas - mantenemos historial
        # Solo marcamos como desconectado en la base de datos
        if self.db_manager:
            self.db_manager.mark_device_disconnected(device_id)
        
        # Callback
        if self.on_device_disconnect:
            await self._safe_callback(self.on_device_disconnect, {
                'device_id': device_id,
                'last_battery': status.last_battery,
                'disconnect_time': status.disconnect_time.isoformat(),
                'timestamp': datetime.now().isoformat()
            })
    
    async def _handle_device_reconnect(self, device_id: str):
        """Manejar reconexión de dispositivo"""
        status = self._device_status.get(device_id)
        if not status:
            return
        
        # Guard: si ya está marcado como conectado, no hacer nada
        if status.is_connected:
            return
        
        # Marcar como conectado INMEDIATAMENTE para evitar múltiples llamadas
        status.is_connected = True
        
        self.stats['reconnections_detected'] += 1
        status.reconnect_count += 1
        
        print(f"   🔄 Dispositivo reconectado: {device_id}")
        
        # Marcar como conectado en la base de datos
        if self.db_manager:
            self.db_manager.mark_device_connected(device_id)
        
        # Callback
        if self.on_device_reconnect:
            await self._safe_callback(self.on_device_reconnect, {
                'device_id': device_id,
                'reconnect_count': status.reconnect_count,
                'disconnect_duration': (datetime.now() - status.disconnect_time).total_seconds() if status.disconnect_time else None,
                'timestamp': datetime.now().isoformat()
            })
    
    async def _safe_callback(self, callback: Callable, data: Any):
        """Ejecutar callback de forma segura"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            print(f"❌ Error en callback: {e}")
    
    def get_device_status(self, device_id: str) -> Optional[Dict]:
        """Obtener estado de un dispositivo"""
        status = self._device_status.get(device_id)
        if not status:
            return None
        
        return {
            'device_id': status.device_id,
            'is_connected': status.is_connected,
            'last_seen': status.last_seen.isoformat(),
            'last_battery': status.last_battery,
            'last_polling': status.last_polling,
            'disconnect_time': status.disconnect_time.isoformat() if status.disconnect_time else None,
            'reconnect_count': status.reconnect_count
        }
    
    def get_all_device_statuses(self) -> List[Dict]:
        """Obtener estado de todos los dispositivos"""
        return [self.get_device_status(device_id) for device_id in self._device_status.keys()]
    
    def get_stats(self) -> Dict:
        """Obtener estadísticas del scheduler"""
        return {
            **self.stats,
            'last_collection': self.stats['last_collection'].isoformat() if self.stats['last_collection'] else None,
            'started_at': self.stats['started_at'].isoformat() if self.stats['started_at'] else None,
            'is_running': self._running,
            'collection_interval_seconds': self.COLLECTION_INTERVAL,
            'tracked_devices': len(self._device_status),
            'connected_devices': sum(1 for s in self._device_status.values() if s.is_connected)
        }
    
    async def force_collection(self):
        """Forzar una recolección inmediata"""
        print("🔋 Forzando recolección de baterías...")
        await self._collect_all_batteries()
    
    def set_interval(self, seconds: int):
        """Cambiar el intervalo de recolección"""
        if seconds < 30:
            print("⚠️ Intervalo mínimo es 30 segundos")
            seconds = 30
        self.COLLECTION_INTERVAL = seconds
        print(f"🔋 Intervalo de recolección cambiado a {seconds}s")
