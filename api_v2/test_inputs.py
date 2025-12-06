#!/usr/bin/env python3
"""
Script para probar las entradas de los controles
"""
import hid
import time
import sys

# IDs de fabricantes
NINTENDO_VID = 0x057E
SONY_VID = 0x054C

# PIDs Nintendo
JOYCON_L_PID = 0x2006
JOYCON_R_PID = 0x2007
PRO_CONTROLLER_PID = 0x2009

# PIDs Sony
DS4_V1_PID = 0x05C4
DS4_V2_PID = 0x09CC
DS5_PID = 0x0CE6

def get_controller_type(vid, pid):
    if vid == NINTENDO_VID:
        if pid == JOYCON_L_PID: return "Joy-Con (L)"
        elif pid == JOYCON_R_PID: return "Joy-Con (R)"
        elif pid == PRO_CONTROLLER_PID: return "Pro Controller"
    elif vid == SONY_VID:
        if pid == DS4_V1_PID: return "DualShock 4 v1"
        elif pid == DS4_V2_PID: return "DualShock 4 v2"
        elif pid == DS5_PID: return "DualSense (PS5)"
    return "Unknown"

def list_controllers():
    print("\n" + "="*60)
    print("CONTROLES DETECTADOS")
    print("="*60)
    
    devices = hid.enumerate()
    controllers = []
    
    for d in devices:
        vid = d['vendor_id']
        pid = d['product_id']
        
        if vid in [NINTENDO_VID, SONY_VID]:
            controller_type = get_controller_type(vid, pid)
            controllers.append({
                'type': controller_type,
                'vid': vid,
                'pid': pid,
                'serial': d['serial_number'],
                'path': d['path'],
                'product': d['product_string']
            })
    
    if not controllers:
        print("\n❌ No se detectaron controles Nintendo o Sony")
        return []
    
    for i, c in enumerate(controllers):
        print(f"\n[{i+1}] {c['type']}")
        print(f"    VID: 0x{c['vid']:04X}, PID: 0x{c['pid']:04X}")
        print(f"    Serial: {c['serial']}")
        print(f"    Producto: {c['product']}")
    
    return controllers

def test_controller_input(controller):
    """Probar entradas de un control"""
    print(f"\n📡 Probando entradas de: {controller['type']}")
    print("Presiona botones o mueve los sticks. Ctrl+C para salir.\n")
    
    try:
        device = hid.device()
        device.open_path(controller['path'])
        device.set_nonblocking(True)
        
        last_data = None
        read_count = 0
        start_time = time.time()
        
        while True:
            data = device.read(64)
            
            if data:
                read_count += 1
                elapsed = time.time() - start_time
                hz = read_count / elapsed if elapsed > 0 else 0
                
                # Mostrar solo si los datos cambiaron
                if data != last_data:
                    # Formatear bytes como hex
                    hex_data = ' '.join(f'{b:02X}' for b in data[:20])
                    print(f"[{hz:.1f} Hz] {hex_data}...")
                    last_data = data
            
            time.sleep(0.001)
            
    except KeyboardInterrupt:
        print("\n\n✅ Prueba finalizada")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        try:
            device.close()
        except:
            pass

def main():
    print("\n🎮 TEST DE ENTRADAS DE CONTROLES")
    print("="*60)
    
    controllers = list_controllers()
    
    if not controllers:
        return
    
    print("\n" + "-"*60)
    
    if len(controllers) == 1:
        choice = 0
    else:
        print("\nSelecciona un control para probar (número) o 'q' para salir:")
        try:
            inp = input("> ").strip()
            if inp.lower() == 'q':
                return
            choice = int(inp) - 1
            if choice < 0 or choice >= len(controllers):
                print("❌ Opción inválida")
                return
        except ValueError:
            print("❌ Entrada inválida")
            return
    
    test_controller_input(controllers[choice])

if __name__ == "__main__":
    main()
