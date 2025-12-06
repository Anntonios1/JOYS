"""
Investigación: ¿Por qué los Joy-Con no se reconectan en Windows?
"""

import subprocess
import time

print("=" * 70)
print("🔬 INVESTIGACIÓN: Joy-Con + Windows Bluetooth")
print("=" * 70)

def run_ps(cmd):
    result = subprocess.run(
        ["powershell", "-Command", cmd],
        capture_output=True,
        text=True,
        timeout=30,
        encoding='utf-8',
        errors='replace'
    )
    return result.stdout.strip(), result.stderr.strip()

print("\n📋 PROBLEMA CONOCIDO:")
print("-" * 70)
print("""
Los Joy-Con tienen un comportamiento especial con Bluetooth:

1. MODO EMPAREJAMIENTO:
   - Mantener botón SYNC 3+ segundos
   - LEDs parpadean verde horizontalmente
   - Se puede ver en "Agregar dispositivo Bluetooth"
   - Aparece como "Joy-Con (L)" o "Joy-Con (R)"

2. PROBLEMA DE RECONEXIÓN:
   - Después de emparejar, el Joy-Con NO se reconecta automáticamente
   - Windows lo marca como emparejado pero "No conectado"
   - Presionar botones del Joy-Con NO lo despierta
   - Esto es diferente a Xbox/DualSense que SÍ se reconectan

3. CAUSA TÉCNICA:
   - Joy-Con usa perfil HID sobre Bluetooth (HID over Bluetooth)
   - Nintendo usa un protocolo propietario no estándar
   - Windows espera que el dispositivo inicie la conexión
   - Joy-Con espera que el HOST (PC) inicie la conexión
   - ¡DEADLOCK! Ninguno inicia la reconexión

4. SOLUCIONES CONOCIDAS:
   a) BetterJoy / JoyShockMapper: Drivers que fuerzan la reconexión
   b) Remover y reemparejar cada vez (molesto)
   c) Usar software que mantenga la conexión activa
   d) Conectar por USB-C con adaptador
""")

print("\n🔍 VERIFICANDO TU SISTEMA:")
print("-" * 70)

# 1. Ver si hay Joy-Con emparejados
print("\n1️⃣ Buscando Joy-Con emparejados...")
stdout, _ = run_ps("Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Joy*'} | Select-Object FriendlyName, Status, InstanceId")
if stdout and "Joy" in stdout:
    print("✅ Encontrado:")
    print(stdout)
else:
    print("❌ No hay Joy-Con emparejados")

# 2. Ver servicios HID Bluetooth
print("\n2️⃣ Verificando servicios HID Bluetooth...")
stdout, _ = run_ps("Get-Service | Where-Object {$_.Name -like '*hid*' -or $_.Name -like '*bluetooth*'} | Select-Object Name, Status | Format-Table")
print(stdout if stdout else "No se encontraron servicios")

# 3. Ver drivers HID
print("\n3️⃣ Verificando drivers HID instalados...")
stdout, _ = run_ps("Get-PnpDevice -Class HIDClass | Where-Object {$_.Status -eq 'OK'} | Select-Object -First 5 FriendlyName")
print(stdout if stdout else "No se encontraron drivers HID")

# 4. Verificar BetterJoy/JoyShockMapper
print("\n4️⃣ Buscando software de Joy-Con instalado...")
paths = [
    "C:\\Program Files\\BetterJoy",
    "C:\\Program Files (x86)\\BetterJoy",
    "C:\\Program Files\\JoyShockMapper",
    "$env:LOCALAPPDATA\\Programs\\BetterJoy"
]

for path in paths:
    stdout, _ = run_ps(f"Test-Path '{path}'")
    if stdout == "True":
        print(f"✅ Encontrado: {path}")
        break
else:
    print("❌ No se encontró BetterJoy ni JoyShockMapper")

print("\n" + "=" * 70)
print("💡 SOLUCIONES PROPUESTAS:")
print("=" * 70)
print("""
OPCIÓN 1: Forzar reconexión programática (COMPLEJO)
   • Usar API de Windows para iniciar conexión desde el PC
   • Requiere conocer la MAC del Joy-Con
   • Puede requerir permisos de administrador
   
OPCIÓN 2: Integrar con BetterJoy (RECOMENDADO)
   • BetterJoy ya resuelve este problema
   • Mantiene conexión activa y emula XInput
   • Podemos detectar si está corriendo y controlarlo
   
OPCIÓN 3: Usar hidapi + libusb (NATIVO)
   • Comunicación directa con el Joy-Con
   • Control total del protocolo
   • Más complejo pero más robusto
   
OPCIÓN 4: Wrapper de Windows Bluetooth API (INTERMEDIO)
   • Llamar a BluetoothAuthenticateDevice()
   • Forzar reconexión con SetServiceState()
   • Usar ctypes para llamar a bthprops.cpl
""")

print("\n🎯 RECOMENDACIÓN:")
print("-" * 70)
print("""
1. Verificar si BetterJoy está instalado
2. Si no, instalar BetterJoy o JoyShockMapper
3. Integrar overlay con BetterJoy para:
   - Detectar cuando está corriendo
   - Mostrar estado de Joy-Con conectados
   - Controlar reconexión a través de BetterJoy
   
Esto es MÁS CONFIABLE que reimplementar todo el protocolo.
""")

print("\n¿Quieres que busque BetterJoy en tu sistema o")
print("prefieres que implemente una solución nativa?")
print("=" * 70)
