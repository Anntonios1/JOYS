"""
Test - Desconectar Bluetooth sin PowerShell
Usa WMI y ctypes para acceder directamente a la API de Windows
"""

import sys
import os
import subprocess

print("=" * 70)
print("🔌 TEST DE DESCONEXIÓN BLUETOOTH")
print("=" * 70)
print()

# ============================================================================
# Método 1: Usar bluetoothctl (si está disponible)
# ============================================================================
print("🔍 Método 1: Verificando bluetoothctl...")

try:
    result = subprocess.run(['bluetoothctl', '--version'], 
                          capture_output=True, text=True, timeout=2)
    if result.returncode == 0:
        print("✅ bluetoothctl disponible")
    else:
        print("❌ bluetoothctl no disponible")
except:
    print("❌ bluetoothctl no disponible en Windows\n")

# ============================================================================
# Método 2: Usar WMI (Windows Management Instrumentation)
# ============================================================================
print("🔍 Método 2: Usando WMI...")

try:
    import wmi
    
    c = wmi.WMI()
    
    # Buscar dispositivos Bluetooth
    print("📋 Buscando dispositivos Bluetooth via WMI...")
    
    # Buscar en PnP devices
    for device in c.Win32_PnPEntity():
        if device.Name and 'joy' in device.Name.lower():
            print(f"\n   Encontrado: {device.Name}")
            print(f"   Estado: {device.Status}")
            print(f"   Device ID: {device.DeviceID[:60]}...")
            
            # Intentar deshabilitarlo
            try:
                # Usar Disable() method
                result = device.Disable()
                print(f"   🔌 Intentando desconectar... Resultado: {result}")
            except Exception as e:
                print(f"   ⚠️ No se puede desconectar via WMI: {e}")
    
    print("\n✅ WMI funcional")

except ImportError:
    print("❌ Módulo 'wmi' no instalado")
    print("   Instalar con: pip install wmi")
except Exception as e:
    print(f"❌ Error con WMI: {e}")

print()

# ============================================================================
# Método 3: Usar Windows Bluetooth API (WinRT)
# ============================================================================
print("🔍 Método 3: Usando Windows Runtime (WinRT)...")

try:
    import winrt.windows.devices.bluetooth as windows_bluetooth
    import winrt.windows.devices.enumeration as windows_enum
    import asyncio
    
    async def disconnect_bluetooth():
        # Selector para dispositivos Bluetooth emparejados
        selector = windows_bluetooth.BluetoothDevice.get_device_selector_from_pairing_state(True)
        
        # Buscar dispositivos
        devices = await windows_enum.DeviceInformation.find_all_async(selector)
        
        print(f"   Encontrados {len(devices)} dispositivos Bluetooth emparejados:")
        
        for device_info in devices:
            print(f"\n   • {device_info.name}")
            print(f"     ID: {device_info.id[:60]}...")
            
            if 'joy' in device_info.name.lower():
                print(f"     🎮 Joy-Con detectado, intentando desconectar...")
                
                try:
                    # Obtener el dispositivo Bluetooth
                    bt_device = await windows_bluetooth.BluetoothDevice.from_id_async(device_info.id)
                    
                    if bt_device:
                        # Cerrar conexión
                        bt_device.close()
                        print(f"     ✅ Dispositivo cerrado")
                    else:
                        print(f"     ❌ No se pudo obtener dispositivo")
                
                except Exception as e:
                    print(f"     ⚠️ Error: {e}")
        
        return len(devices)
    
    count = asyncio.run(disconnect_bluetooth())
    
    if count > 0:
        print(f"\n✅ WinRT funcional, {count} dispositivos encontrados")
    else:
        print(f"\n⚠️ WinRT funcional pero no encontró dispositivos")

except ImportError:
    print("❌ Módulo 'winrt' no instalado")
    print("   Instalar con: pip install winrt")
except Exception as e:
    print(f"❌ Error con WinRT: {e}")

print()

# ============================================================================
# Método 4: Usar pybluez (BlueZ para Windows)
# ============================================================================
print("🔍 Método 4: Usando PyBluez...")

try:
    import bluetooth
    
    print("📋 Buscando dispositivos cercanos...")
    
    nearby_devices = bluetooth.discover_devices(duration=3, lookup_names=True)
    
    print(f"   Encontrados {len(nearby_devices)} dispositivos:")
    
    for addr, name in nearby_devices:
        print(f"   • {name} - {addr}")
        
        if 'joy' in name.lower():
            print(f"     🎮 Joy-Con detectado")
            print(f"     ⚠️ PyBluez no soporta desconexión directa en Windows")
    
    print("\n✅ PyBluez funcional")

except ImportError:
    print("❌ Módulo 'bluetooth' (PyBluez) no instalado")
    print("   Instalar con: pip install pybluez")
except Exception as e:
    print(f"❌ Error con PyBluez: {e}")

print()

# ============================================================================
# Método 5: DevCon (Device Console) alternativa
# ============================================================================
print("🔍 Método 5: Verificando DevCon...")

devcon_paths = [
    r"C:\Windows\System32\devcon.exe",
    r"C:\Windows\SysWOW64\devcon.exe",
    r"devcon.exe"
]

devcon_found = False
for path in devcon_paths:
    if os.path.exists(path) if not path == "devcon.exe" else False:
        devcon_found = True
        print(f"✅ DevCon encontrado en: {path}")
        break

if not devcon_found:
    try:
        result = subprocess.run(['devcon', 'status', '*bluetooth*'], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            devcon_found = True
            print("✅ DevCon disponible en PATH")
    except:
        pass

if not devcon_found:
    print("❌ DevCon no encontrado")
    print("   DevCon es una herramienta de Microsoft para gestionar dispositivos")

print()

# ============================================================================
# RESUMEN Y RECOMENDACIÓN
# ============================================================================
print("=" * 70)
print("📊 RESUMEN Y RECOMENDACIÓN")
print("=" * 70)

print("\n🎯 MEJOR OPCIÓN: Windows Runtime (WinRT)")
print("   • No requiere permisos de administrador")
print("   • API nativa de Windows 10/11")
print("   • Permite cerrar conexiones Bluetooth")
print("   • Comando: pip install winrt")

print("\n⚠️ LIMITACIONES DE WINDOWS:")
print("   • Windows no permite 'desconectar' dispositivos emparejados")
print("   • Solo permite 'cerrar' la conexión actual")
print("   • El dispositivo se reconectará automáticamente si está encendido")
print("   • Para desemparejar, se requiere elevación de permisos")

print("\n💡 SOLUCIÓN PROPUESTA:")
print("   1. Usar WinRT para 'cerrar' la conexión temporalmente")
print("   2. El Joy-Con intentará reconectar automáticamente")
print("   3. Para control real, implementar modo 'app exclusiva':")
print("      - App conecta via BLE directamente (sin emparejar en Windows)")
print("      - App tiene control total")
print("      - Windows no interfiere")

print("\n" + "=" * 70)
