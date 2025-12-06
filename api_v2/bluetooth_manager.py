"""
Módulo para gestionar dispositivos Bluetooth usando Windows Runtime API
"""
import asyncio
import sys
from typing import List, Optional, Dict

# Cargar Windows Runtime
try:
    from winsdk.windows.devices.enumeration import DeviceInformation, DeviceUnpairingResultStatus
    from winsdk.windows.devices.bluetooth import BluetoothDevice
except ImportError:
    print("Error: Necesitas instalar winsdk")
    print("Ejecuta: pip install winsdk")
    sys.exit(1)


class BluetoothManager:
    """Gestor de dispositivos Bluetooth"""
    
    @staticmethod
    async def disconnect_bluetooth(mac_address: str = None, device_name: str = None) -> Dict:
        """
        Desconectar un dispositivo Bluetooth (sin desemparejar)
        
        Para clásico Bluetooth no hay una API directa de "desconectar", 
        pero podemos intentar cerrar la conexión L2CAP/RFCOMM.
        En la práctica, para DS4/DS5 esto no funciona porque mantienen la conexión.
        
        Args:
            mac_address: Dirección MAC del dispositivo
            device_name: Nombre del dispositivo (alternativo)
            
        Returns:
            Dict con status y mensaje
        """
        try:
            # Intentar obtener el dispositivo Bluetooth
            device = None
            
            if mac_address:
                # Convertir MAC a formato Windows (sin separadores)
                mac_clean = mac_address.replace(":", "").replace("-", "").upper()
                mac_int = int(mac_clean, 16)
                
                try:
                    device = await BluetoothDevice.from_bluetooth_address_async(mac_int)
                except Exception as e:
                    print(f"⚠️ No se pudo obtener dispositivo por MAC: {e}")
            
            if device:
                device_name = device.name
                connection_status = device.connection_status  # 0=Disconnected, 1=Connected
                
                # Para Classic Bluetooth, no hay un método directo de "desconectar"
                # Lo que podemos hacer es cerrar las sesiones/servicios
                # Pero la mayoría de dispositivos HID se reconectan automáticamente
                
                if connection_status == 0:
                    return {
                        "success": True,
                        "already_disconnected": True,
                        "message": f"{device_name} ya estaba desconectado"
                    }
                
                # Intentar cerrar conexión vía DeviceAccessInformation
                # (Esto no siempre funciona para HID)
                return {
                    "success": False,
                    "message": f"{device_name} está conectado. Para desconectar un mando DS4/DS5 Bluetooth: mantén PS+Share por 10 segundos, o usa Desemparejar.",
                    "device_name": device_name,
                    "connection_status": "connected"
                }
            else:
                return {
                    "success": False,
                    "message": "Dispositivo Bluetooth no encontrado"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error al desconectar: {str(e)}"
            }
    
    @staticmethod
    async def find_all_bluetooth_devices() -> List[Dict]:
        """
        Encuentra todos los dispositivos Bluetooth emparejados
        
        Returns:
            Lista de dispositivos con nombre, ID y estado
        """
        devices = []
        
        try:
            # Obtener selector para dispositivos Bluetooth
            selector = BluetoothDevice.get_device_selector()
            
            # Buscar dispositivos (find_all_async acepta el selector directamente)
            from winsdk.windows.foundation.collections import IIterable
            device_collection = await DeviceInformation.find_all_async()
            
            for device_info in device_collection:
                # Filtrar solo dispositivos Bluetooth que coincidan
                if "Bluetooth" in device_info.id or "BTHENUM" in device_info.id:
                    devices.append({
                        "name": device_info.name,
                        "id": device_info.id,
                        "is_paired": device_info.pairing.is_paired if device_info.pairing else False
                    })
        
        except Exception as e:
            import traceback
            print(f"Error buscando dispositivos Bluetooth: {e}")
            traceback.print_exc()
        
        return devices
    
    @staticmethod
    async def find_joycons() -> List[Dict]:
        """
        Encuentra solo Joy-Cons emparejados
        
        Returns:
            Lista de Joy-Cons encontrados
        """
        all_devices = await BluetoothManager.find_all_bluetooth_devices()
        
        # Filtrar solo Joy-Cons
        joycons = [
            dev for dev in all_devices 
            if "Joy-Con" in dev["name"] or "Nintendo" in dev["name"]
        ]
        
        return joycons
    
    @staticmethod
    async def unpair_device(device_id: str) -> Dict:
        """
        Desempareja un dispositivo Bluetooth específico
        
        Args:
            device_id: ID del dispositivo a desemparejar
            
        Returns:
            Dict con status y mensaje
        """
        try:
            # Obtener información del dispositivo
            device_info = await DeviceInformation.create_from_id_async(device_id)
            
            if not device_info:
                return {
                    "success": False,
                    "message": f"Dispositivo no encontrado: {device_id}"
                }
            
            # Intentar desemparejar directamente sin verificar is_paired
            # (is_paired puede ser False en interfaces del dispositivo)
            unpair_result = await device_info.pairing.unpair_async()
            
            if unpair_result.status == DeviceUnpairingResultStatus.UNPAIRED:
                return {
                    "success": True,
                    "message": f"Dispositivo {device_info.name} desemparejado correctamente"
                }
            elif unpair_result.status == DeviceUnpairingResultStatus.ALREADY_UNPAIRED:
                return {
                    "success": True,
                    "message": f"Dispositivo {device_info.name} ya estaba desemparejado"
                }
            elif unpair_result.status == DeviceUnpairingResultStatus.FAILED:
                return {
                    "success": False,
                    "message": f"Fallo al desemparejar {device_info.name}. El dispositivo puede no estar emparejado o no ser accesible."
                }
            else:
                return {
                    "success": False,
                    "message": f"Fallo al desemparejar: {unpair_result.status}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error al desemparejar dispositivo: {str(e)}"
            }
    
    @staticmethod
    async def unpair_by_name(device_name: str) -> Dict:
        """
        Desempareja un dispositivo por su nombre
        
        Args:
            device_name: Nombre del dispositivo (ej: "Joy-Con (L)")
            
        Returns:
            Dict con status y mensaje
        """
        try:
            # Buscar el dispositivo
            all_devices = await BluetoothManager.find_all_bluetooth_devices()
            
            matching_device = None
            for dev in all_devices:
                if device_name.lower() in dev["name"].lower():
                    matching_device = dev
                    break
            
            if not matching_device:
                return {
                    "success": False,
                    "message": f"No se encontró dispositivo con nombre: {device_name}"
                }
            
            # Desemparejar usando el ID
            return await BluetoothManager.unpair_device(matching_device["id"])
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error buscando dispositivo: {str(e)}"
            }
    
    @staticmethod
    async def unpair_by_mac(mac_address: str) -> Dict:
        """
        Desempareja un dispositivo por su dirección MAC
        
        Args:
            mac_address: Dirección MAC (formato: DC68EB8346EE o DC:68:EB:83:46:EE)
            
        Returns:
            Dict con status y mensaje
        """
        try:
            # Normalizar MAC (quitar : y -)
            mac_clean = mac_address.replace(":", "").replace("-", "").upper()
            
            # Buscar todos los dispositivos Bluetooth
            all_devices = await BluetoothManager.find_all_bluetooth_devices()
            
            # Buscar el dispositivo que contenga esta MAC en su ID
            matching_device = None
            for dev in all_devices:
                if mac_clean in dev["id"].upper():
                    # Priorizar el que tenga "BluetoothDevice" (es el principal)
                    if "BluetoothDevice" in dev["id"]:
                        matching_device = dev
                        break
                    elif not matching_device:
                        matching_device = dev
            
            if not matching_device:
                return {
                    "success": False,
                    "message": f"No se encontró dispositivo con MAC: {mac_address}"
                }
            
            # Desemparejar usando el ID
            result = await BluetoothManager.unpair_device(matching_device["id"])
            
            if result["success"]:
                result["message"] += f" (MAC: {mac_address})"
            
            return result
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error buscando dispositivo por MAC: {str(e)}"
            }


