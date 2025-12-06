import asyncio
from bluetooth_manager import BluetoothManager

async def test_unpair():
    print("Buscando Joy-Cons...")
    joycons = await BluetoothManager.find_joycons()
    
    print(f"Encontrados: {len(joycons)}")
    
    if not joycons:
        print("No hay Joy-Cons para desemparejar")
        return
    
    # Tomar el primero (debe ser el dispositivo principal, no una interfaz)
    # Filtrar para obtener solo el dispositivo principal
    main_device = None
    for joycon in joycons:
        if "BluetoothDevice" in joycon['id']:
            main_device = joycon
            break
    
    if not main_device:
        main_device = joycons[0]
    
    print(f"\nDesemparejando: {main_device['name']}")
    print(f"ID: {main_device['id']}\n")
    
    result = await BluetoothManager.unpair_device(main_device['id'])
    
    print(f"Resultado: {result['success']}")
    print(f"Mensaje: {result['message']}")
    
    # Verificar si sigue ahí
    print("\nVerificando...")
    joycons_after = await BluetoothManager.find_joycons()
    print(f"Joy-Cons después: {len(joycons_after)}")

if __name__ == "__main__":
    asyncio.run(test_unpair())
