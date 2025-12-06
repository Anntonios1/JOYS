"""
Explorar API de winsdk para DeviceInformation
"""

import sys

try:
    from winsdk.windows.devices.enumeration import DeviceInformation
    from winsdk.windows.devices.bluetooth import BluetoothDevice
    
    print("=" * 60)
    print("🔍 Explorando API de DeviceInformation")
    print("=" * 60)
    
    print("\n📋 Métodos disponibles en DeviceInformation:")
    methods = [m for m in dir(DeviceInformation) if not m.startswith('_')]
    for i, method in enumerate(methods, 1):
        print(f"   {i}. {method}")
    
    print("\n" + "=" * 60)
    print("📋 Métodos de BluetoothDevice:")
    bt_methods = [m for m in dir(BluetoothDevice) if not m.startswith('_') and 'selector' in m.lower()]
    for i, method in enumerate(bt_methods, 1):
        print(f"   {i}. {method}")
    
    # Probar selector
    print("\n" + "=" * 60)
    print("🧪 Probando selector...")
    selector = BluetoothDevice.get_device_selector_from_pairing_state(False)
    print(f"✅ Selector generado: {selector[:100]}...")
    
    print("\n" + "=" * 60)
    print("🧪 Probando crear watcher con diferentes métodos...")
    
    # Método 1: create_watcher con string
    try:
        print("\n1. DeviceInformation.create_watcher(selector)...")
        watcher = DeviceInformation.create_watcher(selector)
        print(f"   ✅ Funciona! Tipo: {type(watcher)}")
        print(f"   Métodos del watcher: {[m for m in dir(watcher) if not m.startswith('_')][:10]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Método 2: find_all_async
    try:
        print("\n2. DeviceInformation.find_all_async(selector)...")
        print("   (requiere async, saltando)")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Exploración completada")
    
except ImportError as e:
    print(f"❌ Error: winsdk no instalado - {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
