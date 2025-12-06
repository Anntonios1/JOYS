"""
Funciones avanzadas para Joy-Con basadas en documentación oficial de Nintendo Switch Reverse Engineering
Fuente: https://github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering
"""

import math
from typing import Dict, Optional


def encode_rumble(frequency: float = 160.0, amplitude: float = 0.5) -> bytearray:
    """
    Codificar datos de rumble con frecuencia y amplitud precisas
    Basado en algoritmo oficial del reverse engineering
    
    Args:
        frequency: Frecuencia en Hz (40-1252)
        amplitude: Amplitud 0.0-1.0
    
    Returns:
        bytearray de 8 bytes con datos de rumble
    """
    rumble_data = bytearray(8)
    
    if amplitude <= 0:
        # Neutral position (sin vibración)
        rumble_data[0] = 0x00
        rumble_data[1] = 0x01
        rumble_data[2] = 0x40
        rumble_data[3] = 0x40
        # Duplicar para actuador derecho
        rumble_data[4:8] = rumble_data[0:4]
        return rumble_data
    
    # Clamp values
    freq = max(40.0, min(1252.0, frequency))
    amp = max(0.0, min(1.0, amplitude))
    
    # Frequency encoding: log2(freq/10.0)*32.0
    encoded_hex_freq = int(round(math.log2(freq / 10.0) * 32.0))
    
    # HF range: 0x0004-0x01FC with +0x0004 steps
    hf = (encoded_hex_freq - 0x60) * 4
    # LF range: 0x01-0x7F
    lf = encoded_hex_freq - 0x40
    
    # Amplitude encoding (ranges from official docs)
    if amp > 0.23:
        encoded_hex_amp = int(round(math.log2(amp * 8.7) * 32.0))
    elif amp > 0.12:
        encoded_hex_amp = int(round(math.log2(amp * 17.0) * 16.0))
    else:
        # Linear for low amplitudes
        encoded_hex_amp = int(round(amp * 64))
    
    # Clamp amplitude
    encoded_hex_amp = max(0, min(255, encoded_hex_amp))
    
    hf_amp = (encoded_hex_amp * 2) & 0xFF
    lf_amp = ((encoded_hex_amp // 2) + 0x40) & 0xFF
    
    # Build rumble packet (left actuator)
    rumble_data[0] = hf & 0xFF
    rumble_data[1] = hf_amp + ((hf >> 8) & 0xFF)
    rumble_data[2] = lf + ((lf_amp >> 8) & 0xFF)
    rumble_data[3] = lf_amp & 0xFF
    
    # Duplicar para actuador derecho (ambos actuadores iguales)
    rumble_data[4:8] = rumble_data[0:4]
    
    return rumble_data


# Tabla de frecuencias predefinidas del documento oficial
RUMBLE_FREQUENCIES = {
    'ultra_low': 41.0,    # Vibración profunda
    'low': 80.0,          # Grave
    'medium_low': 120.0,  # Medio-grave
    'medium': 160.0,      # Medio (default)
    'medium_high': 240.0, # Medio-agudo
    'high': 320.0,        # Agudo
    'ultra_high': 640.0,  # Muy agudo
}


def get_frequency_preset(preset: str) -> float:
    """Obtener frecuencia predefinida por nombre"""
    return RUMBLE_FREQUENCIES.get(preset, 160.0)


# Subcomandos documentados oficialmente
SUBCOMMANDS = {
    'GET_CONTROLLER_STATE': 0x00,
    'BLUETOOTH_MANUAL_PAIRING': 0x01,
    'REQUEST_DEVICE_INFO': 0x02,
    'SET_INPUT_REPORT_MODE': 0x03,
    'TRIGGER_BUTTONS_ELAPSED_TIME': 0x04,
    'GET_PAGE_LIST_STATE': 0x05,
    'SET_HCI_STATE': 0x06,
    'RESET_PAIRING_INFO': 0x07,
    'SET_SHIPMENT_LOW_POWER': 0x08,
    'SPI_FLASH_READ': 0x10,
    'SPI_FLASH_WRITE': 0x11,
    'SPI_SECTOR_ERASE': 0x12,
    'RESET_NFC_IR_MCU': 0x20,
    'SET_NFC_IR_MCU_CONFIG': 0x21,
    'SET_NFC_IR_MCU_STATE': 0x22,
    'SET_PLAYER_LIGHTS': 0x30,
    'GET_PLAYER_LIGHTS': 0x31,
    'SET_HOME_LIGHT': 0x38,
    'ENABLE_IMU': 0x40,
    'SET_IMU_SENSITIVITY': 0x41,
    'WRITE_IMU_REGISTERS': 0x42,
    'READ_IMU_REGISTERS': 0x43,
    'ENABLE_VIBRATION': 0x48,
    'GET_REGULATED_VOLTAGE': 0x50,
}


# Input report modes (subcomando 0x03)
INPUT_REPORT_MODES = {
    'NFC_IR_POLLING': 0x00,
    'NFC_IR_CONFIG_POLLING': 0x01,
    'NFC_IR_DATA_POLLING': 0x02,
    'IR_CAMERA_POLLING': 0x03,
    'MCU_UPDATE': 0x23,
    'STANDARD_FULL': 0x30,      # 60Hz full state
    'NFC_IR_MODE': 0x31,         # 60Hz with NFC/IR data
    'SIMPLE_HID': 0x3F,          # Button press only
}


# SPI Memory Map (direcciones oficiales)
SPI_ADDRESSES = {
    'INITIAL_PATCHRAM': 0x0000,
    'FAILSAFE': 0x1000,
    'PAIRING_INFO': 0x2000,
    'PAIRING_FACTORY': 0x3000,
    'PAIRING_FACTORY2': 0x4000,
    'SHIPMENT': 0x5000,
    'CONFIG_CALIBRATION': 0x6000,
    'SERIAL_NUMBER': 0x6000,      # 16 bytes
    'DEVICE_TYPE': 0x6012,        # 1 byte: 1=JC(L), 2=JC(R), 3=Pro
    'COLOR_INFO_EXISTS': 0x601B,  # 1 byte: 1=has colors
    'BODY_COLOR': 0x6050,         # 3 bytes RGB
    'BUTTON_COLOR': 0x6053,       # 3 bytes RGB
    'LEFT_GRIP_COLOR': 0x6056,    # 3 bytes RGB (Solo Joy-Con L)
    'RIGHT_GRIP_COLOR': 0x6059,   # 3 bytes RGB (Solo Joy-Con R)
    'STICK_CALIBRATION': 0x603D,  # Left stick factory calibration
    'IMU_CALIBRATION': 0x6020,    # 6-Axis sensor calibration
    'USER_STICK_CALIBRATION': 0x8010,  # User stick calibration
    'USER_IMU_CALIBRATION': 0x8026,    # User IMU calibration
    'PATCHRAM_SECTION': 0x10000,
}


# HCI States (subcomando 0x06)
HCI_STATES = {
    'DISCONNECT': 0x00,        # Sleep mode / page scan
    'REBOOT_RECONNECT': 0x01,  # Page mode
    'REBOOT_PAIR': 0x02,       # Discoverable
    'HOME_MODE': 0x04,         # HOME reconnect mode
}


def decode_stick_calibration(data: bytes) -> Dict[str, Dict[str, int]]:
    """
    Decodificar calibración del stick analógico desde SPI
    
    Returns:
        Dict con 'center', 'x_min', 'x_max', 'y_min', 'y_max'
    """
    if len(data) < 9:
        return None
    
    # Factory calibration format (9 bytes)
    # Bytes 0-2: X max, Y max
    # Bytes 3-5: X center, Y center
    # Bytes 6-8: X min, Y min
    
    # Each value is 12-bit packed in weird format
    x_max = ((data[1] << 8) & 0xF00) | data[0]
    y_max = (data[2] << 4) | (data[1] >> 4)
    
    x_center = ((data[4] << 8) & 0xF00) | data[3]
    y_center = (data[5] << 4) | (data[4] >> 4)
    
    x_min = ((data[7] << 8) & 0xF00) | data[6]
    y_min = (data[8] << 4) | (data[7] >> 4)
    
    return {
        'center': {'x': x_center, 'y': y_center},
        'min': {'x': x_min, 'y': y_min},
        'max': {'x': x_max, 'y': y_max},
        'deadzone': 0xAE,  # Default deadzone
    }


def calculate_stick_position(raw_x: int, raw_y: int, calibration: Dict) -> Dict[str, float]:
    """
    Calcular posición normalizada del stick (-1.0 a 1.0) con calibración
    
    Args:
        raw_x: Valor raw X del stick
        raw_y: Valor raw Y del stick
        calibration: Dict de calibración desde decode_stick_calibration
    
    Returns:
        Dict con 'x' y 'y' normalizados (-1.0 a 1.0)
    """
    if not calibration:
        # Sin calibración, normalizar raw (0-255 -> -1.0 a 1.0)
        return {
            'x': (raw_x - 127.5) / 127.5,
            'y': (raw_y - 127.5) / 127.5
        }
    
    center = calibration['center']
    min_val = calibration['min']
    max_val = calibration['max']
    deadzone = calibration.get('deadzone', 0xAE)
    
    # Deadzone check
    dx = raw_x - center['x']
    dy = raw_y - center['y']
    
    if abs(dx) < deadzone and abs(dy) < deadzone:
        return {'x': 0.0, 'y': 0.0}
    
    # Normalize with calibration
    if raw_x >= center['x']:
        norm_x = dx / (max_val['x'] - center['x'])
    else:
        norm_x = dx / (center['x'] - min_val['x'])
    
    if raw_y >= center['y']:
        norm_y = dy / (max_val['y'] - center['y'])
    else:
        norm_y = dy / (center['y'] - min_val['y'])
    
    # Clamp to -1.0 to 1.0
    norm_x = max(-1.0, min(1.0, norm_x))
    norm_y = max(-1.0, min(1.0, norm_y))
    
    return {'x': norm_x, 'y': norm_y}
