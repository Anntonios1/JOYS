"""
Database manager para guardar historial de dispositivos
SQLite con historial de batería, polling rate, y sesiones
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class DatabaseManager:
    """Gestor de base de datos SQLite para historial de dispositivos"""
    
    def __init__(self, db_path: str = "gamepad_monitor.db"):
        """
        Inicializar conexión a la base de datos
        
        Args:
            db_path: Ruta al archivo de base de datos
        """
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """Crear tablas si no existen"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # Tabla de dispositivos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                serial_number TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # Tabla de historial de batería
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS battery_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                percentage INTEGER NOT NULL,
                voltage REAL,
                charging INTEGER NOT NULL,
                level_name TEXT,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        """)
        
        # Índice para búsquedas rápidas por dispositivo y fecha
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_battery_device_timestamp 
            ON battery_history(device_id, timestamp)
        """)
        
        # Tabla de historial de polling rate
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS polling_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rate_hz REAL NOT NULL,
                interval_ms REAL NOT NULL,
                packet_count INTEGER,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        """)
        
        # Tabla de sesiones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                initial_battery INTEGER,
                final_battery INTEGER,
                duration_minutes REAL,
                avg_polling_hz REAL,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        """)
        
        self.conn.commit()
        print(f"✓ Base de datos inicializada: {self.db_path}")
    
    def register_device(self, device_id: str, device_type: str, name: str, 
                       serial_number: Optional[str] = None, metadata: Optional[Dict] = None):
        """Registrar o actualizar un dispositivo"""
        cursor = self.conn.cursor()
        
        metadata_json = json.dumps(metadata) if metadata else None
        
        cursor.execute("""
            INSERT INTO devices (id, type, name, serial_number, metadata, last_seen)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                last_seen = CURRENT_TIMESTAMP,
                name = excluded.name,
                serial_number = excluded.serial_number,
                metadata = excluded.metadata
        """, (device_id, device_type, name, serial_number, metadata_json))
        
        self.conn.commit()
    
    def save_battery_data(self, device_id: str, percentage: int, voltage: Optional[float],
                         charging: bool, level_name: Optional[str] = None):
        """Guardar lectura de batería"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO battery_history (device_id, percentage, voltage, charging, level_name)
            VALUES (?, ?, ?, ?, ?)
        """, (device_id, percentage, voltage, 1 if charging else 0, level_name))
        
        self.conn.commit()
    
    def save_polling_data(self, device_id: str, rate_hz: float, interval_ms: float, 
                         packet_count: Optional[int] = None):
        """Guardar lectura de polling rate"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO polling_history (device_id, rate_hz, interval_ms, packet_count)
            VALUES (?, ?, ?, ?)
        """, (device_id, rate_hz, interval_ms, packet_count))
        
        self.conn.commit()
    
    def get_battery_history(self, device_id: str, hours: int = 24) -> List[Dict]:
        """
        Obtener historial de batería de un dispositivo
        
        Args:
            device_id: ID del dispositivo
            hours: Horas hacia atrás (default 24h)
        
        Returns:
            Lista de registros de batería
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, percentage, voltage, charging, level_name
            FROM battery_history
            WHERE device_id = ?
            AND timestamp >= datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp ASC
        """, (device_id, hours))
        
        rows = cursor.fetchall()
        
        return [
            {
                'timestamp': row['timestamp'],
                'percentage': row['percentage'],
                'voltage': row['voltage'],
                'charging': bool(row['charging']),
                'level_name': row['level_name']
            }
            for row in rows
        ]
    
    def get_polling_history(self, device_id: str, hours: int = 24) -> List[Dict]:
        """Obtener historial de polling rate"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, rate_hz, interval_ms, packet_count
            FROM polling_history
            WHERE device_id = ?
            AND timestamp >= datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp ASC
        """, (device_id, hours))
        
        rows = cursor.fetchall()
        
        return [
            {
                'timestamp': row['timestamp'],
                'rate_hz': row['rate_hz'],
                'interval_ms': row['interval_ms'],
                'packet_count': row['packet_count']
            }
            for row in rows
        ]
    
    def get_battery_stats(self, device_id: str, hours: int = 24) -> Optional[Dict]:
        """Calcular estadísticas de batería"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as readings,
                AVG(percentage) as avg_battery,
                MIN(percentage) as min_battery,
                MAX(percentage) as max_battery,
                MIN(timestamp) as first_reading,
                MAX(timestamp) as last_reading
            FROM battery_history
            WHERE device_id = ?
            AND timestamp >= datetime('now', '-' || ? || ' hours')
        """, (device_id, hours))
        
        row = cursor.fetchone()
        
        if row and row['readings'] > 0:
            # Calcular drain rate
            if row['readings'] > 1:
                cursor.execute("""
                    SELECT 
                        (first.percentage - last.percentage) as battery_drop,
                        (julianday(last.timestamp) - julianday(first.timestamp)) * 24 as hours_elapsed
                    FROM 
                        (SELECT percentage, timestamp FROM battery_history 
                         WHERE device_id = ? AND timestamp >= datetime('now', '-' || ? || ' hours')
                         ORDER BY timestamp ASC LIMIT 1) as first,
                        (SELECT percentage, timestamp FROM battery_history 
                         WHERE device_id = ? AND timestamp >= datetime('now', '-' || ? || ' hours')
                         ORDER BY timestamp DESC LIMIT 1) as last
                """, (device_id, hours, device_id, hours))
                
                drain_row = cursor.fetchone()
                drain_rate = drain_row['battery_drop'] / drain_row['hours_elapsed'] if drain_row['hours_elapsed'] > 0 else 0
            else:
                drain_rate = 0
            
            return {
                'readings': row['readings'],
                'avg_battery': round(row['avg_battery'], 1),
                'min_battery': row['min_battery'],
                'max_battery': row['max_battery'],
                'drain_rate': round(drain_rate, 2),
                'first_reading': row['first_reading'],
                'last_reading': row['last_reading']
            }
        
        return None
    
    def start_session(self, device_id: str, initial_battery: int) -> int:
        """Iniciar una nueva sesión"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO sessions (device_id, initial_battery)
            VALUES (?, ?)
        """, (device_id, initial_battery))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def end_session(self, session_id: int, final_battery: int):
        """Finalizar una sesión"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE sessions
            SET end_time = CURRENT_TIMESTAMP,
                final_battery = ?,
                duration_minutes = (julianday(CURRENT_TIMESTAMP) - julianday(start_time)) * 1440
            WHERE id = ?
        """, (final_battery, session_id))
        
        self.conn.commit()
    
    def cleanup_old_data(self, days: int = 30):
        """Limpiar datos antiguos para mantener la DB pequeña"""
        cursor = self.conn.cursor()
        
        # Eliminar historial de batería antiguo
        cursor.execute("""
            DELETE FROM battery_history
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days,))
        
        # Eliminar historial de polling antiguo
        cursor.execute("""
            DELETE FROM polling_history
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days,))
        
        # Eliminar sesiones antiguas
        cursor.execute("""
            DELETE FROM sessions
            WHERE start_time < datetime('now', '-' || ? || ' days')
        """, (days,))
        
        deleted = cursor.rowcount
        self.conn.commit()
        
        # Vacuum para reducir tamaño del archivo
        cursor.execute("VACUUM")
        
        return deleted
    
    def close(self):
        """Cerrar conexión a la base de datos"""
        if self.conn:
            self.conn.close()
            print("✓ Base de datos cerrada")
