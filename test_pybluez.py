"""
Test con PyBluez - API nativa para Bluetooth Classic
"""

import sys

print("=" * 60)
print("🎮 Test PyBluez - Bluetooth Classic")
print("=" * 60)

try:
    import bluetooth
    print("✅ PyBluez importado correctamente\n")
except ImportError as e:
    print(f"❌ Error importando bluetooth: {e}")
    print("\n💡 PyBluez requiere dependencias nativas de Windows")
    print("   Intentando instalar...")
    sys.exit(1)

def scan_bluetooth_devices():
    """Escanear dispositivos Bluetooth Classic cercanos"""
    print("🔎 Escaneando dispositivos Bluetooth Classic...")
    print("   💡 Pon tu Joy-Con en modo emparejamiento (LED parpadeando)")
    print("   ⏱️  Esto puede tomar 10-15 segundos...\n")
    
    try:
        # Buscar dispositivos cercanos
        nearby_devices = bluetooth.discover_devices(
            duration=15,
            lookup_names=True,
            flush_cache=True,
            lookup_class=True
        )
        
        print(f"✅ Escaneo completado!")
        print(f"📊 Dispositivos encontrados: {len(nearby_devices)}\n")
        
        if nearby_devices:
            print("=" * 60)
            print("📱 DISPOSITIVOS DETECTADOS:")
            print("=" * 60)
            
            gamepad_keywords = ['joy', 'con', 'nintendo', 'switch', 'pro controller',
                              'dualsense', 'dualshock', 'playstation', 'ps4', 'ps5',
                              'xbox', 'controller', 'gamepad']
            
            gamepads = []
            others = []
            
            for addr, name, device_class in nearby_devices:
                is_gamepad = any(kw in name.lower() for kw in gamepad_keywords) if name else False
                
                device_info = {
                    'address': addr,
                    'name': name,
                    'class': device_class
                }
                
                if is_gamepad:
                    gamepads.append(device_info)
                else:
                    others.append(device_info)
            
            # Mostrar gamepads primero
            if gamepads:
                print("\n🎮 GAMEPADS/CONTROLADORES:")
                for i, dev in enumerate(gamepads, 1):
                    print(f"\n   #{i} 🕹️  {dev['name']}")
                    print(f"      Dirección: {dev['address']}")
                    print(f"      Clase: {hex(dev['class']) if dev['class'] else 'N/A'}")
                    
                    # Intentar obtener servicios
                    try:
                        services = bluetooth.find_service(address=dev['address'])
                        if services:
                            print(f"      Servicios: {len(services)}")
                    except:
                        pass
            
            # Mostrar otros dispositivos
            if others:
                print(f"\n📱 OTROS DISPOSITIVOS ({len(others)}):")
                for i, dev in enumerate(others[:5], 1):
                    print(f"   #{i} {dev['name'] if dev['name'] else 'Sin nombre'} ({dev['address']})")
                
                if len(others) > 5:
                    print(f"   ... y {len(others) - 5} más")
            
            return nearby_devices
        else:
            print("⚠️  No se encontraron dispositivos")
            print("\n💡 Consejos:")
            print("   🕹️  Joy-Con: Botón sync 3+ segundos (LED parpadea)")
            print("   🎮 DualSense: PS + Share hasta parpadeo azul")
            print("   🎮 Xbox: Botón pair hasta parpadeo")
            print("   ✅ Bluetooth activo y visible en Windows")
            print("   🔓 Ejecuta como administrador si no detecta nada")
            return []
            
    except OSError as e:
        print(f"❌ Error del sistema: {e}")
        print("\n💡 Posibles causas:")
        print("   • Bluetooth no está activo")
        print("   • No hay adaptador Bluetooth")
        print("   • Permisos insuficientes (ejecuta como admin)")
        return []
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    print("\n🚀 Iniciando detección...\n")
    
    devices = scan_bluetooth_devices()
    
    print("\n" + "=" * 60)
    print("✅ Test completado")
    print("=" * 60)
    
    if devices:
        print(f"\n💡 PyBluez funciona!")
        print(f"   Podemos implementar en el overlay:")
        print(f"   • Escaneo de dispositivos cercanos")
        print(f"   • Detección automática de gamepads")
        print(f"   • Emparejamiento programático")
    else:
        print("\n⚠️  Si no detectó dispositivos, intenta:")
        print("   1. Ejecutar como administrador")
        print("   2. Verificar que Bluetooth esté activo")
        print("   3. Poner el dispositivo MUY cerca del PC")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Cancelado")
