"""
Battery Intelligence Module - Sistema avanzado de monitoreo de batería
========================================================================

Implementa estimación de SOC, ciclos equivalentes, salud (SoH) y curvas de descarga
para tres tipos de mandos con diferentes capacidades:

- Joy-Con: Voltaje real + temperatura → métricas electroquímicas precisas
- DS4/DS5: Solo niveles discretos (0-4) → estimación basada en tiempo

Inspirado en sistemas de batería de Android/iOS.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
import math
import json


# ============================================================================
# CONSTANTES Y CONFIGURACIÓN
# ============================================================================

class DeviceType(Enum):
    """Tipos de dispositivos soportados"""
    JOYCON_L = "joycon_l"
    JOYCON_R = "joycon_r"
    DS4 = "ds4"
    DUALSENSE = "dualsense"


@dataclass
class BatterySpecs:
    """Especificaciones de batería por tipo de dispositivo"""
    nominal_capacity_mah: int       # Capacidad nominal en mAh
    nominal_voltage: float          # Voltaje nominal (V)
    min_voltage: float              # Voltaje mínimo seguro (V)
    max_voltage: float              # Voltaje máximo carga (V)
    typical_drain_per_hour: float   # Descarga típica %/hora en uso activo
    max_cycles: int                 # Ciclos estimados vida útil
    has_voltage: bool               # ¿Expone voltaje real?
    has_temperature: bool           # ¿Expone temperatura?
    discrete_levels: int            # Número de niveles discretos (0 = continuo)


# Especificaciones por dispositivo
DEVICE_SPECS: Dict[DeviceType, BatterySpecs] = {
    DeviceType.JOYCON_L: BatterySpecs(
        nominal_capacity_mah=525,
        nominal_voltage=3.7,
        min_voltage=3.0,
        max_voltage=4.2,
        typical_drain_per_hour=2.5,
        max_cycles=500,
        has_voltage=True,
        has_temperature=True,
        discrete_levels=0  # Voltaje continuo
    ),
    DeviceType.JOYCON_R: BatterySpecs(
        nominal_capacity_mah=525,
        nominal_voltage=3.7,
        min_voltage=3.0,
        max_voltage=4.2,
        typical_drain_per_hour=2.5,
        max_cycles=500,
        has_voltage=True,
        has_temperature=True,
        discrete_levels=0
    ),
    DeviceType.DS4: BatterySpecs(
        nominal_capacity_mah=1000,
        nominal_voltage=3.7,
        min_voltage=3.0,
        max_voltage=4.2,
        typical_drain_per_hour=12.5,  # ~8 horas vida
        max_cycles=500,
        has_voltage=False,
        has_temperature=False,
        discrete_levels=5  # 0-4 niveles
    ),
    DeviceType.DUALSENSE: BatterySpecs(
        nominal_capacity_mah=1560,
        nominal_voltage=3.7,
        min_voltage=3.0,
        max_voltage=4.2,
        typical_drain_per_hour=8.3,  # ~12 horas vida
        max_cycles=500,
        has_voltage=False,
        has_temperature=False,
        discrete_levels=5  # 0-4 niveles
    ),
}


# Curvas de descarga por temperatura para baterías Li-ion (Joy-Con)
# Basadas en datos típicos de baterías 18650
# Formato: {temperatura_celsius: [(voltaje, soc%), ...]}
DISCHARGE_CURVES_BY_TEMP = {
    0: [  # Frío extremo - capacidad reducida ~30%
        (4.20, 100), (4.10, 95), (4.00, 85), (3.90, 70),
        (3.80, 55), (3.70, 40), (3.60, 25), (3.50, 15),
        (3.40, 8), (3.30, 4), (3.20, 2), (3.00, 0)
    ],
    10: [  # Frío - capacidad reducida ~15%
        (4.20, 100), (4.10, 93), (4.00, 82), (3.90, 68),
        (3.80, 52), (3.70, 38), (3.60, 24), (3.50, 14),
        (3.40, 7), (3.30, 3), (3.20, 1), (3.00, 0)
    ],
    25: [  # Temperatura óptima - capacidad 100%
        (4.20, 100), (4.10, 90), (4.00, 78), (3.90, 65),
        (3.80, 50), (3.70, 36), (3.60, 22), (3.50, 12),
        (3.40, 6), (3.30, 3), (3.20, 1), (3.00, 0)
    ],
    35: [  # Cálido - ligeramente mejor rendimiento
        (4.20, 100), (4.10, 91), (4.00, 79), (3.90, 66),
        (3.80, 51), (3.70, 37), (3.60, 23), (3.50, 13),
        (3.40, 6), (3.30, 3), (3.20, 1), (3.00, 0)
    ],
    45: [  # Caliente - degradación acelerada
        (4.20, 100), (4.10, 88), (4.00, 75), (3.90, 62),
        (3.80, 48), (3.70, 34), (3.60, 21), (3.50, 11),
        (3.40, 5), (3.30, 2), (3.20, 1), (3.00, 0)
    ],
}

# Tiempos típicos por nivel para DS4/DS5 (minutos)
# Usado para estimar SOC cuando solo hay niveles discretos
LEVEL_DURATION_REFERENCE = {
    DeviceType.DS4: {
        4: 120,   # Nivel 4 (100-80%): ~2 horas
        3: 120,   # Nivel 3 (80-60%): ~2 horas
        2: 120,   # Nivel 2 (60-40%): ~2 horas
        1: 90,    # Nivel 1 (40-20%): ~1.5 horas
        0: 30,    # Nivel 0 (20-0%): ~30 min (descarga más rápida)
    },
    DeviceType.DUALSENSE: {
        4: 180,   # Nivel 4: ~3 horas
        3: 180,   # Nivel 3: ~3 horas
        2: 150,   # Nivel 2: ~2.5 horas
        1: 90,    # Nivel 1: ~1.5 horas
        0: 30,    # Nivel 0: ~30 min
    },
}


# ============================================================================
# ESTRUCTURAS DE DATOS
# ============================================================================

@dataclass
class BatteryReading:
    """Lectura individual de batería"""
    timestamp: datetime
    soc_percent: float              # State of Charge (0-100)
    voltage: Optional[float]        # Voltaje real (solo Joy-Con)
    temperature: Optional[float]    # Temperatura °C (solo Joy-Con)
    discrete_level: Optional[int]   # Nivel discreto (solo DS4/DS5)
    is_charging: bool
    is_rumble_active: bool = False  # Para medir resistencia interna


@dataclass
class CycleData:
    """Datos de un ciclo de descarga"""
    start_soc: float
    end_soc: float
    start_time: datetime
    end_time: datetime
    discharge_delta: float          # Cantidad descargada (0-1)
    avg_temperature: Optional[float]
    was_interrupted: bool           # True si fue carga parcial


@dataclass 
class BatteryHealth:
    """Estado de salud de la batería"""
    soh_percent: float              # State of Health (0-100)
    equivalent_cycles: float        # Ciclos equivalentes acumulados
    estimated_capacity_mah: int     # Capacidad actual estimada
    internal_resistance_mohm: Optional[float]  # Resistencia interna (Joy-Con)
    degradation_rate: float         # Tasa de degradación por ciclo
    last_full_charge: Optional[datetime]
    health_status: str              # "Excelente", "Buena", "Aceptable", "Degradada", "Crítica"
    confidence: float               # Confianza en la estimación (0-1)
    data_points: int                # Cantidad de datos usados para calcular


@dataclass
class BatteryState:
    """Estado completo de la batería en un momento dado"""
    device_id: str
    device_type: DeviceType
    current_reading: BatteryReading
    health: BatteryHealth
    estimated_minutes_remaining: float
    drain_rate_per_hour: float
    time_to_full_charge: Optional[float]  # Minutos (si está cargando)
    

# ============================================================================
# CLASES PRINCIPALES
# ============================================================================

class BatteryMonitorBase(ABC):
    """Clase base para monitores de batería"""
    
    def __init__(self, device_id: str, device_type: DeviceType):
        self.device_id = device_id
        self.device_type = device_type
        self.specs = DEVICE_SPECS[device_type]
        
        # Historial de lecturas
        self.readings: List[BatteryReading] = []
        self.max_readings = 1000  # Mantener últimas 1000 lecturas
        
        # Ciclos acumulados
        self.cycles: List[CycleData] = []
        self.equivalent_cycles: float = 0.0
        
        # Estado anterior para detectar cambios
        self._last_soc: Optional[float] = None
        self._last_charging: Optional[bool] = None
        self._discharge_start_soc: Optional[float] = None
        self._discharge_start_time: Optional[datetime] = None
        self._temps_in_discharge: List[float] = []
        
        # Calibración de capacidad
        self._original_capacity = self.specs.nominal_capacity_mah
        self._calibrated_capacity = self.specs.nominal_capacity_mah
        self._full_discharge_durations: List[float] = []  # Minutos de 100% a 0%
        
    @abstractmethod
    def process_reading(self, raw_data: Dict[str, Any]) -> BatteryReading:
        """Procesar datos crudos del HID en una lectura estructurada"""
        pass
    
    @abstractmethod
    def calculate_soc(self, raw_data: Dict[str, Any]) -> float:
        """Calcular State of Charge desde datos crudos"""
        pass
    
    def add_reading(self, raw_data: Dict[str, Any]) -> BatteryState:
        """
        Agregar una nueva lectura y actualizar estado
        
        Args:
            raw_data: Datos crudos del reporte HID
            
        Returns:
            Estado completo actualizado de la batería
        """
        reading = self.process_reading(raw_data)
        self.readings.append(reading)
        
        # Limitar historial
        if len(self.readings) > self.max_readings:
            self.readings = self.readings[-self.max_readings:]
        
        # Actualizar ciclos
        self._update_cycles(reading)
        
        # Calcular estado
        return self._calculate_state(reading)
    
    def _update_cycles(self, reading: BatteryReading):
        """Actualizar conteo de ciclos con nueva lectura"""
        if self._last_soc is None:
            self._last_soc = reading.soc_percent
            self._last_charging = reading.is_charging
            return
        
        # Detectar inicio de descarga
        if self._last_charging and not reading.is_charging:
            self._discharge_start_soc = reading.soc_percent
            self._discharge_start_time = reading.timestamp
            self._temps_in_discharge = []
        
        # Acumular temperaturas durante descarga
        if not reading.is_charging and reading.temperature is not None:
            self._temps_in_discharge.append(reading.temperature)
        
        # Detectar fin de descarga (inicio de carga o descarga significativa)
        if not self._last_charging and reading.is_charging and self._discharge_start_soc is not None:
            # Calcular descarga parcial
            discharge_delta = (self._discharge_start_soc - self._last_soc) / 100.0
            
            if discharge_delta > 0.01:  # Mínimo 1% para contar
                cycle = CycleData(
                    start_soc=self._discharge_start_soc,
                    end_soc=self._last_soc,
                    start_time=self._discharge_start_time,
                    end_time=reading.timestamp,
                    discharge_delta=discharge_delta,
                    avg_temperature=sum(self._temps_in_discharge) / len(self._temps_in_discharge) if self._temps_in_discharge else None,
                    was_interrupted=self._last_soc > 5  # No llegó a 0
                )
                self.cycles.append(cycle)
                
                # Acumular ciclos equivalentes (Android style)
                self.equivalent_cycles += discharge_delta
            
            self._discharge_start_soc = None
        
        self._last_soc = reading.soc_percent
        self._last_charging = reading.is_charging
    
    def _calculate_state(self, reading: BatteryReading) -> BatteryState:
        """Calcular estado completo de la batería"""
        health = self._calculate_health()
        drain_rate = self._calculate_drain_rate()
        
        # Tiempo restante
        if reading.is_charging:
            remaining = 0
            time_to_full = self._estimate_charge_time(reading.soc_percent)
        else:
            remaining = self._estimate_remaining_time(reading.soc_percent, drain_rate)
            time_to_full = None
        
        return BatteryState(
            device_id=self.device_id,
            device_type=self.device_type,
            current_reading=reading,
            health=health,
            estimated_minutes_remaining=remaining,
            drain_rate_per_hour=drain_rate,
            time_to_full_charge=time_to_full
        )
    
    def _calculate_health(self) -> BatteryHealth:
        """Calcular salud de la batería"""
        # Datos insuficientes
        if len(self.cycles) < 3:
            return BatteryHealth(
                soh_percent=100.0,
                equivalent_cycles=self.equivalent_cycles,
                estimated_capacity_mah=self._calibrated_capacity,
                internal_resistance_mohm=None,
                degradation_rate=0.0,
                last_full_charge=self._find_last_full_charge(),
                health_status="Sin datos suficientes",
                confidence=0.0,
                data_points=len(self.cycles)
            )
        
        # Estimar SoH basado en duración de descargas
        soh = self._estimate_soh_from_duration()
        
        # Degradación por ciclo
        degradation_rate = (100.0 - soh) / max(self.equivalent_cycles, 1) if self.equivalent_cycles > 0 else 0
        
        # Capacidad estimada
        estimated_capacity = int(self._original_capacity * (soh / 100.0))
        
        # Estado de salud
        if soh >= 90:
            status = "Excelente"
        elif soh >= 80:
            status = "Buena"
        elif soh >= 70:
            status = "Aceptable"
        elif soh >= 50:
            status = "Degradada"
        else:
            status = "Crítica"
        
        # Confianza basada en cantidad de datos
        confidence = min(1.0, len(self.cycles) / 20.0)
        
        return BatteryHealth(
            soh_percent=round(soh, 1),
            equivalent_cycles=round(self.equivalent_cycles, 2),
            estimated_capacity_mah=estimated_capacity,
            internal_resistance_mohm=None,  # Sobrescrito en JoyCon
            degradation_rate=round(degradation_rate, 4),
            last_full_charge=self._find_last_full_charge(),
            health_status=status,
            confidence=round(confidence, 2),
            data_points=len(self.cycles)
        )
    
    def _estimate_soh_from_duration(self) -> float:
        """Estimar SoH comparando duración actual vs referencia"""
        if not self.cycles:
            return 100.0
        
        # Usar últimos 10 ciclos significativos
        significant_cycles = [c for c in self.cycles if c.discharge_delta > 0.2][-10:]
        
        if not significant_cycles:
            return 100.0
        
        # Calcular tiempo promedio por % descargado
        total_minutes = 0
        total_discharge = 0
        
        for cycle in significant_cycles:
            duration_minutes = (cycle.end_time - cycle.start_time).total_seconds() / 60
            total_minutes += duration_minutes
            total_discharge += cycle.discharge_delta
        
        if total_discharge == 0:
            return 100.0
        
        # Minutos por 100% de descarga
        minutes_per_full = total_minutes / total_discharge
        
        # Comparar con referencia (típico del dispositivo)
        expected_minutes = 60.0 / self.specs.typical_drain_per_hour * 100
        
        # SoH = (actual / expected) * 100
        soh = (minutes_per_full / expected_minutes) * 100
        
        return max(20.0, min(100.0, soh))
    
    def _calculate_drain_rate(self) -> float:
        """Calcular tasa de descarga actual (%/hora)"""
        # Buscar lecturas recientes sin carga
        recent = [r for r in self.readings[-20:] if not r.is_charging]
        
        if len(recent) < 2:
            return self.specs.typical_drain_per_hour
        
        # Calcular delta en la última hora o menos
        first = recent[0]
        last = recent[-1]
        
        time_diff = (last.timestamp - first.timestamp).total_seconds() / 3600  # horas
        
        if time_diff < 0.01:  # Menos de 36 segundos
            return self.specs.typical_drain_per_hour
        
        soc_diff = first.soc_percent - last.soc_percent
        
        if soc_diff <= 0:
            return 0.0
        
        return soc_diff / time_diff
    
    def _estimate_remaining_time(self, current_soc: float, drain_rate: float) -> float:
        """Estimar minutos restantes"""
        if drain_rate <= 0:
            return float('inf')
        
        hours = current_soc / drain_rate
        return hours * 60
    
    def _estimate_charge_time(self, current_soc: float) -> float:
        """Estimar minutos hasta carga completa"""
        # Asumimos carga CC-CV típica
        remaining_percent = 100 - current_soc
        
        if remaining_percent <= 0:
            return 0
        
        # Tasa típica: 1C hasta 80%, luego más lento
        if current_soc < 80:
            # Fase CC: aproximadamente 1 hora para 80%
            minutes_to_80 = (80 - current_soc) * 0.75
            minutes_80_to_100 = 20 * 1.5  # CV más lento
            return minutes_to_80 + minutes_80_to_100
        else:
            # Ya en fase CV
            return remaining_percent * 1.5
    
    def _find_last_full_charge(self) -> Optional[datetime]:
        """Encontrar última carga completa"""
        for reading in reversed(self.readings):
            if reading.is_charging and reading.soc_percent >= 99:
                return reading.timestamp
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas del monitor"""
        return {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "total_readings": len(self.readings),
            "total_cycles": len(self.cycles),
            "equivalent_cycles": round(self.equivalent_cycles, 2),
            "calibrated_capacity_mah": self._calibrated_capacity,
            "has_voltage": self.specs.has_voltage,
            "has_temperature": self.specs.has_temperature
        }
    
    def export_data(self) -> Dict[str, Any]:
        """Exportar datos para persistencia"""
        return {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "equivalent_cycles": self.equivalent_cycles,
            "calibrated_capacity": self._calibrated_capacity,
            "cycles": [
                {
                    "start_soc": c.start_soc,
                    "end_soc": c.end_soc,
                    "start_time": c.start_time.isoformat(),
                    "end_time": c.end_time.isoformat(),
                    "discharge_delta": c.discharge_delta,
                    "avg_temperature": c.avg_temperature,
                    "was_interrupted": c.was_interrupted
                }
                for c in self.cycles
            ],
            "full_discharge_durations": self._full_discharge_durations
        }
    
    def import_data(self, data: Dict[str, Any]):
        """Importar datos persistidos"""
        self.equivalent_cycles = data.get("equivalent_cycles", 0.0)
        self._calibrated_capacity = data.get("calibrated_capacity", self._original_capacity)
        self._full_discharge_durations = data.get("full_discharge_durations", [])
        
        # Reconstruir ciclos
        for c in data.get("cycles", []):
            self.cycles.append(CycleData(
                start_soc=c["start_soc"],
                end_soc=c["end_soc"],
                start_time=datetime.fromisoformat(c["start_time"]),
                end_time=datetime.fromisoformat(c["end_time"]),
                discharge_delta=c["discharge_delta"],
                avg_temperature=c.get("avg_temperature"),
                was_interrupted=c.get("was_interrupted", True)
            ))


