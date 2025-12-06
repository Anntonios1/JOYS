"""
Database Manager for Gamepad Monitor
Gestiona tablas con persistencia completa:
- devices: Datos estáticos (serial, firmware, colors, estado conexión)
- device_metrics: Datos dinámicos (batería, polling rate) - SIN purga automática
- device_sessions: Sesiones de conexión/desconexión
- battery_stats: Estadísticas inteligentes de batería
- discharge_history: Historial de descargas para análisis
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import json


# ============ Datos de batería por modelo de controlador ============
BATTERY_PROFILES = {
    'Joy-Con (L)': {'capacity_mah': 525, 'typical_hours': 20, 'min_hours': 15, 'max_hours': 25},
    'Joy-Con (R)': {'capacity_mah': 525, 'typical_hours': 20, 'min_hours': 15, 'max_hours': 25},
    'Joy-Con': {'capacity_mah': 525, 'typical_hours': 20, 'min_hours': 15, 'max_hours': 25},
    'DualShock 4': {'capacity_mah': 1000, 'typical_hours': 8, 'min_hours': 4, 'max_hours': 10},
    'DualShock 4 v1': {'capacity_mah': 1000, 'typical_hours': 8, 'min_hours': 4, 'max_hours': 10},
    'DualShock 4 v2': {'capacity_mah': 1000, 'typical_hours': 8, 'min_hours': 4, 'max_hours': 10},
    'DualSense': {'capacity_mah': 1560, 'typical_hours': 12, 'min_hours': 8, 'max_hours': 15},
    'DualSense Edge': {'capacity_mah': 1050, 'typical_hours': 6, 'min_hours': 4, 'max_hours': 8},
    'Xbox Wireless': {'capacity_mah': 0, 'typical_hours': 40, 'min_hours': 30, 'max_hours': 50},
    'Xbox Elite': {'capacity_mah': 1850, 'typical_hours': 40, 'min_hours': 30, 'max_hours': 50},
}

# Especificaciones de batería para análisis inteligente (por tipo de dispositivo)
BATTERY_SPECS = {
    'joy-con': {'typical_mah': 525, 'min_mah': 450, 'max_mah': 600, 'typical_drain_per_hour': 2.5},
    'dualshock': {'typical_mah': 1000, 'min_mah': 800, 'max_mah': 1200, 'typical_drain_per_hour': 12.5},
    'dualsense': {'typical_mah': 1560, 'min_mah': 1400, 'max_mah': 1700, 'typical_drain_per_hour': 8.3},
    'xbox': {'typical_mah': 1400, 'min_mah': 1200, 'max_mah': 1600, 'typical_drain_per_hour': 2.5},
}

# Estados de batería con umbrales y colores
BATTERY_STATES = {
    'critical': {'min': 0, 'max': 10, 'color': '#ef4444', 'icon': '🔴', 'priority': 5, 'message': 'Batería crítica'},
    'low': {'min': 10, 'max': 25, 'color': '#f97316', 'icon': '🟠', 'priority': 4, 'message': 'Batería baja'},
    'medium': {'min': 25, 'max': 50, 'color': '#eab308', 'icon': '🟡', 'priority': 3, 'message': 'Batería media'},
    'high': {'min': 50, 'max': 80, 'color': '#22c55e', 'icon': '🟢', 'priority': 2, 'message': 'Batería alta'},
    'full': {'min': 80, 'max': 101, 'color': '#10b981', 'icon': '🔋', 'priority': 1, 'message': 'Batería llena'},
}


def get_battery_state(percentage: int) -> Dict[str, Any]:
    """Obtener estado de batería basado en porcentaje"""
    if percentage is None:
        return {'state': 'unknown', 'color': '#6b7280', 'icon': '❓', 'priority': 0, 'message': 'Desconocido'}
    
    for state_name, state_info in BATTERY_STATES.items():
        if state_info['min'] <= percentage < state_info['max']:
            return {
                'state': state_name,
                'percentage': percentage,
                'color': state_info['color'],
                'icon': state_info['icon'],
                'priority': state_info['priority'],
                'message': state_info['message']
            }
    return {'state': 'unknown', 'color': '#6b7280', 'icon': '❓', 'priority': 0, 'message': 'Desconocido'}


def get_battery_profile(device_type: str) -> Dict[str, Any]:
    """Obtener perfil de batería para un tipo de dispositivo"""
    if not device_type:
        return {'capacity_mah': 1000, 'typical_hours': 10, 'min_hours': 5, 'max_hours': 15, 'model': 'Generic'}
    
    # Buscar coincidencia exacta o parcial
    device_type_lower = device_type.lower()
    for model, profile in BATTERY_PROFILES.items():
        if model.lower() in device_type_lower or device_type_lower in model.lower():
            return {**profile, 'model': model}
    
    # Perfil genérico
    return {'capacity_mah': 1000, 'typical_hours': 10, 'min_hours': 5, 'max_hours': 15, 'model': 'Generic'}


class DatabaseManager:
    def __init__(self, db_path: str = "gamepad_monitor.db"):
        """Inicializa el gestor de base de datos"""
        self.db_path = Path(db_path)
        self.init_database()
    
    def get_connection(self):
        """Crea una conexión a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Crea las tablas si no existen"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabla de dispositivos (datos estáticos + estado)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                device_type TEXT NOT NULL,
                serial_number TEXT,
                firmware_version TEXT,
                colors TEXT,
                player_number INTEGER,
                is_connected INTEGER DEFAULT 1,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_disconnect TIMESTAMP
            )
        """)
        
        # Tabla de métricas (datos dinámicos) - SIN purga automática
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                battery_level INTEGER,
                polling_rate REAL,
                session_id INTEGER,
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
        """)
        
        # Tabla de sesiones (tracking de conexiones/desconexiones)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                disconnected_at TIMESTAMP,
                initial_battery INTEGER,
                final_battery INTEGER,
                duration_seconds REAL,
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
        """)
        
        # Índices para optimizar consultas
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_device_time 
            ON device_metrics(device_id, timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_devices_last_seen 
            ON devices(last_seen DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_device 
            ON device_sessions(device_id, connected_at DESC)
        """)
        
        # Nueva tabla: Estadísticas de batería por dispositivo
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battery_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL UNIQUE,
                device_type TEXT,
                capacity_mah INTEGER,
                avg_drain_rate_per_hour REAL,
                avg_session_hours REAL,
                total_sessions INTEGER DEFAULT 0,
                total_usage_hours REAL DEFAULT 0,
                total_battery_consumed REAL DEFAULT 0,
                last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
        """)
        
        # Nueva tabla: Historial de descargas (para análisis)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discharge_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                session_id INTEGER,
                start_battery INTEGER,
                end_battery INTEGER,
                duration_hours REAL,
                drain_rate_per_hour REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
        """)
        
        # Nueva tabla: Especificaciones de batería por dispositivo (inteligencia de batería)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battery_specs (
                device_id TEXT PRIMARY KEY,
                device_type TEXT NOT NULL,
                typical_capacity_mah INTEGER,
                calibrated_capacity_mah INTEGER,
                health_percentage REAL DEFAULT 100.0,
                avg_drain_rate_per_hour REAL DEFAULT 0,
                total_discharge_cycles REAL DEFAULT 0,
                last_full_charge TIMESTAMP,
                last_calibration TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(device_id)
            )
        """)
        
        # Índices para nuevas tablas
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_battery_stats_device 
            ON battery_stats(device_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_discharge_history_device 
            ON discharge_history(device_id, timestamp DESC)
        """)
        
        # Migrar tabla devices si no tiene las nuevas columnas
        try:
            cursor.execute("SELECT is_connected FROM devices LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE devices ADD COLUMN is_connected INTEGER DEFAULT 1")
            cursor.execute("ALTER TABLE devices ADD COLUMN last_disconnect TIMESTAMP")
            print("   📊 DB migrada: añadidas columnas is_connected, last_disconnect")
        
        # Migrar player_number si no existe
        try:
            cursor.execute("SELECT player_number FROM devices LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE devices ADD COLUMN player_number INTEGER")
            print("   📊 DB migrada: añadida columna player_number")
        
        conn.commit()
        conn.close()
    
    def save_device_static_data(
        self,
        device_id: str,
        device_type: str,
        serial_number: Optional[str] = None,
        firmware_version: Optional[str] = None,
        colors: Optional[Dict[str, Any]] = None
    ):
        """
        Guarda o actualiza datos estáticos de un dispositivo
        También inicializa battery_specs si es un dispositivo nuevo
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Convertir colors a JSON si existe
        colors_json = json.dumps(colors) if colors else None
        
        # Insertar o actualizar
        cursor.execute("""
            INSERT INTO devices (device_id, device_type, serial_number, firmware_version, colors, last_seen)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(device_id) DO UPDATE SET
                serial_number = COALESCE(?, serial_number),
                firmware_version = COALESCE(?, firmware_version),
                colors = COALESCE(?, colors),
                last_seen = CURRENT_TIMESTAMP
        """, (
            device_id, device_type, serial_number, firmware_version, colors_json,
            serial_number, firmware_version, colors_json
        ))
        
        # Inicializar battery_specs para el dispositivo si no existe
        device_type_lower = device_type.lower()
        specs = BATTERY_SPECS.get('unknown', BATTERY_SPECS['joy-con'])
        
        for key in BATTERY_SPECS:
            if key in device_type_lower:
                specs = BATTERY_SPECS[key]
                break
        
        cursor.execute("""
            INSERT INTO battery_specs (device_id, device_type, typical_capacity_mah, calibrated_capacity_mah)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id) DO NOTHING
        """, (device_id, device_type, specs['typical_mah'], specs['typical_mah']))
        
        conn.commit()
        conn.close()
    
    def save_device_metrics(
        self,
        device_id: str,
        battery_level: Optional[int] = None,
        polling_rate: Optional[float] = None
    ):
        """
        Guarda métricas dinámicas de un dispositivo
        Solo guarda si al menos uno de los valores no es None
        """
        if battery_level is None and polling_rate is None:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO device_metrics (device_id, battery_level, polling_rate)
            VALUES (?, ?, ?)
        """, (device_id, battery_level, polling_rate))
        
        # Actualizar last_seen en la tabla devices
        cursor.execute("""
            UPDATE devices SET last_seen = CURRENT_TIMESTAMP
            WHERE device_id = ?
        """, (device_id,))
        
        conn.commit()
        conn.close()
    
    def get_device_static_data(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene los datos estáticos de un dispositivo"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT device_id, device_type, serial_number, firmware_version, 
                   colors, first_seen, last_seen
            FROM devices
            WHERE device_id = ?
        """, (device_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data = dict(row)
            # Parsear colors de JSON a dict
            if data['colors']:
                data['colors'] = json.loads(data['colors'])
            return data
        return None
    
    def get_device_metrics_history(
        self,
        device_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de métricas de un dispositivo
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, battery_level, polling_rate
            FROM device_metrics
            WHERE device_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (device_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Obtiene todos los dispositivos registrados"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT device_id, device_type, serial_number, firmware_version,
                   colors, first_seen, last_seen
            FROM devices
            ORDER BY last_seen DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        devices = []
        for row in rows:
            data = dict(row)
            if data['colors']:
                data['colors'] = json.loads(data['colors'])
            devices.append(data)
        
        return devices
    
    def cleanup_old_metrics(self, days: int = 7):
        """
        Limpia métricas más antiguas que X días
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM device_metrics
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted
    
    def purge_all_metrics(self):
        """
        Elimina TODAS las métricas de todos los dispositivos
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM device_metrics")
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted
    
    def cleanup_device_metrics(self, device_id: str):
        """
        Elimina todas las métricas de un dispositivo específico
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM device_metrics
            WHERE device_id = ?
        """, (device_id,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted
    
    def get_latest_metrics(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene las últimas métricas registradas de un dispositivo"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, battery_level, polling_rate
            FROM device_metrics
            WHERE device_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_usage_time(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Calcula el tiempo de uso desde el primer registro"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Obtener primer y último registro
        cursor.execute("""
            SELECT 
                MIN(timestamp) as first_seen,
                MAX(timestamp) as last_seen,
                COUNT(*) as total_records
            FROM device_metrics
            WHERE device_id = ?
        """, (device_id,))
        
        row = cursor.fetchone()
        
        if not row or not row['first_seen']:
            conn.close()
            return None
        
        # Calcular diferencia de tiempo
        from datetime import datetime
        first = datetime.fromisoformat(row['first_seen'])
        last = datetime.fromisoformat(row['last_seen'])
        duration = last - first
        
        # Obtener niveles de batería inicial y actual
        cursor.execute("""
            SELECT battery_level FROM device_metrics
            WHERE device_id = ?
            ORDER BY timestamp ASC
            LIMIT 1
        """, (device_id,))
        first_battery_row = cursor.fetchone()
        first_battery = first_battery_row['battery_level'] if first_battery_row else None
        
        cursor.execute("""
            SELECT battery_level FROM device_metrics
            WHERE device_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        last_battery_row = cursor.fetchone()
        last_battery = last_battery_row['battery_level'] if last_battery_row else None
        
        conn.close()
        
        # Calcular consumo
        battery_consumed = None
        estimated_autonomy_hours = None
        if first_battery and last_battery and duration.total_seconds() > 0:
            battery_consumed = first_battery - last_battery
            hours = duration.total_seconds() / 3600
            if hours > 0 and battery_consumed > 0:
                consumption_rate = battery_consumed / hours  # % por hora
                if consumption_rate > 0:
                    estimated_autonomy_hours = last_battery / consumption_rate
        
        return {
            'first_seen': row['first_seen'],
            'last_seen': row['last_seen'],
            'duration_seconds': duration.total_seconds(),
            'duration_hours': duration.total_seconds() / 3600,
            'duration_minutes': duration.total_seconds() / 60,
            'total_records': row['total_records'],
            'first_battery': first_battery,
            'last_battery': last_battery,
            'battery_consumed': battery_consumed,
            'estimated_autonomy_hours': estimated_autonomy_hours
        }

    def mark_device_connected(self, device_id: str):
        """Marca un dispositivo como conectado y crea una nueva sesión"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Actualizar estado en devices
        cursor.execute("""
            UPDATE devices 
            SET is_connected = 1, last_seen = CURRENT_TIMESTAMP
            WHERE device_id = ?
        """, (device_id,))
        
        # Crear nueva sesión
        cursor.execute("""
            INSERT INTO device_sessions (device_id, connected_at)
            VALUES (?, CURRENT_TIMESTAMP)
        """, (device_id,))
        
        session_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return session_id
    
    def set_player_number(self, device_id: str, player_number: int):
        """Asigna un número de jugador (1-8) a un dispositivo"""
        if player_number < 1 or player_number > 8:
            return False
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE devices 
            SET player_number = ?
            WHERE device_id = ?
        """, (player_number, device_id))
        
        conn.commit()
        conn.close()
        return True
    
    def get_player_number(self, device_id: str) -> Optional[int]:
        """Obtiene el número de jugador asignado a un dispositivo"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT player_number 
            FROM devices 
            WHERE device_id = ?
        """, (device_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row['player_number'] is not None:
            return row['player_number']
        return None
    
    def mark_device_disconnected(self, device_id: str):
        """Marca un dispositivo como desconectado y cierra la sesión activa"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Obtener última batería registrada
        cursor.execute("""
            SELECT battery_level FROM device_metrics
            WHERE device_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (device_id,))
        last_battery_row = cursor.fetchone()
        final_battery = last_battery_row['battery_level'] if last_battery_row else None
        
        # Actualizar estado en devices
        cursor.execute("""
            UPDATE devices 
            SET is_connected = 0, 
                last_disconnect = CURRENT_TIMESTAMP,
                last_seen = CURRENT_TIMESTAMP
            WHERE device_id = ?
        """, (device_id,))
        
        # Cerrar sesión activa (la más reciente sin disconnected_at)
        cursor.execute("""
            UPDATE device_sessions 
            SET disconnected_at = CURRENT_TIMESTAMP,
                final_battery = ?,
                duration_seconds = (julianday(CURRENT_TIMESTAMP) - julianday(connected_at)) * 86400
            WHERE device_id = ? AND disconnected_at IS NULL
        """, (final_battery, device_id))
        
        conn.commit()
        conn.close()
    
    def get_device_sessions(self, device_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtiene el historial de sesiones de un dispositivo"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, connected_at, disconnected_at, 
                   initial_battery, final_battery, duration_seconds
            FROM device_sessions
            WHERE device_id = ?
            ORDER BY connected_at DESC
            LIMIT ?
        """, (device_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_active_session(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene la sesión activa de un dispositivo"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, connected_at, initial_battery
            FROM device_sessions
            WHERE device_id = ? AND disconnected_at IS NULL
            ORDER BY connected_at DESC
            LIMIT 1
        """, (device_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            data = dict(row)
            # Calcular duración actual
            connected_at = datetime.fromisoformat(data['connected_at'])
            data['current_duration_seconds'] = (datetime.now() - connected_at).total_seconds()
            data['current_duration_minutes'] = data['current_duration_seconds'] / 60
            return data
        return None
    
    def update_session_initial_battery(self, device_id: str, battery_level: int):
        """Actualiza la batería inicial de la sesión activa"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE device_sessions 
            SET initial_battery = ?
            WHERE device_id = ? 
              AND disconnected_at IS NULL 
              AND initial_battery IS NULL
        """, (battery_level, device_id))
        
        conn.commit()
        conn.close()
    
    def get_metrics_for_graph(self, device_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Obtiene métricas optimizadas para gráficas
        Agrupa por intervalos de 2 minutos para reducir puntos
        Devuelve timestamp y battery_level para compatibilidad con overlay
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                strftime('%Y-%m-%dT%H:%M:00', timestamp, 'localtime') as timestamp,
                ROUND(AVG(battery_level)) as battery_level,
                AVG(polling_rate) as polling_rate,
                MIN(battery_level) as min_battery,
                MAX(battery_level) as max_battery,
                COUNT(*) as sample_count
            FROM device_metrics
            WHERE device_id = ?
              AND timestamp >= datetime('now', '-' || ? || ' hours')
            GROUP BY strftime('%Y-%m-%d %H:%M', timestamp, 'localtime')
            ORDER BY timestamp ASC
        """, (device_id, hours))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_battery_drain_rate(self, device_id: str, hours: int = 1) -> Optional[float]:
        """
        Calcula la tasa de descarga de batería en % por hora
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT battery_level, timestamp
            FROM device_metrics
            WHERE device_id = ?
              AND timestamp >= datetime('now', '-' || ? || ' hours')
              AND battery_level IS NOT NULL
            ORDER BY timestamp ASC
        """, (device_id, hours))
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 2:
            return None
        
        first = rows[0]
        last = rows[-1]
        
        first_time = datetime.fromisoformat(first['timestamp'])
        last_time = datetime.fromisoformat(last['timestamp'])
        
        time_diff_hours = (last_time - first_time).total_seconds() / 3600
        battery_diff = first['battery_level'] - last['battery_level']
        
        if time_diff_hours > 0:
            return battery_diff / time_diff_hours  # % por hora
        return None
    
    def purge_metrics_by_user_request(self, device_id: Optional[str] = None) -> Dict[str, int]:
        """
        Purga métricas SOLO cuando el usuario lo solicita explícitamente
        
        Args:
            device_id: Si se especifica, purga solo ese dispositivo
        
        Returns:
            Dict con conteo de registros eliminados
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        result = {'metrics_deleted': 0, 'sessions_deleted': 0}
        
        if device_id:
            # Purgar solo un dispositivo
            cursor.execute("DELETE FROM device_metrics WHERE device_id = ?", (device_id,))
            result['metrics_deleted'] = cursor.rowcount
            
            cursor.execute("DELETE FROM device_sessions WHERE device_id = ?", (device_id,))
            result['sessions_deleted'] = cursor.rowcount
        else:
            # Purgar todo
            cursor.execute("DELETE FROM device_metrics")
            result['metrics_deleted'] = cursor.rowcount
            
            cursor.execute("DELETE FROM device_sessions")
            result['sessions_deleted'] = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return result
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la base de datos"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Contar métricas
        cursor.execute("SELECT COUNT(*) as count FROM device_metrics")
        metrics_count = cursor.fetchone()['count']
        
        # Contar sesiones
        cursor.execute("SELECT COUNT(*) as count FROM device_sessions")
        sessions_count = cursor.fetchone()['count']
        
        # Contar dispositivos
        cursor.execute("SELECT COUNT(*) as count FROM devices")
        devices_count = cursor.fetchone()['count']
        
        # Dispositivos conectados
        cursor.execute("SELECT COUNT(*) as count FROM devices WHERE is_connected = 1")
        connected_count = cursor.fetchone()['count']
        
        # Rango de fechas de métricas
        cursor.execute("""
            SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest
            FROM device_metrics
        """)
        date_range = cursor.fetchone()
        
        # Tamaño aproximado
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        db_size = cursor.fetchone()['size']
        
        conn.close()
        
        return {
            'total_metrics': metrics_count,
            'total_sessions': sessions_count,
            'total_devices': devices_count,
            'connected_devices': connected_count,
            'oldest_metric': date_range['oldest'],
            'newest_metric': date_range['newest'],
            'database_size_bytes': db_size,
            'database_size_mb': round(db_size / (1024 * 1024), 2)
        }

    # ============ Métodos de Batería Inteligente ============
    
    def get_battery_info(self, device_id: str, device_type: str = None) -> Dict[str, Any]:
        """
        Obtiene información completa de batería con cálculos inteligentes
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Obtener tipo de dispositivo si no se proporciona
        if not device_type:
            cursor.execute("SELECT device_type FROM devices WHERE device_id = ?", (device_id,))
            row = cursor.fetchone()
            device_type = row['device_type'] if row else 'Generic'
        
        # Obtener perfil de batería del modelo
        profile = get_battery_profile(device_type)
        
        # Obtener estadísticas actuales del dispositivo
        cursor.execute("""
            SELECT * FROM battery_stats WHERE device_id = ?
        """, (device_id,))
        stats_row = cursor.fetchone()
        
        # Obtener último nivel de batería
        cursor.execute("""
            SELECT battery_level, timestamp FROM device_metrics 
            WHERE device_id = ? AND battery_level IS NOT NULL
            ORDER BY timestamp DESC LIMIT 1
        """, (device_id,))
        last_battery_row = cursor.fetchone()
        
        current_battery = last_battery_row['battery_level'] if last_battery_row else None
        battery_state = get_battery_state(current_battery)
        
        # Calcular autonomía estimada
        estimated_hours = None
        if current_battery is not None:
            if stats_row and stats_row['avg_drain_rate_per_hour'] and stats_row['avg_drain_rate_per_hour'] > 0:
                # Usar tasa de descarga real del dispositivo
                estimated_hours = current_battery / stats_row['avg_drain_rate_per_hour']
            else:
                # Usar perfil del modelo
                estimated_hours = (current_battery / 100) * profile['typical_hours']
        
        conn.close()
        
        return {
            'device_id': device_id,
            'device_type': device_type,
            'current_percentage': current_battery,
            'state': battery_state,
            'profile': profile,
            'estimated_hours_remaining': round(estimated_hours, 1) if estimated_hours else None,
            'stats': {
                'avg_drain_rate_per_hour': stats_row['avg_drain_rate_per_hour'] if stats_row else None,
                'avg_session_hours': stats_row['avg_session_hours'] if stats_row else None,
                'total_sessions': stats_row['total_sessions'] if stats_row else 0,
                'total_usage_hours': stats_row['total_usage_hours'] if stats_row else 0,
            } if stats_row else None
        }
    
    def record_discharge(self, device_id: str, session_id: int, start_battery: int, 
                         end_battery: int, duration_hours: float):
        """
        Registra una descarga y actualiza estadísticas
        """
        if duration_hours <= 0 or start_battery <= end_battery:
            return  # No hay descarga válida
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        battery_consumed = start_battery - end_battery
        drain_rate = battery_consumed / duration_hours
        
        # Registrar en historial de descargas
        cursor.execute("""
            INSERT INTO discharge_history 
            (device_id, session_id, start_battery, end_battery, duration_hours, drain_rate_per_hour)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (device_id, session_id, start_battery, end_battery, duration_hours, drain_rate))
        
        # Actualizar estadísticas agregadas
        self._update_battery_stats(cursor, device_id)
        
        conn.commit()
        conn.close()
    
    def _update_battery_stats(self, cursor, device_id: str):
        """
        Actualiza las estadísticas de batería para un dispositivo
        """
        # Obtener tipo de dispositivo
        cursor.execute("SELECT device_type FROM devices WHERE device_id = ?", (device_id,))
        row = cursor.fetchone()
        device_type = row['device_type'] if row else 'Generic'
        profile = get_battery_profile(device_type)
        
        # Calcular promedios desde el historial de descargas
        cursor.execute("""
            SELECT 
                AVG(drain_rate_per_hour) as avg_drain,
                AVG(duration_hours) as avg_duration,
                COUNT(*) as total_sessions,
                SUM(duration_hours) as total_hours,
                SUM(start_battery - end_battery) as total_consumed
            FROM discharge_history
            WHERE device_id = ?
        """, (device_id,))
        
        stats = cursor.fetchone()
        
        # Insertar o actualizar estadísticas
        cursor.execute("""
            INSERT INTO battery_stats 
            (device_id, device_type, capacity_mah, avg_drain_rate_per_hour, avg_session_hours, 
             total_sessions, total_usage_hours, total_battery_consumed, last_calculated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(device_id) DO UPDATE SET
                avg_drain_rate_per_hour = excluded.avg_drain_rate_per_hour,
                avg_session_hours = excluded.avg_session_hours,
                total_sessions = excluded.total_sessions,
                total_usage_hours = excluded.total_usage_hours,
                total_battery_consumed = excluded.total_battery_consumed,
                last_calculated = CURRENT_TIMESTAMP
        """, (
            device_id, 
            device_type, 
            profile['capacity_mah'],
            stats['avg_drain'] if stats else None,
            stats['avg_duration'] if stats else None,
            stats['total_sessions'] if stats else 0,
            stats['total_hours'] if stats else 0,
            stats['total_consumed'] if stats else 0
        ))
    
    def get_smart_autonomy(self, device_id: str, current_battery: int, device_type: str = None) -> Dict[str, Any]:
        """
        Calcula autonomía inteligente basada en historial real
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if not device_type:
            cursor.execute("SELECT device_type FROM devices WHERE device_id = ?", (device_id,))
            row = cursor.fetchone()
            device_type = row['device_type'] if row else 'Generic'
        
        profile = get_battery_profile(device_type)
        
        # Obtener estadísticas del dispositivo
        cursor.execute("""
            SELECT avg_drain_rate_per_hour, total_sessions FROM battery_stats 
            WHERE device_id = ?
        """, (device_id,))
        stats = cursor.fetchone()
        
        # Obtener tasa de descarga reciente (última hora)
        cursor.execute("""
            SELECT drain_rate_per_hour FROM discharge_history
            WHERE device_id = ? 
            ORDER BY timestamp DESC LIMIT 5
        """, (device_id,))
        recent_rates = cursor.fetchall()
        
        conn.close()
        
        # Calcular autonomía
        result = {
            'current_battery': current_battery,
            'device_type': device_type,
            'profile': profile,
            'estimation_method': 'profile',  # default
            'confidence': 'low'
        }
        
        if stats and stats['avg_drain_rate_per_hour'] and stats['total_sessions'] >= 3:
            # Usar promedio histórico (buena confianza)
            drain_rate = stats['avg_drain_rate_per_hour']
            result['estimation_method'] = 'historical_average'
            result['confidence'] = 'high' if stats['total_sessions'] >= 10 else 'medium'
            result['drain_rate_per_hour'] = round(drain_rate, 2)
            
            if drain_rate > 0:
                result['estimated_hours'] = round(current_battery / drain_rate, 1)
                result['estimated_minutes'] = round((current_battery / drain_rate) * 60)
        
        elif recent_rates and len(recent_rates) >= 2:
            # Usar tasa reciente
            avg_recent = sum(r['drain_rate_per_hour'] for r in recent_rates) / len(recent_rates)
            result['estimation_method'] = 'recent'
            result['confidence'] = 'medium'
            result['drain_rate_per_hour'] = round(avg_recent, 2)
            
            if avg_recent > 0:
                result['estimated_hours'] = round(current_battery / avg_recent, 1)
                result['estimated_minutes'] = round((current_battery / avg_recent) * 60)
        
        else:
            # Usar perfil del modelo
            result['drain_rate_per_hour'] = round(100 / profile['typical_hours'], 2)
            result['estimated_hours'] = round((current_battery / 100) * profile['typical_hours'], 1)
            result['estimated_minutes'] = round(result['estimated_hours'] * 60)
        
        # Añadir rango estimado
        if 'estimated_hours' in result:
            variance = 0.2 if result['confidence'] == 'high' else 0.4
            result['min_hours'] = round(result['estimated_hours'] * (1 - variance), 1)
            result['max_hours'] = round(result['estimated_hours'] * (1 + variance), 1)
        
        return result
    
    def get_battery_health_report(self, device_id: str) -> Dict[str, Any]:
        """
        Genera un reporte de salud de batería
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Obtener datos del dispositivo
        cursor.execute("SELECT device_type FROM devices WHERE device_id = ?", (device_id,))
        device_row = cursor.fetchone()
        device_type = device_row['device_type'] if device_row else 'Generic'
        profile = get_battery_profile(device_type)
        
        # Estadísticas
        cursor.execute("SELECT * FROM battery_stats WHERE device_id = ?", (device_id,))
        stats = cursor.fetchone()
        
        # Historial de descargas recientes
        cursor.execute("""
            SELECT * FROM discharge_history 
            WHERE device_id = ? 
            ORDER BY timestamp DESC LIMIT 20
        """, (device_id,))
        history = [dict(row) for row in cursor.fetchall()]
        
        # Último nivel de batería
        cursor.execute("""
            SELECT battery_level FROM device_metrics 
            WHERE device_id = ? AND battery_level IS NOT NULL
            ORDER BY timestamp DESC LIMIT 1
        """, (device_id,))
        last_battery = cursor.fetchone()
        current = last_battery['battery_level'] if last_battery else None
        
        conn.close()
        
        # Análisis de salud
        health_score = 100
        health_issues = []
        
        if stats and stats['avg_drain_rate_per_hour']:
            expected_rate = 100 / profile['typical_hours']
            actual_rate = stats['avg_drain_rate_per_hour']
            
            if actual_rate > expected_rate * 1.5:
                health_score -= 30
                health_issues.append("Descarga más rápida de lo esperado")
            elif actual_rate > expected_rate * 1.2:
                health_score -= 15
                health_issues.append("Descarga ligeramente elevada")
        
        return {
            'device_id': device_id,
            'device_type': device_type,
            'profile': profile,
            'current_battery': current,
            'current_state': get_battery_state(current),
            'health_score': max(0, health_score),
            'health_issues': health_issues,
            'stats': dict(stats) if stats else None,
            'recent_discharges': history[:5]
        }
    
    # ============ SMART BATTERY INTELLIGENCE METHODS ============
    
    def _calculate_real_battery_health(
        self, 
        device_id: str, 
        device_specs: Dict, 
        type_specs: Dict
    ) -> tuple:
        """
        Calcula la salud real de la batería basándose en:
        1. Comparación de tasa de descarga real vs esperada
        2. Historial de descargas completas
        3. Variabilidad en el comportamiento de la batería
        
        Returns:
            Tuple: (porcentaje de salud 0-100, cantidad de muestras usadas)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Obtener historial de descargas recientes
        cursor.execute("""
            SELECT drain_rate_per_hour, duration_hours, start_battery, end_battery
            FROM discharge_history
            WHERE device_id = ? AND drain_rate_per_hour > 0
            ORDER BY timestamp DESC
            LIMIT 20
        """, (device_id,))
        
        discharges = cursor.fetchall()
        conn.close()
        
        if not discharges or len(discharges) < 3:
            # No hay suficientes datos, devolver salud almacenada o 100%
            return (device_specs.get('health_percentage') or 100.0, len(discharges) if discharges else 0)
        
        # 1. Calcular tasa de descarga promedio real
        drain_rates = [d['drain_rate_per_hour'] for d in discharges if d['drain_rate_per_hour'] > 0]
        if not drain_rates:
            return (device_specs.get('health_percentage') or 100.0, 0)
            
        avg_real_drain = sum(drain_rates) / len(drain_rates)
        expected_drain = type_specs.get('typical_drain_per_hour', 5.0)
        
        # 2. Comparar tasa real vs esperada
        # Si descarga más rápido de lo esperado, la salud es menor
        if expected_drain > 0:
            efficiency_ratio = expected_drain / max(avg_real_drain, 0.1)
            # Limitar entre 0.5 y 1.2 (no puede ser >100% pero permite pequeño margen)
            efficiency_ratio = max(0.5, min(1.2, efficiency_ratio))
        else:
            efficiency_ratio = 1.0
        
        # 3. Analizar variabilidad (baterías degradadas tienen comportamiento errático)
        if len(drain_rates) >= 3:
            avg_drain = sum(drain_rates) / len(drain_rates)
            variance = sum((d - avg_drain) ** 2 for d in drain_rates) / len(drain_rates)
            std_dev = variance ** 0.5
            # Coeficiente de variación (normalizado)
            cv = std_dev / avg_drain if avg_drain > 0 else 0
            # Alta variabilidad (cv > 0.3) indica degradación
            stability_factor = max(0.7, 1.0 - (cv * 0.5))
        else:
            stability_factor = 1.0
        
        # 4. Factor de ciclos de carga (cada ciclo completo degrada ~0.04%)
        total_cycles = device_specs.get('total_discharge_cycles') or 0
        cycle_degradation = 1.0 - (total_cycles * 0.0004)  # 500 ciclos = 80% salud
        cycle_degradation = max(0.5, cycle_degradation)
        
        # 5. Calcular salud final
        health = 100.0 * efficiency_ratio * stability_factor * cycle_degradation
        health = max(20.0, min(100.0, health))  # Limitar entre 20% y 100%
        
        return (round(health, 1), len(drain_rates))
    
    def get_smart_battery_status(
        self, 
        device_id: str, 
        current_battery: int, 
        device_type: str
    ) -> Dict[str, Any]:
        """
        Obtiene un estado inteligente de la batería con predicciones
        
        Returns:
            Dict con:
            - status: 'Critical' | 'Low' | 'Normal' | 'High' | 'Full'
            - battery_health: porcentaje de salud (0-100)
            - drain_rate_per_hour: tasa de descarga actual
            - estimated_minutes_remaining: minutos estimados restantes
            - capacity_mah: capacidad estimada del dispositivo
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Determinar specs del tipo de dispositivo
        device_type_lower = device_type.lower()
        specs = BATTERY_SPECS.get('joy-con')  # Default
        
        for key in BATTERY_SPECS:
            if key in device_type_lower:
                specs = BATTERY_SPECS[key]
                break
        
        # Obtener specs guardadas para este dispositivo específico
        cursor.execute("""
            SELECT calibrated_capacity_mah, health_percentage, avg_drain_rate_per_hour
            FROM battery_specs WHERE device_id = ?
        """, (device_id,))
        device_specs = cursor.fetchone()
        
        # Obtener tasa de descarga real del historial reciente
        cursor.execute("""
            SELECT drain_rate_per_hour FROM discharge_history
            WHERE device_id = ? AND drain_rate_per_hour > 0
            ORDER BY timestamp DESC LIMIT 5
        """, (device_id,))
        recent_drains = cursor.fetchall()
        
        conn.close()
        
        # Calcular tasa de descarga promedio
        if recent_drains:
            drain_rate = sum(row['drain_rate_per_hour'] for row in recent_drains) / len(recent_drains)
        else:
            drain_rate = specs.get('typical_drain_per_hour', 5.0)
        
        # Usar valores del dispositivo si existen
        health_samples = 0
        if device_specs:
            # Convertir sqlite3.Row a dict para poder usar .get()
            device_specs_dict = dict(device_specs)
            capacity = device_specs_dict.get('calibrated_capacity_mah') or specs['typical_mah']
            # Calcular salud basada en datos reales de descarga
            health, health_samples = self._calculate_real_battery_health(device_id, device_specs_dict, specs)
            if device_specs_dict.get('avg_drain_rate_per_hour') and device_specs_dict['avg_drain_rate_per_hour'] > 0:
                drain_rate = device_specs_dict['avg_drain_rate_per_hour']
        else:
            capacity = specs['typical_mah']
            health = 100.0
        
        # Calcular tiempo restante
        if drain_rate > 0:
            estimated_minutes = (current_battery / drain_rate) * 60
        else:
            # Fallback: usar típico del perfil
            profile = BATTERY_PROFILES.get(device_type, BATTERY_PROFILES.get('Joy-Con', {}))
            typical_hours = profile.get('typical_hours', 8)
            estimated_minutes = (current_battery / 100) * typical_hours * 60
        
        # Determinar estado
        if current_battery <= 10:
            status = 'Critical'
        elif current_battery <= 20:
            status = 'Low'
        elif current_battery <= 50:
            status = 'Normal'
        elif current_battery <= 80:
            status = 'High'
        else:
            status = 'Full'
        
        # Determinar si hay datos suficientes para la salud
        # Necesita al menos 3 muestras para ser confiable
        health_reliable = health_samples >= 3
        
        return {
            'status': status,
            'battery_health': round(health, 1),
            'health_reliable': health_reliable,
            'health_samples': health_samples,
            'drain_rate_per_hour': round(drain_rate, 2),
            'estimated_minutes_remaining': round(estimated_minutes, 0),
            'capacity_mah': capacity
        }
    
    def get_battery_drain_analysis(self, device_id: str) -> Dict[str, Any]:
        """
        Analiza el patrón de descarga de batería
        
        Returns:
            Dict con estadísticas de descarga por hora, sesión, etc.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Obtener historial de descargas
        cursor.execute("""
            SELECT drain_rate_per_hour, duration_hours, start_battery, end_battery, timestamp
            FROM discharge_history
            WHERE device_id = ?
            ORDER BY timestamp DESC
            LIMIT 50
        """, (device_id,))
        
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not history:
            return {
                'has_data': False,
                'message': 'No hay suficientes datos de descarga'
            }
        
        # Calcular estadísticas
        drain_rates = [h['drain_rate_per_hour'] for h in history if h['drain_rate_per_hour'] and h['drain_rate_per_hour'] > 0]
        
        if not drain_rates:
            return {
                'has_data': False,
                'message': 'No hay tasas de descarga válidas'
            }
        
        avg_drain = sum(drain_rates) / len(drain_rates)
        min_drain = min(drain_rates)
        max_drain = max(drain_rates)
        
        # Calcular descarga por hora del día (si hay timestamps)
        hourly_drains = {}
        for h in history:
            if h['timestamp'] and h['drain_rate_per_hour'] and h['drain_rate_per_hour'] > 0:
                try:
                    dt = datetime.fromisoformat(h['timestamp'])
                    hour = dt.hour
                    if hour not in hourly_drains:
                        hourly_drains[hour] = []
                    hourly_drains[hour].append(h['drain_rate_per_hour'])
                except:
                    pass
        
        hourly_avg = {hour: sum(rates)/len(rates) for hour, rates in hourly_drains.items()}
        
        return {
            'has_data': True,
            'total_sessions': len(history),
            'avg_drain_rate': round(avg_drain, 2),
            'min_drain_rate': round(min_drain, 2),
            'max_drain_rate': round(max_drain, 2),
            'hourly_average': hourly_avg,
            'estimated_full_to_empty_hours': round(100 / avg_drain, 1) if avg_drain > 0 else None
        }
    
    def update_battery_specs(
        self, 
        device_id: str, 
        device_type: str, 
        drain_rate: Optional[float] = None,
        full_charge_detected: bool = False
    ):
        """
        Actualiza las especificaciones de batería basándose en el uso real
        
        Args:
            device_id: ID del dispositivo
            device_type: Tipo de dispositivo
            drain_rate: Tasa de descarga observada (si hay)
            full_charge_detected: Si se detectó carga completa (100%)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Obtener specs actuales
        cursor.execute("SELECT * FROM battery_specs WHERE device_id = ?", (device_id,))
        current = cursor.fetchone()
        
        device_type_lower = device_type.lower()
        specs = BATTERY_SPECS.get('joy-con')
        for key in BATTERY_SPECS:
            if key in device_type_lower:
                specs = BATTERY_SPECS[key]
                break
        
        if current:
            # Actualizar existente
            updates = ["updated_at = CURRENT_TIMESTAMP"]
            params = []
            
            if drain_rate is not None and drain_rate > 0:
                # Promedio móvil de drain rate
                old_rate = current['avg_drain_rate_per_hour'] or drain_rate
                new_rate = (old_rate * 0.8) + (drain_rate * 0.2)  # 80% antiguo, 20% nuevo
                updates.append("avg_drain_rate_per_hour = ?")
                params.append(new_rate)
            
            if full_charge_detected:
                updates.append("last_full_charge = CURRENT_TIMESTAMP")
                # Incrementar ciclos de descarga
                cycles = (current['total_discharge_cycles'] or 0) + 0.1  # Cada carga completa = 0.1 ciclo aprox
                updates.append("total_discharge_cycles = ?")
                params.append(cycles)
                
                # Recalcular salud basada en ciclos
                # Típicamente las baterías pierden ~20% después de 500 ciclos
                health = max(50, 100 - (cycles / 500 * 20))
                updates.append("health_percentage = ?")
                params.append(health)
            
            params.append(device_id)
            cursor.execute(f"""
                UPDATE battery_specs SET {', '.join(updates)} WHERE device_id = ?
            """, params)
        else:
            # Insertar nuevo
            cursor.execute("""
                INSERT INTO battery_specs 
                (device_id, device_type, typical_capacity_mah, calibrated_capacity_mah, avg_drain_rate_per_hour)
                VALUES (?, ?, ?, ?, ?)
            """, (device_id, device_type, specs['typical_mah'], specs['typical_mah'], drain_rate or 0))
        
        conn.commit()
        conn.close()
