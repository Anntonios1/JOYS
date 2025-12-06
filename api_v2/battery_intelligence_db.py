"""
Battery Intelligence Database Integration
==========================================

Integra el sistema de inteligencia de batería con la base de datos SQLite.
Maneja persistencia de:
- Ciclos de carga/descarga
- Calibración de capacidad
- Historial de resistencia interna
- Estadísticas por nivel (DS4/DS5)
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

from battery_intelligence import (
    BatteryIntelligenceManager,
    BatteryMonitorBase,
    JoyConBatteryMonitor,
    DiscreteLevelBatteryMonitor,
    BatteryHealth,
    BatteryState,
    CycleData,
    DeviceType,
    get_battery_intelligence_manager
)


class BatteryIntelligenceDB:
    """
    Capa de persistencia para el sistema de inteligencia de batería
    """
    
    def __init__(self, db_path: str = "gamepad_monitor.db"):
        self.db_path = db_path
        self._ensure_tables()
    
    def get_connection(self) -> sqlite3.Connection:
        """Obtener conexión a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_tables(self):
        """Crear tablas necesarias si no existen"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabla para ciclos de carga/descarga
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battery_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                start_soc REAL NOT NULL,
                end_soc REAL NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                discharge_delta REAL NOT NULL,
                avg_temperature REAL,
                was_interrupted INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(device_id, start_time)
            )
        """)
        
        # Tabla para estado de inteligencia de batería
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battery_intelligence_state (
                device_id TEXT PRIMARY KEY,
                device_type TEXT NOT NULL,
                equivalent_cycles REAL DEFAULT 0,
                calibrated_capacity INTEGER,
                internal_resistance_mohm REAL,
                voltage_offset REAL DEFAULT 0,
                level_durations_json TEXT,
                level_times_json TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla para historial de resistencia interna (Joy-Con)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS internal_resistance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                resistance_mohm REAL NOT NULL,
                voltage_no_load REAL,
                voltage_under_load REAL,
                temperature REAL,
                measured_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla para historial de salud
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battery_health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                soh_percent REAL NOT NULL,
                equivalent_cycles REAL NOT NULL,
                estimated_capacity_mah INTEGER,
                confidence REAL,
                recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices para consultas rápidas
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cycles_device ON battery_cycles(device_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cycles_time ON battery_cycles(start_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_resistance_device ON internal_resistance_history(device_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_health_device ON battery_health_history(device_id)")
        
        conn.commit()
        conn.close()
    
    def save_monitor_state(self, monitor: BatteryMonitorBase):
        """
        Guardar estado completo de un monitor
        
        Args:
            monitor: Monitor de batería a persistir
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Datos base
            data = {
                "device_id": monitor.device_id,
                "device_type": monitor.device_type.value,
                "equivalent_cycles": monitor.equivalent_cycles,
                "calibrated_capacity": monitor._calibrated_capacity,
                "last_updated": datetime.now().isoformat()
            }
            
            # Datos específicos de Joy-Con
            if isinstance(monitor, JoyConBatteryMonitor):
                data["internal_resistance_mohm"] = monitor._estimated_resistance
                data["voltage_offset"] = monitor._voltage_offset
            
            # Datos específicos de DS4/DS5
            if isinstance(monitor, DiscreteLevelBatteryMonitor):
                data["level_durations_json"] = json.dumps(monitor._level_durations)
                data["level_times_json"] = json.dumps({
                    str(k): v for k, v in monitor._actual_level_times.items()
                })
            
            # Insertar o actualizar
            cursor.execute("""
                INSERT OR REPLACE INTO battery_intelligence_state (
                    device_id, device_type, equivalent_cycles, calibrated_capacity,
                    internal_resistance_mohm, voltage_offset, level_durations_json,
                    level_times_json, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["device_id"],
                data["device_type"],
                data["equivalent_cycles"],
                data["calibrated_capacity"],
                data.get("internal_resistance_mohm"),
                data.get("voltage_offset", 0),
                data.get("level_durations_json"),
                data.get("level_times_json"),
                data["last_updated"]
            ))
            
            # Guardar ciclos nuevos
            for cycle in monitor.cycles:
                self._save_cycle(cursor, monitor.device_id, cycle)
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"Error guardando estado de monitor: {e}")
        finally:
            conn.close()
    
    def _save_cycle(self, cursor: sqlite3.Cursor, device_id: str, cycle: CycleData):
        """Guardar un ciclo de descarga"""
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO battery_cycles (
                    device_id, start_soc, end_soc, start_time, end_time,
                    discharge_delta, avg_temperature, was_interrupted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                device_id,
                cycle.start_soc,
                cycle.end_soc,
                cycle.start_time.isoformat(),
                cycle.end_time.isoformat(),
                cycle.discharge_delta,
                cycle.avg_temperature,
                1 if cycle.was_interrupted else 0
            ))
        except sqlite3.IntegrityError:
            pass  # Ciclo ya existe
    
    def load_monitor_state(self, monitor: BatteryMonitorBase) -> bool:
        """
        Cargar estado persistido en un monitor
        
        Args:
            monitor: Monitor donde cargar los datos
            
        Returns:
            True si se encontraron datos, False si es nuevo
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Cargar estado base
            cursor.execute("""
                SELECT * FROM battery_intelligence_state WHERE device_id = ?
            """, (monitor.device_id,))
            
            row = cursor.fetchone()
            
            if not row:
                return False
            
            # Restaurar datos base
            monitor.equivalent_cycles = row["equivalent_cycles"] or 0
            monitor._calibrated_capacity = row["calibrated_capacity"] or monitor._original_capacity
            
            # Restaurar datos específicos de Joy-Con
            if isinstance(monitor, JoyConBatteryMonitor):
                if row["internal_resistance_mohm"]:
                    monitor._estimated_resistance = row["internal_resistance_mohm"]
                if row["voltage_offset"]:
                    monitor._voltage_offset = row["voltage_offset"]
            
            # Restaurar datos específicos de DS4/DS5
            if isinstance(monitor, DiscreteLevelBatteryMonitor):
                if row["level_durations_json"]:
                    monitor._level_durations = json.loads(row["level_durations_json"])
                    # Convertir keys a int
                    monitor._level_durations = {int(k): v for k, v in monitor._level_durations.items()}
                
                if row["level_times_json"]:
                    level_times = json.loads(row["level_times_json"])
                    monitor._actual_level_times = {int(k): v for k, v in level_times.items()}
            
            # Cargar ciclos históricos
            cursor.execute("""
                SELECT * FROM battery_cycles 
                WHERE device_id = ? 
                ORDER BY start_time DESC
                LIMIT 100
            """, (monitor.device_id,))
            
            for cycle_row in cursor.fetchall():
                cycle = CycleData(
                    start_soc=cycle_row["start_soc"],
                    end_soc=cycle_row["end_soc"],
                    start_time=datetime.fromisoformat(cycle_row["start_time"]),
                    end_time=datetime.fromisoformat(cycle_row["end_time"]),
                    discharge_delta=cycle_row["discharge_delta"],
                    avg_temperature=cycle_row["avg_temperature"],
                    was_interrupted=bool(cycle_row["was_interrupted"])
                )
                monitor.cycles.append(cycle)
            
            return True
            
        except Exception as e:
            print(f"Error cargando estado de monitor: {e}")
            return False
        finally:
            conn.close()
    
    def save_health_snapshot(self, device_id: str, health: BatteryHealth):
        """
        Guardar snapshot de salud para historial
        
        Args:
            device_id: ID del dispositivo
            health: Estado de salud actual
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO battery_health_history (
                    device_id, soh_percent, equivalent_cycles,
                    estimated_capacity_mah, confidence
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                device_id,
                health.soh_percent,
                health.equivalent_cycles,
                health.estimated_capacity_mah,
                health.confidence
            ))
            conn.commit()
        except Exception as e:
            print(f"Error guardando snapshot de salud: {e}")
        finally:
            conn.close()
    
    def save_resistance_reading(self, device_id: str, resistance: float,
                                 v_no_load: float = None, v_load: float = None,
                                 temperature: float = None):
        """
        Guardar lectura de resistencia interna (Joy-Con)
        
        Args:
            device_id: ID del dispositivo
            resistance: Resistencia en mΩ
            v_no_load: Voltaje sin carga
            v_load: Voltaje bajo carga
            temperature: Temperatura en °C
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO internal_resistance_history (
                    device_id, resistance_mohm, voltage_no_load,
                    voltage_under_load, temperature
                ) VALUES (?, ?, ?, ?, ?)
            """, (device_id, resistance, v_no_load, v_load, temperature))
            conn.commit()
        except Exception as e:
            print(f"Error guardando resistencia: {e}")
        finally:
            conn.close()
    
    def get_health_history(self, device_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        Obtener historial de salud
        
        Args:
            device_id: ID del dispositivo
            days: Días hacia atrás
            
        Returns:
            Lista de snapshots de salud
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM battery_health_history
                WHERE device_id = ?
                AND recorded_at >= datetime('now', ?)
                ORDER BY recorded_at DESC
            """, (device_id, f'-{days} days'))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_resistance_history(self, device_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Obtener historial de resistencia interna
        
        Args:
            device_id: ID del dispositivo
            limit: Máximo de registros
            
        Returns:
            Lista de mediciones de resistencia
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM internal_resistance_history
                WHERE device_id = ?
                ORDER BY measured_at DESC
                LIMIT ?
            """, (device_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_cycle_statistics(self, device_id: str) -> Dict[str, Any]:
        """
        Obtener estadísticas de ciclos
        
        Args:
            device_id: ID del dispositivo
            
        Returns:
            Estadísticas agregadas
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_cycles,
                    SUM(discharge_delta) as total_discharge,
                    AVG(discharge_delta) as avg_discharge_per_cycle,
                    AVG(avg_temperature) as avg_temperature,
                    MIN(start_time) as first_cycle,
                    MAX(end_time) as last_cycle,
                    SUM(CASE WHEN was_interrupted = 0 THEN 1 ELSE 0 END) as full_cycles,
                    SUM(CASE WHEN was_interrupted = 1 THEN 1 ELSE 0 END) as partial_cycles
                FROM battery_cycles
                WHERE device_id = ?
            """, (device_id,))
            
            row = cursor.fetchone()
            
            if not row or row["total_cycles"] == 0:
                return {
                    "total_cycles": 0,
                    "equivalent_cycles": 0,
                    "full_cycles": 0,
                    "partial_cycles": 0,
                    "avg_temperature": None,
                    "first_cycle": None,
                    "last_cycle": None
                }
            
            return {
                "total_cycles": row["total_cycles"],
                "equivalent_cycles": round(row["total_discharge"], 2),
                "full_cycles": row["full_cycles"],
                "partial_cycles": row["partial_cycles"],
                "avg_discharge_per_cycle": round(row["avg_discharge_per_cycle"] * 100, 1),
                "avg_temperature": round(row["avg_temperature"], 1) if row["avg_temperature"] else None,
                "first_cycle": row["first_cycle"],
                "last_cycle": row["last_cycle"]
            }
        finally:
            conn.close()
    
    def get_degradation_trend(self, device_id: str) -> Dict[str, Any]:
        """
        Analizar tendencia de degradación
        
        Args:
            device_id: ID del dispositivo
            
        Returns:
            Análisis de tendencia
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Obtener historial de salud ordenado
            cursor.execute("""
                SELECT soh_percent, equivalent_cycles, recorded_at
                FROM battery_health_history
                WHERE device_id = ?
                ORDER BY recorded_at ASC
            """, (device_id,))
            
            rows = cursor.fetchall()
            
            if len(rows) < 2:
                return {
                    "has_trend": False,
                    "message": "Datos insuficientes para análisis"
                }
            
            # Calcular pendiente de degradación
            first = rows[0]
            last = rows[-1]
            
            soh_change = last["soh_percent"] - first["soh_percent"]
            cycle_change = last["equivalent_cycles"] - first["equivalent_cycles"]
            
            if cycle_change > 0:
                degradation_per_cycle = soh_change / cycle_change
            else:
                degradation_per_cycle = 0
            
            # Estimar vida restante
            current_soh = last["soh_percent"]
            if degradation_per_cycle < 0:
                cycles_to_80 = (current_soh - 80) / abs(degradation_per_cycle)
                cycles_to_50 = (current_soh - 50) / abs(degradation_per_cycle)
            else:
                cycles_to_80 = float('inf')
                cycles_to_50 = float('inf')
            
            return {
                "has_trend": True,
                "current_soh": current_soh,
                "soh_change": round(soh_change, 1),
                "cycles_analyzed": round(cycle_change, 2),
                "degradation_per_cycle": round(degradation_per_cycle, 4),
                "estimated_cycles_to_80_percent": round(cycles_to_80, 0) if cycles_to_80 != float('inf') else None,
                "estimated_cycles_to_50_percent": round(cycles_to_50, 0) if cycles_to_50 != float('inf') else None,
                "trend": "estable" if abs(degradation_per_cycle) < 0.05 else ("degradando" if degradation_per_cycle < 0 else "mejorando")
            }
        finally:
            conn.close()
    
    def load_historical_data(self, device_id: str, monitor: BatteryMonitorBase) -> Dict[str, Any]:
        """
        Cargar datos históricos de device_metrics para inicializar el monitor
        
        Args:
            device_id: ID del dispositivo
            monitor: Monitor a inicializar
            
        Returns:
            Estadísticas de datos cargados
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Obtener métricas históricas ordenadas por tiempo
            cursor.execute("""
                SELECT battery_level, timestamp 
                FROM device_metrics 
                WHERE device_id = ? 
                ORDER BY timestamp
            """, (device_id,))
            
            metrics = cursor.fetchall()
            
            if not metrics:
                return {"loaded": False, "metrics": 0, "charges": 0, "discharges": 0}
            
            charge_events = []
            discharge_events = []
            prev_level = None
            prev_ts = None
            
            # Detectar eventos de carga y descarga
            for m in metrics:
                level = m["battery_level"]
                ts = m["timestamp"]
                
                if prev_level is not None:
                    diff = level - prev_level
                    
                    if diff > 5:  # Subida > 5% = carga
                        charge_events.append({
                            'from': prev_level,
                            'to': level,
                            'timestamp': ts
                        })
                    elif diff < -3:  # Bajada > 3% = descarga
                        discharge_events.append({
                            'from': prev_level,
                            'to': level,
                            'diff': abs(diff),
                            'timestamp': ts,
                            'prev_ts': prev_ts
                        })
                
                prev_level = level
                prev_ts = ts
            
            # Calcular ciclos equivalentes desde descargas
            total_discharge = sum(d['diff'] for d in discharge_events)
            equivalent_cycles = total_discharge / 100.0
            
            # Actualizar monitor
            if equivalent_cycles > monitor.equivalent_cycles:
                monitor.equivalent_cycles = equivalent_cycles
            
            # Guardar última carga conocida
            if charge_events:
                last_charge = charge_events[-1]
                # Actualizar battery_specs con última carga
                cursor.execute("""
                    UPDATE battery_specs 
                    SET last_full_charge = ?, total_discharge_cycles = ?
                    WHERE device_id = ?
                """, (last_charge['timestamp'], equivalent_cycles, device_id))
                conn.commit()
            
            return {
                "loaded": True,
                "metrics": len(metrics),
                "charges": len(charge_events),
                "discharges": len(discharge_events),
                "equivalent_cycles": round(equivalent_cycles, 2),
                "charge_events": charge_events[-5:],  # Últimas 5 cargas
                "discharge_events": discharge_events[-5:]  # Últimas 5 descargas
            }
            
        except Exception as e:
            print(f"Error cargando datos históricos: {e}")
            return {"loaded": False, "error": str(e)}
        finally:
            conn.close()
    
    def get_charge_count(self, device_id: str) -> Dict[str, Any]:
        """
        Obtener conteo de cargas detectadas para un dispositivo
        
        Args:
            device_id: ID del dispositivo
            
        Returns:
            Estadísticas de carga
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Obtener métricas históricas
            cursor.execute("""
                SELECT battery_level, timestamp 
                FROM device_metrics 
                WHERE device_id = ? 
                ORDER BY timestamp
            """, (device_id,))
            
            metrics = cursor.fetchall()
            
            if not metrics:
                return {"count": 0, "events": []}
            
            charges = []
            prev_level = None
            prev_ts = None
            
            for m in metrics:
                level = m["battery_level"]
                ts = m["timestamp"]
                
                if prev_level is not None and level > prev_level + 5:
                    charges.append({
                        'from_level': prev_level,
                        'to_level': level,
                        'charged': level - prev_level,
                        'timestamp': ts
                    })
                
                prev_level = level
                prev_ts = ts
            
            # Identificar cargas completas (llegaron a 100%)
            full_charges = [c for c in charges if c['to_level'] >= 95]
            
            return {
                "total_charges": len(charges),
                "full_charges": len(full_charges),
                "partial_charges": len(charges) - len(full_charges),
                "last_charge": charges[-1] if charges else None,
                "recent_charges": charges[-5:]  # Últimas 5
            }
            
        except Exception as e:
            print(f"Error obteniendo conteo de cargas: {e}")
            return {"count": 0, "error": str(e)}
        finally:
            conn.close()


# ============================================================================
# INTEGRACIÓN CON BATTERY INTELLIGENCE MANAGER
# ============================================================================

class PersistentBatteryIntelligenceManager(BatteryIntelligenceManager):
    """
    Extensión del manager con persistencia automática
    """
    
    def __init__(self, db_path: str = "gamepad_monitor.db"):
        super().__init__()
        self.db = BatteryIntelligenceDB(db_path)
        self._auto_save_interval = 60  # segundos
        self._last_save: Dict[str, datetime] = {}
    
    def get_or_create_monitor(self, device_id: str, device_type: str) -> BatteryMonitorBase:
        """Obtener o crear monitor con carga desde DB"""
        if device_id not in self.monitors:
            monitor = super().get_or_create_monitor(device_id, device_type)
            # Intentar cargar estado persistido
            loaded = self.db.load_monitor_state(monitor)
            
            # Si no hay estado guardado, cargar datos históricos de device_metrics
            if not loaded or monitor.equivalent_cycles == 0:
                historical = self.db.load_historical_data(device_id, monitor)
                if historical.get("loaded"):
                    print(f"📊 {device_id}: Cargados {historical['metrics']} métricas, "
                          f"{historical['charges']} cargas, {historical['equivalent_cycles']} ciclos")
        return self.monitors[device_id]
    
    def process_reading(self, device_id: str, device_type: str, raw_data: Dict[str, Any]) -> BatteryState:
        """Procesar lectura con auto-guardado"""
        state = super().process_reading(device_id, device_type, raw_data)
        
        # Auto-guardar cada intervalo
        now = datetime.now()
        last = self._last_save.get(device_id)
        
        if last is None or (now - last).total_seconds() >= self._auto_save_interval:
            self.save_monitor(device_id)
            self._last_save[device_id] = now
        
        return state
    
    def save_monitor(self, device_id: str):
        """Guardar estado de un monitor específico"""
        if device_id in self.monitors:
            self.db.save_monitor_state(self.monitors[device_id])
    
    def save_all(self):
        """Guardar todos los monitores"""
        for device_id, monitor in self.monitors.items():
            self.db.save_monitor_state(monitor)
    
    def get_health_with_history(self, device_id: str) -> Dict[str, Any]:
        """Obtener salud con historial y tendencias"""
        health = self.get_health(device_id)
        
        if health is None:
            return None
        
        # Obtener conteo de cargas
        charge_stats = self.db.get_charge_count(device_id)
        
        return {
            "current": {
                "soh_percent": health.soh_percent,
                "equivalent_cycles": health.equivalent_cycles,
                "estimated_capacity_mah": health.estimated_capacity_mah,
                "internal_resistance_mohm": health.internal_resistance_mohm,
                "health_status": health.health_status,
                "confidence": health.confidence,
                "data_points": health.data_points
            },
            "charge_stats": charge_stats,
            "cycle_stats": self.db.get_cycle_statistics(device_id),
            "degradation_trend": self.db.get_degradation_trend(device_id),
            "health_history": self.db.get_health_history(device_id, days=30)
        }
    
    def get_charge_count(self, device_id: str) -> Dict[str, Any]:
        """Obtener conteo de cargas para un dispositivo"""
        return self.db.get_charge_count(device_id)
    
    def record_health_snapshot(self, device_id: str):
        """Registrar snapshot de salud actual"""
        health = self.get_health(device_id)
        if health:
            self.db.save_health_snapshot(device_id, health)


# ============================================================================
# INSTANCIA GLOBAL CON PERSISTENCIA
# ============================================================================

_persistent_manager: Optional[PersistentBatteryIntelligenceManager] = None


def get_persistent_battery_manager(db_path: str = None) -> PersistentBatteryIntelligenceManager:
    """Obtener instancia global del manager con persistencia"""
    global _persistent_manager
    
    if _persistent_manager is None:
        if db_path is None:
            # Buscar path de DB existente
            db_path = Path(__file__).parent / "gamepad_monitor.db"
        _persistent_manager = PersistentBatteryIntelligenceManager(str(db_path))
    
    return _persistent_manager