# ============================================================================
# JOY-CON BATTERY MONITOR (Voltaje + Temperatura)
# ============================================================================

class JoyConBatteryMonitor(BatteryMonitorBase):
    """
    Monitor de batería para Joy-Con con soporte de voltaje y temperatura
    
    Capacidades:
    - Lectura de voltaje real desde SPI
    - Corrección térmica del voltaje
    - Curvas de descarga por temperatura
    - Estimación de resistencia interna
    - Detección de degradación electroquímica
    """
    
    # Coeficiente de corrección térmica (mV/°C)
    THERMAL_COEFFICIENT = 0.5  # Típico para Li-ion
    
    def __init__(self, device_id: str, is_left: bool = True):
        device_type = DeviceType.JOYCON_L if is_left else DeviceType.JOYCON_R
        super().__init__(device_id, device_type)
        
        # Historial para resistencia interna
        self._voltage_under_load: List[Tuple[float, float]] = []  # (voltage, temp)
        self._voltage_no_load: List[Tuple[float, float]] = []
        self._estimated_resistance: Optional[float] = None
        
        # Calibración específica
        self._voltage_offset = 0.0  # Offset de calibración
    
    def process_reading(self, raw_data: Dict[str, Any]) -> BatteryReading:
        """Procesar datos del Joy-Con"""
        voltage = raw_data.get("voltage", 0.0)
        temperature = raw_data.get("temperature")  # Puede ser None
        is_charging = raw_data.get("charging", False)
        is_rumble = raw_data.get("rumble_active", False)
        
        # Aplicar corrección térmica si hay temperatura
        corrected_voltage = self._apply_thermal_correction(voltage, temperature)
        
        # Calcular SOC con curva de temperatura
        soc = self._voltage_to_soc(corrected_voltage, temperature)
        
        # Guardar para cálculo de resistencia
        if is_rumble:
            if temperature:
                self._voltage_under_load.append((voltage, temperature))
        else:
            if temperature:
                self._voltage_no_load.append((voltage, temperature))
        
        return BatteryReading(
            timestamp=datetime.now(),
            soc_percent=soc,
            voltage=voltage,
            temperature=temperature,
            discrete_level=None,
            is_charging=is_charging,
            is_rumble_active=is_rumble
        )
    
    def calculate_soc(self, raw_data: Dict[str, Any]) -> float:
        """Calcular SOC desde voltaje"""
        voltage = raw_data.get("voltage", 0.0)
        temperature = raw_data.get("temperature")
        corrected = self._apply_thermal_correction(voltage, temperature)
        return self._voltage_to_soc(corrected, temperature)
    
    def _apply_thermal_correction(self, voltage: float, temperature: Optional[float]) -> float:
        """
        Aplicar corrección térmica al voltaje
        
        V_corr = V - k*(T - 25°C)
        
        donde k es el coeficiente térmico (~0.5 mV/°C)
        """
        if temperature is None:
            return voltage
        
        # Corrección en mV, convertir a V
        correction = self.THERMAL_COEFFICIENT * (temperature - 25.0) / 1000.0
        return voltage - correction
    
    def _voltage_to_soc(self, voltage: float, temperature: Optional[float] = None) -> float:
        """
        Convertir voltaje a SOC usando curvas de descarga
        
        Interpola entre curvas de temperatura para mayor precisión
        """
        # Seleccionar temperatura más cercana
        temp = temperature if temperature is not None else 25.0
        
        # Encontrar curvas adyacentes
        temps = sorted(DISCHARGE_CURVES_BY_TEMP.keys())
        
        lower_temp = temps[0]
        upper_temp = temps[-1]
        
        for i, t in enumerate(temps):
            if t >= temp:
                upper_temp = t
                lower_temp = temps[max(0, i-1)]
                break
        
        # Interpolar SOC de ambas curvas
        soc_lower = self._interpolate_curve(DISCHARGE_CURVES_BY_TEMP[lower_temp], voltage)
        soc_upper = self._interpolate_curve(DISCHARGE_CURVES_BY_TEMP[upper_temp], voltage)
        
        # Interpolar entre temperaturas
        if upper_temp == lower_temp:
            return soc_lower
        
        t_ratio = (temp - lower_temp) / (upper_temp - lower_temp)
        soc = soc_lower + t_ratio * (soc_upper - soc_lower)
        
        return max(0.0, min(100.0, soc))
    
    def _interpolate_curve(self, curve: List[Tuple[float, float]], voltage: float) -> float:
        """Interpolar SOC desde una curva de descarga"""
        # Curva ordenada de mayor a menor voltaje
        for i in range(len(curve) - 1):
            v1, soc1 = curve[i]
            v2, soc2 = curve[i + 1]
            
            if v2 <= voltage <= v1:
                # Interpolación lineal
                ratio = (voltage - v2) / (v1 - v2)
                return soc2 + ratio * (soc1 - soc2)
        
        # Fuera de rango
        if voltage >= curve[0][0]:
            return 100.0
        return 0.0
    
    def estimate_internal_resistance(self) -> Optional[float]:
        """
        Estimar resistencia interna usando caída de voltaje con rumble
        
        R_int = ΔV / I_load
        
        donde I_load ≈ 0.3A para rumble típico de Joy-Con
        """
        if len(self._voltage_no_load) < 5 or len(self._voltage_under_load) < 5:
            return None
        
        # Promedios de voltaje con y sin carga a temperatura similar
        avg_no_load = sum(v for v, t in self._voltage_no_load[-10:]) / len(self._voltage_no_load[-10:])
        avg_load = sum(v for v, t in self._voltage_under_load[-10:]) / len(self._voltage_under_load[-10:])
        
        # Corriente estimada del motor de rumble (A)
        RUMBLE_CURRENT = 0.3
        
        # ΔV en voltios
        delta_v = avg_no_load - avg_load
        
        if delta_v <= 0:
            return None
        
        # Resistencia en miliohmios
        resistance = (delta_v / RUMBLE_CURRENT) * 1000
        
        self._estimated_resistance = resistance
        return resistance
    
    def _calculate_health(self) -> BatteryHealth:
        """Calcular salud con datos de resistencia interna"""
        base_health = super()._calculate_health()
        
        # Actualizar resistencia interna
        resistance = self.estimate_internal_resistance()
        
        if resistance is not None:
            base_health.internal_resistance_mohm = round(resistance, 1)
            
            # Ajustar SoH basado en resistencia
            # Resistencia nueva: ~50 mΩ, degradada: >150 mΩ
            resistance_factor = max(0.5, min(1.0, 50 / max(resistance, 50)))
            adjusted_soh = base_health.soh_percent * resistance_factor
            base_health.soh_percent = round(adjusted_soh, 1)
        
        return base_health
    
    def calibrate_voltage(self, known_soc: float, measured_voltage: float, temperature: float = 25.0):
        """
        Calibrar offset de voltaje con un SOC conocido
        
        Útil cuando se sabe que la batería está llena (100%) o vacía (0%)
        """
        # Buscar voltaje esperado para ese SOC en la curva
        curve = DISCHARGE_CURVES_BY_TEMP[25]  # Usar curva de referencia
        
        expected_voltage = None
        for v, soc in curve:
            if abs(soc - known_soc) < 1:
                expected_voltage = v
                break
        
        if expected_voltage:
            self._voltage_offset = measured_voltage - expected_voltage


