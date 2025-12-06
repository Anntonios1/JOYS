"""
Test de vibración usando XInput (API nativa de Windows)
XInput es lo que usan los juegos y aplicaciones para vibración
"""
import ctypes
import time
from ctypes import wintypes

# Cargar la DLL de XInput
try:
    xinput = ctypes.WinDLL('xinput1_4.dll')
except:
    try:
        xinput = ctypes.WinDLL('xinput1_3.dll')
    except:
        try:
            xinput = ctypes.WinDLL('xinput9_1_0.dll')
        except:
            print("❌ No se pudo cargar XInput")
            exit(1)

# Definir estructuras de XInput
class XINPUT_VIBRATION(ctypes.Structure):
    _fields_ = [
        ("wLeftMotorSpeed", wintypes.WORD),   # Motor izquierdo (heavy)
        ("wRightMotorSpeed", wintypes.WORD),  # Motor derecho (light)
    ]

class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", wintypes.DWORD),
        ("Gamepad", ctypes.c_byte * 16),
    ]

class XINPUT_BATTERY_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BatteryType", ctypes.c_ubyte),
        ("BatteryLevel", ctypes.c_ubyte),
    ]

# Funciones de XInput
XInputGetState = xinput.XInputGetState
XInputGetState.argtypes = [wintypes.DWORD, ctypes.POINTER(XINPUT_STATE)]
XInputGetState.restype = wintypes.DWORD

XInputSetState = xinput.XInputSetState
XInputSetState.argtypes = [wintypes.DWORD, ctypes.POINTER(XINPUT_VIBRATION)]
XInputSetState.restype = wintypes.DWORD

XInputGetBatteryInformation = xinput.XInputGetBatteryInformation
XInputGetBatteryInformation.argtypes = [wintypes.DWORD, ctypes.c_ubyte, ctypes.POINTER(XINPUT_BATTERY_INFORMATION)]
XInputGetBatteryInformation.restype = wintypes.DWORD

ERROR_SUCCESS = 0
ERROR_DEVICE_NOT_CONNECTED = 1167

print("=" * 70)
print("🎮 TEST DE VIBRACIÓN - XInput API")
print("=" * 70)
print()

# Buscar controladores conectados
print("🔍 Buscando controladores XInput...")
connected_controllers = []

for i in range(4):  # XInput soporta hasta 4 controladores
    state = XINPUT_STATE()
    result = XInputGetState(i, ctypes.byref(state))
    
    if result == ERROR_SUCCESS:
        connected_controllers.append(i)
        print(f"✅ Controlador #{i} conectado")
        
        # Leer batería
        battery = XINPUT_BATTERY_INFORMATION()
        if XInputGetBatteryInformation(i, 0, ctypes.byref(battery)) == ERROR_SUCCESS:
            battery_types = ["Disconnected", "Wired", "Alkaline", "NiMH", "Unknown"]
            battery_levels = ["Empty", "Low", "Medium", "Full"]
            
            btype = battery_types[battery.BatteryType] if battery.BatteryType < len(battery_types) else "Unknown"
            blevel = battery_levels[battery.BatteryLevel] if battery.BatteryLevel < len(battery_levels) else "Unknown"
            print(f"   🔋 Batería: {blevel} ({btype})")

if not connected_controllers:
    print("❌ No se encontraron controladores XInput")
    print("\n💡 Nota: XInput solo detecta controladores compatibles con Xbox")
    print("   Los Joy-Cons no son compatibles con XInput directamente")
    print("   El DualShock 4 puede ser compatible si está en modo XInput")
    exit(1)

print(f"\n✅ Total: {len(connected_controllers)} controladores\n")
print("=" * 70)

# Probar vibración en cada controlador
for controller_id in connected_controllers:
    print(f"\n🎮 Controlador #{controller_id}")
    print("-" * 70)
    
    # Test 1: Solo motor pesado (izquierdo)
    print("📳 Test 1: Motor pesado (heavy/left) - 2 segundos...")
    vibration = XINPUT_VIBRATION()
    vibration.wLeftMotorSpeed = 65535  # Máximo
    vibration.wRightMotorSpeed = 0
    
    result = XInputSetState(controller_id, ctypes.byref(vibration))
    if result == ERROR_SUCCESS:
        print("   ✅ Vibrando motor pesado...")
        time.sleep(2)
    else:
        print(f"   ❌ Error: {result}")
    
    # Test 2: Solo motor ligero (derecho)
    print("📳 Test 2: Motor ligero (light/right) - 2 segundos...")
    vibration.wLeftMotorSpeed = 0
    vibration.wRightMotorSpeed = 65535  # Máximo
    
    result = XInputSetState(controller_id, ctypes.byref(vibration))
    if result == ERROR_SUCCESS:
        print("   ✅ Vibrando motor ligero...")
        time.sleep(2)
    else:
        print(f"   ❌ Error: {result}")
    
    # Test 3: Ambos motores
    print("📳 Test 3: Ambos motores - 2 segundos...")
    vibration.wLeftMotorSpeed = 50000
    vibration.wRightMotorSpeed = 50000
    
    result = XInputSetState(controller_id, ctypes.byref(vibration))
    if result == ERROR_SUCCESS:
        print("   ✅ Vibrando ambos motores...")
        time.sleep(2)
    else:
        print(f"   ❌ Error: {result}")
    
    # Detener vibración
    vibration.wLeftMotorSpeed = 0
    vibration.wRightMotorSpeed = 0
    XInputSetState(controller_id, ctypes.byref(vibration))
    print("   ⏹️  Vibración detenida")

print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)
print("\n✅ XInput es la API nativa de Windows para gamepads")
print("   • Usado por juegos y aplicaciones")
print("   • Vibración funciona directamente sin CRC ni formateo complejo")
print("   • Solo detecta controladores Xbox y compatibles")
print("\n💡 Para la API podemos usar:")
print("   1. XInput para DS4/DS5 (si están en modo XInput)")
print("   2. HID directo para Joy-Cons (que ya funciona)")
print("=" * 70)
