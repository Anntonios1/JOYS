"""
Auto-reconexión de Joy-Cons
Detecta Joy-Cons emparejados y los reconecta automáticamente
"""

import subprocess
import time
import sys

def restart_bluetooth_adapter():
    """Reiniciar el adaptador Bluetooth"""
    print("🔄 Reiniciando adaptador Bluetooth...")
    
    try:
        # Deshabilitar adaptador Bluetooth
        result = subprocess.run(
            ['powershell', '-Command', 
             'Get-PnpDevice -Class Bluetooth -FriendlyName "*Bluetooth*" | Disable-PnpDevice -Confirm:$false'],
            capture_output=True, text=True
        )
        
        time.sleep(2)
        
        # Habilitar adaptador Bluetooth
        result = subprocess.run(
            ['powershell', '-Command', 
             'Get-PnpDevice -Class Bluetooth -FriendlyName "*Bluetooth*" | Enable-PnpDevice -Confirm:$false'],
            capture_output=True, text=True
        )
        
        time.sleep(3)
        print("✅ Adaptador Bluetooth reiniciado")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_joycons_connected():
    """Verificar si hay Joy-Cons conectados"""
    import hid
    
    NINTENDO_VENDOR_ID = 0x057E
    JOYCON_L_PRODUCT = 0x2006
    JOYCON_R_PRODUCT = 0x2007
    
    joycons = []
    for device_dict in hid.enumerate(NINTENDO_VENDOR_ID):
        if device_dict['product_id'] in [JOYCON_L_PRODUCT, JOYCON_R_PRODUCT]:
            joycons.append(device_dict)
    
    return len(joycons)

if __name__ == "__main__":
    print("=" * 60)
    print("🎮 AUTO-RECONEXIÓN DE JOY-CONS")
    print("=" * 60)
    print()
    
    # Verificar conexiones actuales
    print("🔍 Verificando Joy-Cons conectados...")
    count = check_joycons_connected()
    print(f"   Encontrados: {count}")
    
    if count < 2:
        print("\n⚠️  No se detectaron ambos Joy-Cons")
        print("💡 Intentando reconectar...")
        print()
        
        # Reiniciar adaptador Bluetooth
        if restart_bluetooth_adapter():
            print("\n⏳ Esperando 5 segundos...")
            print("💡 Presiona un botón en cada Joy-Con ahora...")
            time.sleep(5)
            
            # Verificar de nuevo
            count = check_joycons_connected()
            print(f"\n✅ Joy-Cons conectados: {count}")
            
            if count == 2:
                print("🎉 ¡Ambos Joy-Cons reconectados!")
            elif count == 1:
                print("⚠️  Solo un Joy-Con reconectado. Presiona un botón en el otro.")
            else:
                print("❌ No se pudieron reconectar. Intenta emparejarlos manualmente.")
    else:
        print("✅ Ambos Joy-Cons ya están conectados")
    
    print()
    print("=" * 60)
