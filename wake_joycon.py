"""
Script para despertar/reconectar Joy-Con en Windows
"""

import subprocess
import time

print("=" * 70)
print("⚡ Wake Up Joy-Con")
print("=" * 70)

print("""
🎯 PASOS PARA RECONECTAR:

1. Abre Configuración de Bluetooth de Windows
2. Busca "Joy-Con (R)" en la lista
3. Si dice "Emparejado" pero no "Conectado":
   - Haz clic en "Conectar"
   - O haz clic en los 3 puntos → "Quitar dispositivo" y vuelve a emparejar

Voy a abrir la configuración ahora...
""")

input("\nPresiona ENTER para abrir Configuración de Bluetooth...")

# Abrir configuración de Bluetooth
subprocess.run(["powershell", "-Command", "Start-Process ms-settings:bluetooth"], 
               capture_output=True)

print("\n✅ Configuración abierta")
print("\n📝 Instrucciones:")
print("   1. Busca 'Joy-Con (R)' en la lista")
print("   2. Click en 'Conectar' o en los 3 puntos")
print("   3. Si no funciona, haz clic en 'Quitar dispositivo'")
print("   4. Vuelve a emparejar:")
print("      a) En el Joy-Con: mantén botón SYNC 3+ segundos")
print("      b) En Windows: Click 'Agregar dispositivo' → Bluetooth")
print("      c) Selecciona 'Joy-Con (R)' cuando aparezca")

print("\n" + "=" * 70)
print("💡 ALTERNATIVA RÁPIDA (Requiere Admin):")
print("=" * 70)
print("""
Ejecuta PowerShell como ADMINISTRADOR y corre:

$joycon = Get-PnpDevice | Where-Object {$_.FriendlyName -like '*Joy*'}
Disable-PnpDevice -InstanceId $joycon.InstanceId -Confirm:$false
Start-Sleep -Seconds 2
Enable-PnpDevice -InstanceId $joycon.InstanceId -Confirm:$false

Esto forzará un ciclo de reconexión.
""")

print("\n⏳ Esperando que conectes el Joy-Con...")
print("   Cuando veas 'Conectado' en Windows, presiona ENTER")

input()

print("\n🔍 Verificando si el Joy-Con está conectado ahora...")
time.sleep(2)

# Verificar con hidapi
try:
    import hid
    devices = hid.enumerate(0x057e, 0x2007)  # Joy-Con R
    
    if devices:
        print("✅ ¡Joy-Con detectado via HID!")
        print(f"   Encontrados {len(devices)} interfaces")
        for dev in devices:
            print(f"   • {dev['product_string']} - Interface {dev['interface_number']}")
    else:
        print("❌ Joy-Con aún no se detecta via HID")
        print("   Puede necesitar presionar un botón del Joy-Con")
        
        print("\n🔄 Intentando de nuevo...")
        print("   Presiona CUALQUIER BOTÓN en el Joy-Con ahora...")
        time.sleep(5)
        
        devices = hid.enumerate(0x057e, 0x2007)
        if devices:
            print("✅ ¡Ahora sí! Joy-Con detectado")
        else:
            print("❌ Todavía no se detecta")
            print("\n💡 El Joy-Con necesita:")
            print("   1. Estar 'Conectado' en Windows (no solo emparejado)")
            print("   2. Ser activado presionando un botón")
            
except ImportError:
    print("⚠️  hidapi no disponible, verifica manualmente")

print("\n" + "=" * 70)
