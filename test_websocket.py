"""
🧪 Test Script para WebSocket Notifications
Simula eventos de dispositivos para probar el sistema de notificaciones del overlay.

Uso:
    python test_websocket.py
"""

import asyncio
import json
from datetime import datetime

# Colores para la consola
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


async def test_websocket_connection():
    """Prueba básica de conexión WebSocket"""
    import aiohttp
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}🧪 Test de WebSocket - Gamepad Monitor{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
    
    ws_url = "ws://localhost:8000/api/ws"
    
    print(f"{Colors.BLUE}📡 Conectando a {ws_url}...{Colors.RESET}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                print(f"{Colors.GREEN}✅ Conectado exitosamente!{Colors.RESET}\n")
                
                print(f"{Colors.YELLOW}📨 Esperando mensajes (Ctrl+C para salir)...{Colors.RESET}\n")
                print("-" * 60)
                
                msg_count = 0
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        msg_count += 1
                        data = json.loads(msg.data)
                        msg_type = data.get('type', 'unknown')
                        
                        # Colorear según tipo
                        if msg_type == 'devices_update':
                            devices = data.get('devices', [])
                            alerts = data.get('alerts', [])
                            print(f"{Colors.BLUE}[{msg_count}] 📊 devices_update: {len(devices)} dispositivo(s){Colors.RESET}")
                            
                            for d in devices:
                                battery = d.get('battery', {})
                                pct = battery.get('percentage', '?')
                                charging = battery.get('charging', False)
                                name = d.get('name', 'Unknown')
                                charge_icon = '⚡' if charging else '🔋'
                                print(f"    {charge_icon} {name}: {pct}%")
                            
                            if alerts:
                                print(f"    {Colors.RED}⚠️ {len(alerts)} alerta(s){Colors.RESET}")
                        
                        elif msg_type == 'battery_update':
                            event_data = data.get('data', {})
                            print(f"{Colors.GREEN}[{msg_count}] 🔋 battery_update: {event_data.get('device_id', '?')[:20]}... → {event_data.get('battery')}%{Colors.RESET}")
                        
                        elif msg_type == 'device_disconnected':
                            event_data = data.get('data', {})
                            print(f"{Colors.RED}[{msg_count}] 🔌 device_disconnected: {event_data.get('device_id', '?')[:30]}...{Colors.RESET}")
                        
                        elif msg_type == 'device_reconnected':
                            event_data = data.get('data', {})
                            print(f"{Colors.GREEN}[{msg_count}] 🎮 device_reconnected: {event_data.get('device_id', '?')[:30]}...{Colors.RESET}")
                        
                        elif msg_type == 'charging_change':
                            event_data = data.get('data', {})
                            charging = event_data.get('charging', False)
                            icon = '⚡' if charging else '🔌'
                            status = 'Cargando' if charging else 'No cargando'
                            print(f"{Colors.YELLOW}[{msg_count}] {icon} charging_change: {status} ({event_data.get('battery')}%){Colors.RESET}")
                        
                        else:
                            print(f"{Colors.CYAN}[{msg_count}] 📩 {msg_type}{Colors.RESET}")
                    
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"{Colors.RED}❌ Error: {ws.exception()}{Colors.RESET}")
                        break
                        
    except aiohttp.ClientConnectorError:
        print(f"{Colors.RED}❌ No se pudo conectar. ¿Está el servidor corriendo?{Colors.RESET}")
        print(f"{Colors.YELLOW}   Inicia el servidor con: python api_v2/main.py{Colors.RESET}")
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}👋 Desconectado por el usuario{Colors.RESET}")