# Funciones de prueba
async def test_list_devices():
    """Prueba: Listar todos los dispositivos Bluetooth"""
    print("=== DISPOSITIVOS BLUETOOTH EMPAREJADOS ===\n")
    
    devices = await BluetoothManager.find_all_bluetooth_devices()
    
    if not devices:
        print("No se encontraron dispositivos emparejados")
        return
    
    for i, device in enumerate(devices, 1):
        print(f"[{i}] {device['name']}")
        print(f"    ID: {device['id']}")
        print(f"    Emparejado: {device['is_paired']}")
        print()


async def test_list_joycons():
    """Prueba: Listar solo Joy-Cons"""
    print("=== JOY-CONS ENCONTRADOS ===\n")
    
    joycons = await BluetoothManager.find_joycons()
    
    if not joycons:
        print("No se encontraron Joy-Cons emparejados")
        return
    
    for i, joycon in enumerate(joycons, 1):
        print(f"[{i}] {joycon['name']}")
        print(f"    ID: {joycon['id']}")
        print()
    
    return joycons


async def test_unpair_joycon():
    """Prueba: Desemparejar un Joy-Con específico"""
    print("=== PRUEBA DE DESEMPAREJAMIENTO ===\n")
    
    # Buscar Joy-Cons
    joycons = await BluetoothManager.find_joycons()
    
    if not joycons:
        print("No se encontraron Joy-Cons para desemparejar")
        return
    
    # Mostrar opciones
    print("Joy-Cons disponibles:")
    for i, joycon in enumerate(joycons, 1):
        print(f"[{i}] {joycon['name']}")
    print()
    
    # Seleccionar el primero como prueba
    if len(joycons) > 0:
        selected = joycons[0]
        print(f"Seleccionado para prueba: {selected['name']}")
        print(f"ID: {selected['id']}\n")
        
        # Confirmar
        confirm = input("¿Deseas desemparejar este dispositivo? (S/N): ")
        if confirm.upper() == "S":
            print("\nDesemparejando...")
            result = await BluetoothManager.unpair_device(selected['id'])
            
            if result['success']:
                print(f"✓ {result['message']}")
            else:
                print(f"✗ {result['message']}")
        else:
            print("Operación cancelada")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python bluetooth_manager.py list        - Listar todos los dispositivos")
        print("  python bluetooth_manager.py joycons     - Listar solo Joy-Cons")
        print("  python bluetooth_manager.py unpair      - Desemparejar un Joy-Con (interactivo)")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "list":
        asyncio.run(test_list_devices())
    elif command == "joycons":
        asyncio.run(test_list_joycons())
    elif command == "unpair":
        asyncio.run(test_unpair_joycon())
    else:
        print(f"Comando desconocido: {command}")
