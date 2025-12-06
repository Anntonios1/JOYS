"""
Mantener Joy-Cons conectados - Evita desconexión automática
Envía comandos periódicos para mantener la conexión activa
"""

import hid
import time
import sys

NINTENDO_VENDOR_ID = 0x057E
JOYCON_L_PRODUCT = 0x2006
JOYCON_R_PRODUCT = 0x2007

def send_keepalive(device):
    """Enviar comando keep-alive al Joy-Con"""
    try:
        # Rumble neutral (mantiene conexión sin vibrar)
        report = bytearray(64)
        report[0] = 0x10  # Rumble only report
        report[1] = 0x00
        report[2:10] = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]
        device.write(bytes(report))
        return True
    except:
        return False

def keep_alive():
    """Mantener Joy-Cons conectados indefinidamente"""
    print("🎮 Manteniendo Joy-Cons conectados...")
    print("💡 Presiona Ctrl+C para detener\n")
    
    devices = {}
    
    try:
        while True:
            # Buscar Joy-Cons conectados
            current_devices = {}
            
            for device_dict in hid.enumerate(NINTENDO_VENDOR_ID):
                if device_dict['product_id'] in [JOYCON_L_PRODUCT, JOYCON_R_PRODUCT]:
                    path = device_dict['path']
                    side = "L" if device_dict['product_id'] == JOYCON_L_PRODUCT else "R"
                    
                    # Abrir dispositivo si no está abierto
                    if path not in devices:
                        try:
                            dev = hid.device()
                            dev.open_path(path)
                            devices[path] = {'device': dev, 'side': side}
                            print(f"✅ Joy-Con ({side}) conectado")
                        except Exception as e:
                            print(f"❌ Error conectando Joy-Con ({side}): {e}")
                            continue
                    
                    current_devices[path] = True
            
            # Eliminar dispositivos desconectados
            for path in list(devices.keys()):
                if path not in current_devices:
                    side = devices[path]['side']
                    try:
                        devices[path]['device'].close()
                    except:
                        pass
                    del devices[path]
                    print(f"⚠️  Joy-Con ({side}) desconectado")
            
            # Enviar keep-alive a todos los dispositivos
            for path, info in devices.items():
                if not send_keepalive(info['device']):
                    print(f"⚠️  Error enviando keep-alive a Joy-Con ({info['side']})")
            
            # Esperar 10 segundos antes del próximo keep-alive
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Deteniendo...")
        
        # Cerrar todos los dispositivos
        for path, info in devices.items():
            try:
                info['device'].close()
                print(f"👋 Joy-Con ({info['side']}) cerrado")
            except:
                pass
        
        print("✅ Finalizado")

if __name__ == "__main__":
    keep_alive()