# ============================================================================
# DS4/DS5 BATTERY MONITOR (Solo niveles discretos)
# ============================================================================

class DiscreteLevelBatteryMonitor(BatteryMonitorBase):
    """
    Monitor de batería para DS4/DS5 basado en niveles discretos
    
    Limitaciones:
    - NO hay voltaje real
    - NO hay temperatura
    - Solo 5 niveles (0-4)
    
    Estrategia:
    - Medir tiempo en cada nivel
    - Comparar con tiempos de referencia
    - Estimar SOC por interpolación temporal
    """
    
    def __init__(self, device_id: str, is_dualsense: bool = False):
        device_type = DeviceType.DUALSENSE if is_dualsense else DeviceType.DS4
        super().__init__(device_id, device_type)
        
        # Referencia de tiempos por nivel
        self._level_durations = LEVEL_DURATION_REFERENCE[device_type].copy()
        
        # Historial de tiempos reales por nivel
        self._actual_level_times: Dict[int, List[float]] = {i: [] for i in range(5)}
        
        # Estado del nivel actual
        self._current_level: Optional[int] = None
        self._level_start_time: Optional[datetime] = None
    
    def process_reading(self, raw_data: Dict[str, Any]) -> BatteryReading:
        """Procesar datos de DS4/DS5"""
        level = raw_data.get("level", 0)  # 0-4
        is_charging = raw_data.get("charging", False)
        percentage = raw_data.get("percentage", level * 25)  # Si viene %
        
        now = datetime.now()
        
        # Detectar cambio de nivel
        if self._current_level is not None and level != self._current_level and not is_charging:
            # Registrar tiempo en nivel anterior
            if self._level_start_time:
                duration = (now - self._level_start_time).total_seconds() / 60
                self._actual_level_times[self._current_level].append(duration)
                
                # Actualizar referencia si tenemos suficientes datos
                self._update_level_reference(self._current_level)
        
        # Actualizar nivel actual
        if level != self._current_level or (not is_charging and self._level_start_time is None):
            self._current_level = level
            self._level_start_time = now
        
        # Calcular SOC interpolado
        soc = self._calculate_interpolated_soc(level, is_charging)
        
        return BatteryReading(
            timestamp=now,
            soc_percent=soc,
            voltage=None,
            temperature=None,
            discrete_level=level,
            is_charging=is_charging
        )
    
    def calculate_soc(self, raw_data: Dict[str, Any]) -> float:
        """Calcular SOC desde nivel discreto"""
        level = raw_data.get("level", 0)
        is_charging = raw_data.get("charging", False)
        return self._calculate_interpolated_soc(level, is_charging)
    
    def _calculate_interpolated_soc(self, level: int, is_charging: bool) -> float:
        """
        Calcular SOC interpolado dentro del nivel actual
        
        SOC = nivel_base + (tiempo_transcurrido / tiempo_referencia) * 20
        """
        # SOC base del nivel (cada nivel = 20%)
        level_soc_ranges = {
            4: (80, 100),
            3: (60, 80),
            2: (40, 60),
            1: (20, 40),
            0: (0, 20)
        }
        
        min_soc, max_soc = level_soc_ranges.get(level, (0, 20))
        
        if is_charging:
            # Durante carga, interpolar hacia arriba
            if self._level_start_time:
                elapsed = (datetime.now() - self._level_start_time).total_seconds() / 60
                reference = self._level_durations.get(level, 120)
                progress = min(1.0, elapsed / reference)
                return min_soc + progress * (max_soc - min_soc)
            return min_soc
        else:
            # Durante descarga, interpolar hacia abajo
            if self._level_start_time:
                elapsed = (datetime.now() - self._level_start_time).total_seconds() / 60
                reference = self._level_durations.get(level, 120)
                progress = min(1.0, elapsed / reference)
                return max_soc - progress * (max_soc - min_soc)
            return max_soc
    
    def _update_level_reference(self, level: int):
        """Actualizar tiempo de referencia basado en datos reales"""
        times = self._actual_level_times[level]
        
        if len(times) >= 3:
            # Usar promedio de últimas mediciones
            avg_time = sum(times[-5:]) / len(times[-5:])
            
            # Actualizar solo si es razonable (±50% del original)
            original = LEVEL_DURATION_REFERENCE[self.device_type][level]
            if original * 0.5 <= avg_time <= original * 1.5:
                self._level_durations[level] = avg_time
    
    def _estimate_soh_from_duration(self) -> float:
        """Estimar SoH comparando tiempos actuales vs referencia"""
        total_actual = 0
        total_reference = 0
        levels_counted = 0
        
        for level, times in self._actual_level_times.items():
            if len(times) >= 2:
                avg_time = sum(times[-5:]) / len(times[-5:])
                ref_time = LEVEL_DURATION_REFERENCE[self.device_type][level]
                
                total_actual += avg_time
                total_reference += ref_time
                levels_counted += 1
        
        if levels_counted < 2:
            return 100.0
        
        # SoH = (tiempo actual / tiempo referencia) * 100
        soh = (total_actual / total_reference) * 100
        
        return max(20.0, min(100.0, soh))
    
    def get_level_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas por nivel"""
        stats = {}
        
        for level in range(5):
            times = self._actual_level_times[level]
            ref = LEVEL_DURATION_REFERENCE[self.device_type][level]
            current = self._level_durations[level]
            
            stats[f"level_{level}"] = {
                "reference_minutes": ref,
                "current_estimate_minutes": round(current, 1),
                "samples": len(times),
                "last_5_times": [round(t, 1) for t in times[-5:]] if times else []
            }
        
        return stats


# ============================================================================
# FACTORY Y GESTIÓN
# ============================================================================

class BatteryMonitorFactory:
    """Factory para crear monitores apropiados según tipo de dispositivo"""
    
    @staticmethod
    def create(device_id: str, device_type: str) -> BatteryMonitorBase:
        """
        Crear monitor apropiado para el tipo de dispositivo
        
        Args:
            device_id: ID único del dispositivo
            device_type: Tipo de dispositivo (string)
        
        Returns:
            Monitor de batería apropiado
        """
        device_type_lower = device_type.lower()
        
        if "joycon" in device_type_lower or "joy-con" in device_type_lower:
            is_left = "_l" in device_type_lower or "left" in device_type_lower
            return JoyConBatteryMonitor(device_id, is_left)
        
        elif "dualsense" in device_type_lower or "ds5" in device_type_lower:
            return DiscreteLevelBatteryMonitor(device_id, is_dualsense=True)
        
        elif "dualshock" in device_type_lower or "ds4" in device_type_lower:
            return DiscreteLevelBatteryMonitor(device_id, is_dualsense=False)
        
        else:
            # Default a DS4 para dispositivos desconocidos
            return DiscreteLevelBatteryMonitor(device_id, is_dualsense=False)


class BatteryIntelligenceManager:
    """
    Gestor central de monitores de batería
    
    Mantiene un monitor por dispositivo y coordina persistencia
    """
    
    def __init__(self):
        self.monitors: Dict[str, BatteryMonitorBase] = {}
    
    def get_or_create_monitor(self, device_id: str, device_type: str) -> BatteryMonitorBase:
        """Obtener o crear monitor para un dispositivo"""
        if device_id not in self.monitors:
            self.monitors[device_id] = BatteryMonitorFactory.create(device_id, device_type)
        return self.monitors[device_id]
    
    def process_reading(self, device_id: str, device_type: str, raw_data: Dict[str, Any]) -> BatteryState:
        """Procesar lectura de batería para un dispositivo"""
        monitor = self.get_or_create_monitor(device_id, device_type)
        return monitor.add_reading(raw_data)
    
    def get_health(self, device_id: str) -> Optional[BatteryHealth]:
        """Obtener salud de batería de un dispositivo"""
        if device_id in self.monitors:
            return self.monitors[device_id]._calculate_health()
        return None
    
    def get_all_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Obtener estadísticas de todos los monitores"""
        return {
            device_id: monitor.get_statistics()
            for device_id, monitor in self.monitors.items()
        }
    
    def export_all(self) -> Dict[str, Dict[str, Any]]:
        """Exportar datos de todos los monitores"""
        return {
            device_id: monitor.export_data()
            for device_id, monitor in self.monitors.items()
        }
    
    def import_data(self, data: Dict[str, Dict[str, Any]]):
        """Importar datos para todos los monitores"""
        for device_id, monitor_data in data.items():
            device_type = monitor_data.get("device_type", "ds4")
            monitor = self.get_or_create_monitor(device_id, device_type)
            monitor.import_data(monitor_data)
    
    def remove_monitor(self, device_id: str):
        """Eliminar monitor de un dispositivo"""
        if device_id in self.monitors:
            del self.monitors[device_id]


# ============================================================================
# INSTANCIA GLOBAL
# ============================================================================

# Singleton para uso global
_battery_intelligence_manager: Optional[BatteryIntelligenceManager] = None


def get_battery_intelligence_manager() -> BatteryIntelligenceManager:
    """Obtener instancia global del gestor de inteligencia de batería"""
    global _battery_intelligence_manager
    if _battery_intelligence_manager is None:
        _battery_intelligence_manager = BatteryIntelligenceManager()
    return _battery_intelligence_manager