async def simulate_events():
    """Simula eventos enviando requests a la API para provocar notificaciones"""
    import aiohttp
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}🎭 Simulador de Eventos - Gamepad Monitor{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
    
    api_base = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        # 1. Obtener dispositivos
        print(f"{Colors.BLUE}📡 Obteniendo dispositivos...{Colors.RESET}")
        try:
            async with session.get(f"{api_base}/api/devices") as resp:
                if resp.status == 200:
                    devices = await resp.json()
                    print(f"{Colors.GREEN}✅ {len(devices)} dispositivo(s) encontrado(s){Colors.RESET}\n")
                    
                    if not devices:
                        print(f"{Colors.YELLOW}⚠️ No hay dispositivos conectados para simular eventos{Colors.RESET}")
                        print(f"{Colors.YELLOW}   Conecta un Joy-Con y vuelve a intentar{Colors.RESET}")
                        return
                    
                    for i, d in enumerate(devices):
                        print(f"  [{i+1}] {d.get('name', 'Unknown')} - {d.get('id', '?')[:30]}...")
                    
                    print()
                    
                    # Menú de opciones
                    while True:
                        print(f"{Colors.BOLD}Opciones:{Colors.RESET}")
                        print("  1. Hacer vibrar dispositivo (prueba conexión)")
                        print("  2. Forzar escaneo de dispositivos")
                        print("  3. Ver estado del scheduler")
                        print("  4. Salir")
                        print()
                        
                        try:
                            choice = input(f"{Colors.CYAN}Selecciona opción (1-4): {Colors.RESET}")
                        except EOFError:
                            break
                        
                        if choice == '1':
                            device_id = devices[0].get('id')
                            print(f"\n{Colors.YELLOW}📳 Vibrando {device_id[:30]}...{Colors.RESET}")
                            async with session.post(
                                f"{api_base}/api/device/{device_id}/vibrate",
                                json={"duration": 0.5, "intensity": 0.5}
                            ) as vib_resp:
                                if vib_resp.status == 200:
                                    print(f"{Colors.GREEN}✅ Vibración enviada!{Colors.RESET}\n")
                                else:
                                    print(f"{Colors.RED}❌ Error: {await vib_resp.text()}{Colors.RESET}\n")
                        
                        elif choice == '2':
                            print(f"\n{Colors.YELLOW}🔍 Escaneando dispositivos...{Colors.RESET}")
                            async with session.post(f"{api_base}/api/scan") as scan_resp:
                                if scan_resp.status == 200:
                                    result = await scan_resp.json()
                                    print(f"{Colors.GREEN}✅ Escaneo completo: {result.get('total_devices')} dispositivo(s){Colors.RESET}\n")
                                else:
                                    print(f"{Colors.RED}❌ Error en escaneo{Colors.RESET}\n")
                        
                        elif choice == '3':
                            print(f"\n{Colors.YELLOW}📊 Estado del scheduler...{Colors.RESET}")
                            async with session.get(f"{api_base}/api/scheduler/status") as status_resp:
                                if status_resp.status == 200:
                                    status = await status_resp.json()
                                    print(f"{Colors.GREEN}Estado: {'Corriendo' if status.get('running') else 'Detenido'}{Colors.RESET}")
                                    stats = status.get('stats', {})
                                    print(f"  Total recolecciones: {stats.get('total_collections', 0)}")
                                    print(f"  Lecturas exitosas: {stats.get('successful_reads', 0)}")
                                    print(f"  Lecturas fallidas: {stats.get('failed_reads', 0)}")
                                    print(f"  Desconexiones: {stats.get('disconnections_detected', 0)}")
                                    print(f"  Reconexiones: {stats.get('reconnections_detected', 0)}")
                                    print()
                                else:
                                    print(f"{Colors.RED}❌ Error obteniendo estado{Colors.RESET}\n")
                        
                        elif choice == '4':
                            print(f"\n{Colors.YELLOW}👋 Saliendo...{Colors.RESET}")
                            break
                        
                        else:
                            print(f"{Colors.RED}Opción no válida{Colors.RESET}\n")
                else:
                    print(f"{Colors.RED}❌ Error: {resp.status}{Colors.RESET}")
                    
        except aiohttp.ClientConnectorError:
            print(f"{Colors.RED}❌ No se pudo conectar. ¿Está el servidor corriendo?{Colors.RESET}")
            print(f"{Colors.YELLOW}   Inicia el servidor con: python api_v2/main.py{Colors.RESET}")


def main():
    print(f"\n{Colors.BOLD}🎮 Gamepad Monitor - Test Suite{Colors.RESET}\n")
    print("Selecciona una opción:")
    print("  1. Monitor WebSocket (ver mensajes en tiempo real)")
    print("  2. Simulador de eventos (interactuar con dispositivos)")
    print("  3. Salir")
    print()
    
    try:
        choice = input(f"{Colors.CYAN}Opción (1-3): {Colors.RESET}")
    except EOFError:
        return
    
    if choice == '1':
        asyncio.run(test_websocket_connection())
    elif choice == '2':
        asyncio.run(simulate_events())
    else:
        print("👋 Saliendo...")


if __name__ == "__main__":
    main()
