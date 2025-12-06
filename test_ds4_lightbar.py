"""
Test de control del lightbar del DualShock 4
Basado en el código del driver hid-sony.c de Linux
"""

import hid
import time

# Colores predefinidos según Linux kernel (device_id % 7)
DS4_COLORS = [
    (0x00, 0x00, 0x40),  # Blue   - DS4 #1
    (0x40, 0x00, 0x00),  # Red    - DS4 #2
    (0x00, 0x40, 0x00),  # Green  - DS4 #3
    (0x20, 0x00, 0x20),  # Pink   - DS4 #4
    (0x02, 0x01, 0x00),  # Orange - DS4 #5
    (0x00, 0x01, 0x01),  # Teal   - DS4 #6
    (0x01, 0x01, 0x01),  # White  - DS4 #7
]

def crc32_ds4(data: bytes) -> int:
    """Calcular CRC-32 para DualShock 4 Bluetooth"""
    crc = 0xFFFFFFFF
    polynomial = 0xEDB88320
    
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ polynomial
            else:
                crc >>= 1
    
    return ~crc & 0xFFFFFFFF

def set_ds4_lightbar(device, r, g, b, is_bluetooth=True):
    """Establecer color del lightbar del DS4"""
    try:
        if is_bluetooth:
            # Bluetooth report (0x11)
            report = bytearray(78)
            report[0] = 0x11  # Report ID
            report[1] = 0xC4  # 0x80 | btPollRate donde btPollRate=0x04
            report[2] = 0x00  
            report[3] = 0x02  # outputFeaturesByte: lightbar(0x02)
            report[4] = 0x04  
            report[5] = 0x00  
            report[6] = 0     # Motor rápido (off)
            report[7] = 0     # Motor pesado (off)
            report[8] = r     # LED R
            report[9] = g     # LED G
            report[10] = b    # LED B
            report[11] = 0    # Flash on duration
            report[12] = 0    # Flash off duration
            
            # Calcular CRC-32
            crc_head = bytes([0xA2])
            crc = ~crc32_ds4(crc_head)
            crc = ~crc32_ds4(report[0:74]) ^ crc
            
            report[74] = crc & 0xFF
            report[75] = (crc >> 8) & 0xFF
            report[76] = (crc >> 16) & 0xFF
            report[77] = (crc >> 24) & 0xFF
            
            # Intentar write primero, luego send_feature_report
            result = device.write(bytes(report))
            if result == -1:
                print(f"    Debug BT: write falló, probando send_feature_report")
                result = device.send_feature_report(bytes(report))
            print(f"    Debug BT: Enviados {result} bytes")
        else:
            # USB report (0x05)
            report = bytearray(32)
            report[0] = 0x05  # Report ID
            report[1] = 0xFF  # Feature flags
            report[4] = 0     # Motor rápido (off)
            report[5] = 0     # Motor pesado (off)
            report[6] = r     # LED R
            report[7] = g     # LED G
            report[8] = b     # LED B
            report[9] = 0     # Flash on duration
            report[10] = 0    # Flash off duration
            
            # Intentar write primero, luego send_feature_report
            result = device.write(bytes(report))
            if result == -1:
                print(f"    Debug USB: write falló, probando send_feature_report")
                result = device.send_feature_report(bytes(report))
            print(f"    Debug USB: Enviados {result} bytes")
        
        return result > 0
    except Exception as e:
        print(f"    Debug: Error en set_lightbar: {e}")
        return False

def detect_connection_type(device):
    """Detectar si es Bluetooth o USB leyendo un reporte"""
    try:
        device.set_nonblocking(True)
        detected_reports = []
        for _ in range(100):
            data = device.read(64)
            if data:
                report_id = data[0]
                detected_reports.append(report_id)
                # Report ID 0x01 = USB, 0x11 = Bluetooth
                if report_id == 0x01:
                    device.set_nonblocking(False)
                    return "USB"
                elif report_id == 0x11:
                    device.set_nonblocking(False)
                    return "Bluetooth"
        device.set_nonblocking(False)
        
        # Si no detectamos nada, imprimir debug
        if detected_reports:
            unique_reports = set(detected_reports)
            print(f"    Debug: Report IDs detectados: {[hex(r) for r in unique_reports]}")
        else:
            print(f"    Debug: No se recibieron reportes")
        
        return "Unknown"
    except Exception as e:
        print(f"    Debug: Error en detección: {e}")
        return "Unknown"

def main():
    print("=== Test de Lightbar DualShock 4 ===\n")
    
    # Buscar DS4
    devices = []
    for d in hid.enumerate(0x054C, 0x09CC):
        # Filtrar solo gamepad interface
        if d.get('usage_page') == 1 and d.get('usage') == 5:
            devices.append(d)
    
    if not devices:
        print("❌ No se encontraron DS4 conectados")
        return
    
    print(f"✅ {len(devices)} DS4 encontrado(s)\n")
    
    for idx, device_info in enumerate(devices):
        path = device_info['path']
        serial = device_info.get('serial_number', 'Unknown')
        
        print(f"DS4 #{idx + 1} (Serial: {serial}):")
        
        # Conectar
        device = hid.device()
        try:
            device.open_path(path)
            print(f"  ✅ Conectado")
            
            # Detectar tipo de conexión
            conn_type = detect_connection_type(device)
            is_bluetooth = conn_type == "Bluetooth"
            print(f"  🔌 Conexión: {conn_type}")
            
            # Asignar color según índice (como Linux)
            color_idx = idx % 7
            r, g, b = DS4_COLORS[color_idx]
            color_name = ["Azul", "Rojo", "Verde", "Rosa", "Naranja", "Turquesa", "Blanco"][color_idx]
            
            print(f"  🎨 Asignando color: {color_name} (R={r}, G={g}, B={b})")
            
            if set_ds4_lightbar(device, r, g, b, is_bluetooth):
                print(f"  ✅ Color aplicado")
            else:
                print(f"  ❌ Error aplicando color")
            
            time.sleep(2)
            
            # Probar secuencia de colores
            print(f"  🌈 Probando secuencia de colores...")
            test_colors = [
                (255, 0, 0, "Rojo"),
                (0, 255, 0, "Verde"),
                (0, 0, 255, "Azul"),
                (255, 255, 0, "Amarillo"),
                (255, 0, 255, "Magenta"),
                (0, 255, 255, "Cian"),
                (255, 255, 255, "Blanco"),
            ]
            
            for r, g, b, name in test_colors:
                print(f"    - {name}...")
                set_ds4_lightbar(device, r, g, b, is_bluetooth)
                time.sleep(0.5)
            
            # Volver al color asignado
            r, g, b = DS4_COLORS[color_idx]
            set_ds4_lightbar(device, r, g, b, is_bluetooth)
            print(f"  ✅ Test completado, volviendo a {color_name}\n")
            
            device.close()
        except Exception as e:
            print(f"  ❌ Error: {e}\n")

if __name__ == "__main__":
    main()
