"""
Cache Manager - Sistema de caché para reducir lecturas HID/SPI
"""

from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Entrada de caché con timestamp"""
    data: Any
    timestamp: datetime
    
    def is_expired(self, ttl_seconds: int) -> bool:
        """Verificar si el caché ha expirado"""
        elapsed = (datetime.now() - self.timestamp).total_seconds()
        return elapsed >= ttl_seconds


class CacheManager:
    """
    Gestor de caché para datos de dispositivos
    
    Reduce lecturas costosas de HID/SPI usando diferentes TTLs:
    - Batería: 2 minutos (120s) - sincronizado con scheduler
    - Polling: 2 minutos (120s) - sincronizado con scheduler
    - Datos estáticos: Permanente hasta desconexión
    """
    
    # TTLs por tipo de dato (en segundos) - Sincronizado con BatteryScheduler
    TTL_BATTERY = 120      # 2 minutos - el scheduler actualiza cada 2 min
    TTL_POLLING = 120      # 2 minutos - el scheduler actualiza cada 2 min
    TTL_SMART_BATTERY = 300  # 5 minutos - salud no cambia frecuentemente
    TTL_STATIC = None      # Permanente (hasta que se limpie)
    
    def __init__(self):
        # Cache por dispositivo y tipo de dato
        # Estructura: {device_id: {data_type: CacheEntry}}
        self._cache: Dict[str, Dict[str, CacheEntry]] = {}
    
    def get(self, device_id: str, data_type: str, ttl_seconds: Optional[int] = None) -> Optional[Any]:
        """
        Obtener dato desde caché
        
        Args:
            device_id: ID del dispositivo
            data_type: Tipo de dato ('battery', 'polling', 'static', etc.)
            ttl_seconds: TTL personalizado, si None usa el default del tipo
        
        Returns:
            Dato cacheado o None si no existe o expiró
        """
        if device_id not in self._cache:
            return None
        
        if data_type not in self._cache[device_id]:
            return None
        
        entry = self._cache[device_id][data_type]
        
        # Determinar TTL
        if ttl_seconds is None:
            ttl_seconds = self._get_default_ttl(data_type)
        
        # Verificar expiración (si no es permanente)
        if ttl_seconds is not None and entry.is_expired(ttl_seconds):
            # Expirado, eliminar y retornar None
            del self._cache[device_id][data_type]
            return None
        
        return entry.data
    
    def set(self, device_id: str, data_type: str, data: Any):
        """
        Guardar dato en caché
        
        Args:
            device_id: ID del dispositivo
            data_type: Tipo de dato ('battery', 'polling', 'static', etc.)
            data: Dato a cachear
        """
        if device_id not in self._cache:
            self._cache[device_id] = {}
        
        self._cache[device_id][data_type] = CacheEntry(
            data=data,
            timestamp=datetime.now()
        )
    
    def clear_device(self, device_id: str):
        """
        Limpiar todo el caché de un dispositivo
        
        Args:
            device_id: ID del dispositivo
        """
        if device_id in self._cache:
            del self._cache[device_id]
    
    def clear_type(self, device_id: str, data_type: str):
        """
        Limpiar un tipo específico de dato de un dispositivo
        
        Args:
            device_id: ID del dispositivo
            data_type: Tipo de dato a limpiar
        """
        if device_id in self._cache and data_type in self._cache[device_id]:
            del self._cache[device_id][data_type]
    
    def clear_all(self):
        """Limpiar todo el caché"""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtener estadísticas del caché
        
        Returns:
            Dict con estadísticas
        """
        total_devices = len(self._cache)
        total_entries = sum(len(entries) for entries in self._cache.values())
        
        by_type = {}
        for device_cache in self._cache.values():
            for data_type in device_cache.keys():
                by_type[data_type] = by_type.get(data_type, 0) + 1
        
        return {
            "total_devices": total_devices,
            "total_entries": total_entries,
            "entries_by_type": by_type,
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_default_ttl(self, data_type: str) -> Optional[int]:
        """
        Obtener TTL por defecto para un tipo de dato
        
        Args:
            data_type: Tipo de dato
        
        Returns:
            TTL en segundos o None si es permanente
        """
        if data_type == 'battery':
            return self.TTL_BATTERY
        elif data_type == 'polling':
            return self.TTL_POLLING
        elif data_type == 'smart_battery':
            return self.TTL_SMART_BATTERY
        elif data_type == 'static':
            return self.TTL_STATIC
        else:
            # Default: 5 minutos para tipos desconocidos
            return 300
    
    def get_cache_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtener información de caché de un dispositivo específico
        
        Args:
            device_id: ID del dispositivo
        
        Returns:
            Dict con info de caché o None si no existe
        """
        if device_id not in self._cache:
            return None
        
        device_cache = self._cache[device_id]
        info = {}
        
        for data_type, entry in device_cache.items():
            ttl = self._get_default_ttl(data_type)
            elapsed = (datetime.now() - entry.timestamp).total_seconds()
            
            info[data_type] = {
                "cached_at": entry.timestamp.isoformat(),
                "age_seconds": int(elapsed),
                "ttl_seconds": ttl,
                "expires_in": int(ttl - elapsed) if ttl else None,
                "is_expired": entry.is_expired(ttl) if ttl else False
            }
        
        return info
