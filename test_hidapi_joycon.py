"""
Test hidapi - Comunicación directa con Joy-Con
"""

import sys

print("=" * 70)
print("🕹️  Test hidapi - Joy-Con Direct Communication")
print("=" * 70)

try:
    import hid
    print("✅ hidapi importado correctamente\n")
except ImportError as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

def list_hid_devices():
    """Listar todos los dispositivos HID"""
    print("🔍 Escaneando dispositivos HID...\n")
    
    devices = hid.enumerate()
    
    joycon_devices = []
    other_controllers = []
    
    # IDs conocidos de Joy-Con
    NINTENDO_VENDOR = 0x057e
    JOYCON_L_PRODUCT = 0x2006
    JOYCON_R_PRODUCT = 0x2007
    PRO_CONTROLLER = 0x2009
    
    for device in devices:
        vendor_id = device['vendor_id']
        product_id = device['product_id']
        product_name = device['product_string']
        
        # Detectar Joy-Con
        if vendor_id == NINTENDO_VENDOR:
            if product_id == JOYCON_L_PRODUCT:
                device['type'] = '🕹️ Joy-Con (L)'
                joycon_devices.append(device)
            elif product_id == JOYCON_R_PRODUCT:
                device['type'] = '🕹️ Joy-Con (R)'
                joycon_devices.append(device)
            elif product_id == PRO_CONTROLLER:
                device['type'] = '🎮 Pro Controller'
                joycon_devices.append(device)
        
        # Otros controladores
        elif product_name and any(kw in product_name.lower() for kw in 
                                ['controller', 'gamepad', 'xbox', 'playstation', 'dualsense']):
            device['type'] = f"🎮 {product_name}"
            other_controllers.append(device)
    
    return joycon_devices, other_controllers, devices

def print_device_info(device, index=None):
    """Imprimir información de un dispositivo"""
    prefix = f"#{index} " if index else ""
    device_type = device.get('type', device.get('product_string', 'Desconocido'))
    
    print(f"{prefix}{device_type}")
    print(f"   Vendor ID:  0x{device['vendor_id']:04x}")
    print(f"   Product ID: 0x{device['product_id']:04x}")
    print(f"   Path:       {device['path']}")
    print(f"   Interface:  {device['interface_number']}")
    print()

def test_joycon_connection(device):
    """Intentar conectar con Joy-Con"""
    print(f"\n🔌 Intentando conectar con {device.get('type', 'dispositivo')}...")
    print(f"   Path: {device['path']}\n")
    
    try:
        # Abrir dispositivo
        h = hid.device()
        h.open_path(device['path'])
        
        print("✅ Conexión establecida!")
        
        # Obtener info del fabricante
        try:
            manufacturer = h.get_manufacturer_string()
            product = h.get_product_string()
            serial = h.get_serial_number_string()
            
            print(f"   Fabricante: {manufacturer}")
            print(f"   Producto:   {product}")
            print(f"   Serial:     {serial}")
        except:
            pass
        
        # Intentar leer estado (no bloqueante)
        print("\n📊 Intentando leer estado del Joy-Con...")
        h.set_nonblocking(True)
        
        # Enviar comando simple para obtener info
        # 0x01 = solicitar info del dispositivo
        try:
            # Intentar leer datos existentes
            data = h.read(64, timeout_ms=100)
            if data:
                print(f"✅ Datos recibidos: {len(data)} bytes")
                print(f"   Primeros bytes: {' '.join(f'{b:02x}' for b in data[:16])}")
            else:
                print("⚠️  No hay datos disponibles (normal si está inactivo)")
        except Exception as e:
            print(f"⚠️  No se pudieron leer datos: {e}")
        
        h.close()
        print("\n✅ Prueba completada exitosamente!")
        return True
        
    except Exception as e:
        print(f"❌ Error al conectar: {e}")
        return False

def main():
    print("🚀 Iniciando escaneo...\n")
    
    joycons, controllers, all_devices = list_hid_devices()
    
    print("=" * 70)
    print("📊 RESULTADOS:")
    print("=" * 70)
    
    if joycons:
        print(f"\n🕹️  JOY-CON ENCONTRADOS ({len(joycons)}):")
        print("-" * 70)
        for i, device in enumerate(joycons, 1):
            print_device_info(device, i)
        
        # Probar conexión con el primero
        print("=" * 70)
        print("🧪 TEST DE CONEXIÓN:")
        print("=" * 70)
        test_joycon_connection(joycons[0])
    else:
        print("\n⚠️  No se encontraron Joy-Con")
        print("\n💡 Posibles causas:")
        print("   • Joy-Con no está conectado (presiona un botón)")
        print("   • Driver HID no está activo")
        print("   • Joy-Con necesita re-emparejarse")
    
    if controllers:
        print(f"\n🎮 OTROS CONTROLADORES ({len(controllers)}):")
        print("-" * 70)
        for i, device in enumerate(controllers, 1):
            print_device_info(device, i)
    
    print("\n" + "=" * 70)
    print("💡 RESUMEN:")
    print("=" * 70)
    print(f"""
Total dispositivos HID: {len(all_devices)}
Joy-Con encontrados:    {len(joycons)}
Otros controladores:    {len(controllers)}

Si hidapi detecta el Joy-Con, podemos:
✅ Leer estado de botones y sticks en tiempo real
✅ Enviar comandos (vibración, LEDs, etc.)
✅ Detectar cuando se conecta/desconecta
❌ NO podemos forzar la reconexión inicial (Windows debe conectar)

Solución para reconexión:
1. Presionar cualquier botón del Joy-Con
2. O implementar watchdog que detecte cuando desaparece
3. O usar script de reconexión como admin en segundo plano
""")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelado")
