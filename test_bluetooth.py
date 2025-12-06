"""
Test script para probar el módulo Bluetooth
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from modules.bluetooth_manager import get_bluetooth_manager

async def test_scan():
    """Test scanning for devices"""
    print("🔍 Iniciando escaneo de dispositivos Bluetooth...")
    print("⚠️ Asegúrate de que tu Joy-Con esté en modo emparejamiento")
    print("   (Mantén presionado el botón SYNC por 3 segundos)")
    print()
    
    bt_manager = get_bluetooth_manager()
    
    try:
        print("Escaneando por 10 segundos...")
        devices = await bt_manager.scan_devices(duration=10)
        
        print(f"\n✅ Escaneo completado. Encontrados {len(devices)} dispositivos:")
        
        for device in devices:
            print(f"\n  📱 {device.name}")
            print(f"     MAC: {device.mac_address}")
            print(f"     Tipo: {device.controller_type.value}")
            print(f"     RSSI: {device.rssi} dBm")
        
        if not devices:
            print("\n⚠️ No se encontraron dispositivos.")
            print("   Verifica que:")
            print("   1. Bluetooth esté habilitado")
            print("   2. El Joy-Con esté en modo emparejamiento")
            print("   3. Las luces del Joy-Con estén parpadeando")
    
    except Exception as e:
        print(f"\n❌ Error durante el escaneo: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_scan())
