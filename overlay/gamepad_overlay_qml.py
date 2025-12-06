"""
🎮 Gamepad Monitor Overlay v3 - QML Edition
Réplica exacta del overlay PyQt6 pero con animaciones fluidas QtQuick/QML
"""

import sys
import os
import subprocess
import asyncio
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty, QUrl, QTimer, QThread
from PyQt6.QtGui import QColor
import requests
import json

# ============ Configuration ============
API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "overlay_config.json")

# Importar clases del v2 (TopColorBar, NotificationToast, sonidos)
sys.path.insert(0, SCRIPT_DIR)
try:
    from gamepad_overlay_v2 import (
        TopColorBar, NotificationToast, SettingsManager,
        BluetoothManagerWindow, DetailedViewWindow, OptionsWindow,
        get_brand_info
    )
    HAS_V2_COMPONENTS = True
except ImportError as e:
    print(f"⚠️ No se pudieron importar componentes v2: {e}")
    HAS_V2_COMPONENTS = False

# Audio para sonidos
try:
    import pygame
    pygame.mixer.init()
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False


# ============ WebSocket Worker (igual que v2) ============
class WebSocketWorker(QThread):
    """Worker que usa WebSocket para recibir actualizaciones en tiempo real"""
    data_received = pyqtSignal(list)
    device_connected = pyqtSignal(dict)
    device_disconnected = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self._reconnect_delay = 1.0
    
    def run(self):
        import aiohttp
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                loop.run_until_complete(self._websocket_loop())
            except Exception as e:
                self.connection_status.emit(False)
            
            if self.running:
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)
        
        loop.close()
    
    async def _websocket_loop(self):
        import aiohttp
        ws_url = f"{WS_BASE}/api/ws"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.ws_connect(ws_url, heartbeat=30) as ws:
                    self.connection_status.emit(True)
                    self._reconnect_delay = 1.0
                    print(f"📡 WebSocket conectado")
                    
                    async for msg in ws:
                        if not self.running:
                            break
                        
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = msg.json()
                                await self._handle_message(data)
                            except:
                                pass
                        elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                            break
            except Exception as e:
                print(f"WebSocket error: {e}")
                self.connection_status.emit(False)
    
    async def _handle_message(self, data: dict):
        msg_type = data.get('type', '')
        
        if msg_type == 'devices_update':
            devices = data.get('devices', [])
            graph_data = data.get('graph_data', {})
            
            for device in devices:
                device_id = device.get('id')
                if device_id and device_id in graph_data:
                    history = graph_data[device_id].get('data_points') or graph_data[device_id].get('history', [])
                    device['graph_points'] = [
                        {'percentage': m.get('battery_level', 0), 'timestamp': m.get('timestamp', '')}
                        for m in history if m.get('battery_level') is not None
                    ]
            
            self.data_received.emit(devices)
        
        elif msg_type == 'device_connected':
            self.device_connected.emit(data.get('data', {}))
        
        elif msg_type == 'device_disconnected':
            device_data = data.get('data', {})
            self.device_disconnected.emit(device_data.get('device_id', ''))
    
    def stop(self):
        self.running = False


class OverlayController(QObject):
    """Controlador Python para el overlay QML"""
    
    # Señales para QML
    devicesChanged = pyqtSignal()
    positionChanged = pyqtSignal()
    lockStateChanged = pyqtSignal()
    connectionChanged = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self._devices = []
        self._device_ids = set()  # Para detectar cambios
        self._isLocked = True
        self._posX = 100
        self._posY = 100
        self._isConnected = False
        
        # Ventanas auxiliares (mantener referencia)
        self._options_window = None
        self._bt_window = None
        self._detail_window = None
        
        # Componentes v2: barra de color y notificaciones
        self._top_color_bar = None
        self._notification_toast = None
        self._settings = None
        if HAS_V2_COMPONENTS:
            self._settings = SettingsManager()
            self._top_color_bar = TopColorBar()
            self._notification_toast = NotificationToast()
        
        # Cargar configuración
        self.load_config()
        
        # Iniciar WebSocket worker
        self.ws_worker = WebSocketWorker()
        self.ws_worker.data_received.connect(self._on_data_received)
        self.ws_worker.device_connected.connect(self._on_device_connected)
        self.ws_worker.device_disconnected.connect(self._on_device_disconnected)
        self.ws_worker.connection_status.connect(self._on_connection_status)
        self.ws_worker.start()
    
    def _on_data_received(self, devices: list):
        """Recibir datos de dispositivos del WebSocket"""
        new_ids = {d.get('id', '') for d in devices}
        
        # Detectar nuevos dispositivos conectados
        for device in devices:
            device_id = device.get('id', '')
            if device_id and device_id not in self._device_ids:
                # Nuevo dispositivo! Disparar animaciones
                self._trigger_connection_effects(device)
        
        # Detectar dispositivos desconectados
        for old_id in self._device_ids:
            if old_id not in new_ids:
                self._trigger_disconnection_effects(old_id)
        
        # Actualizar estado
        self._devices = devices
        self._device_ids = new_ids
        self.devicesChanged.emit()
    
    def _trigger_connection_effects(self, device: dict):
        """Disparar efectos visuales y sonido al conectar"""
        device_id = device.get('id', '')
        device_type = device.get('type', '') or device_id
        device_name = device.get('name', '') or device.get('model', '') or device_type
        
        print(f"🎮 ¡Nuevo dispositivo detectado! {device_name}")
        
        # Obtener color del dispositivo
        device_color = QColor("#0ea5e9")  # Default azul
        colors = device.get('colors', {})
        if colors and colors.get('body') and colors['body'].get('hex'):
            device_color = QColor(colors['body']['hex'])
        elif HAS_V2_COMPONENTS:
            brand_info = get_brand_info(device_type, device_name)
            device_color = QColor(brand_info['colors']['primary'])
        
        # Barra de color arriba
        if self._top_color_bar:
            print(f"   → Triggering color bar animation: {device_color.name()}")
            self._top_color_bar.trigger_animation(device_id, device_color)
        
        # Notificación toast
        if self._notification_toast:
            print(f"   → Showing notification toast")
            
            # Obtener número de jugador si es Joy-Con
            player_num = device.get('player_number')
            notification_title = device_name
            
            if player_num and ('joycon' in device_id.lower() or 'joy-con' in device_name.lower()):
                notification_title = f"{device_name} - Jugador {player_num}"
            
            self._notification_toast.add_notification(
                'device_connected',
                notification_title,
                "Dispositivo conectado",
                device_color,
                "🎮",
                device_id
            )
        
        # Sonido
        self._play_connection_sound(device_type, device_name)
    
    def _trigger_disconnection_effects(self, device_id: str):
        """Disparar efectos al desconectar"""
        print(f"❌ Dispositivo desconectado: {device_id}")
        
        if self._top_color_bar:
            self._top_color_bar.remove_device(device_id)
        
        if self._notification_toast:
            self._notification_toast.add_notification(
                'device_disconnected',
                "Desconectado",
                device_id,
                QColor("#ef4444"),
                "❌",
                device_id
            )
    
    def _on_device_connected(self, data: dict):
        """Evento WebSocket de dispositivo conectado (backup)"""
        pass  # Ya manejado en _on_data_received
    
    def _on_device_disconnected(self, device_id: str):
        """Evento WebSocket de dispositivo desconectado (backup)"""
        pass  # Ya manejado en _on_data_received
    
    def _on_connection_status(self, connected: bool):
        """Estado de conexión WebSocket"""
        self._isConnected = connected
        self.connectionChanged.emit()
        if connected:
            print("✅ Conectado al servidor")
        else:
            print("⚠️ Desconectado del servidor")
    
    def _play_connection_sound(self, device_type: str, model: str = ""):
        """Reproducir sonido de conexión según tipo de dispositivo"""
        if not HAS_AUDIO:
            return
        
        try:
            device_type_lower = (device_type + ' ' + model).lower()
            
            # Rutas de sonidos
            base_path = os.path.dirname(SCRIPT_DIR)
            sounds_paths = [
                os.path.join(base_path, "Icosns"),
                os.path.join(os.path.dirname(base_path), "Icosns"),
                r"c:\Users\teamp\Documents\joys\Icosns",
            ]
            
            sounds_path = None
            for p in sounds_paths:
                if os.path.exists(p):
                    sounds_path = p
                    break
            
            if not sounds_path:
                return
            
            sound_file = None
            pan = 0.0
            
            if 'joy-con' in device_type_lower or 'joycon' in device_type_lower:
                sound_file = os.path.join(sounds_path, "switch-sound.mp3")
                if '_l' in device_type_lower or '(l)' in device_type_lower or 'left' in device_type_lower:
                    pan = -1.0
                elif '_r' in device_type_lower or '(r)' in device_type_lower or 'right' in device_type_lower:
                    pan = 1.0
            elif 'dualsense' in device_type_lower or 'ps5' in device_type_lower:
                sound_file = os.path.join(sounds_path, "ps5-original-trophy.mp3")
            elif 'dualshock' in device_type_lower or 'ds4' in device_type_lower or 'ps4' in device_type_lower:
                sound_file = os.path.join(sounds_path, "ps4-trophy.mp3")
            elif 'playstation' in device_type_lower:
                sound_file = os.path.join(sounds_path, "ps5-original-trophy.mp3")
            
            if sound_file and os.path.exists(sound_file):
                pygame.mixer.stop()
                sound = pygame.mixer.Sound(sound_file)
                channel = sound.play(loops=0)
                if channel and pan != 0.0:
                    left_vol = 1.0 if pan <= 0 else 1.0 - pan
                    right_vol = 1.0 if pan >= 0 else 1.0 + pan
                    channel.set_volume(left_vol, right_vol)
        except Exception as e:
            print(f"Error reproduciendo sonido: {e}")
    
    @pyqtSlot()
    def toggleLock(self):
        """Alternar bloqueo de posición"""
        self._isLocked = not self._isLocked
        self.lockStateChanged.emit()
        self.save_config()
        print(f"🔒 Locked: {self._isLocked}")
    
    @pyqtSlot()
    def openSettings(self):
        """Abrir ventana de opciones"""
        print("🔧 Abriendo configuración...")
        if not HAS_V2_COMPONENTS:
            print("❌ Componentes v2 no disponibles")
            return
        try:
            if self._options_window is None or not self._options_window.isVisible():
                self._options_window = OptionsWindow(self._settings)
            self._options_window.show()
            self._options_window.raise_()
            self._options_window.activateWindow()
        except Exception as e:
            print(f"❌ Error abriendo opciones: {e}")
            import traceback
            traceback.print_exc()
    
    @pyqtSlot()
    def openBluetoothManager(self):
        """Abrir gestor de Bluetooth"""
        print("📡 Abriendo Bluetooth Manager...")
        if not HAS_V2_COMPONENTS:
            subprocess.Popen(["explorer.exe", "ms-settings:bluetooth"])
            return
        try:
            if self._bt_window is None or not self._bt_window.isVisible():
                self._bt_window = BluetoothManagerWindow()
            self._bt_window.show()
            self._bt_window.raise_()
            self._bt_window.activateWindow()
        except Exception as e:
            print(f"❌ Error abriendo Bluetooth Manager: {e}")
            subprocess.Popen(["explorer.exe", "ms-settings:bluetooth"])
    
    @pyqtSlot()
    def openDetailedView(self):
        """Abrir vista detallada HTML"""
        print("📱 Abriendo Vista Detallada...")
        if not HAS_V2_COMPONENTS:
            print("❌ Componentes v2 no disponibles")
            return
        try:
            if self._detail_window is None or not self._detail_window.isVisible():
                self._detail_window = DetailedViewWindow()
            self._detail_window.show()
            self._detail_window.raise_()
            self._detail_window.activateWindow()
            self._detail_window.refresh_devices()
        except Exception as e:
            print(f"❌ Error abriendo Vista Detallada: {e}")
            traceback.print_exc()
    
    @pyqtSlot(int, int)
    def updatePosition(self, x, y):
        """Actualizar posición del overlay"""
        self._posX = x
        self._posY = y
        self.positionChanged.emit()
        self.save_config()
    
    def save_config(self):
        """Guardar configuración"""
        config = {
            "position": {"x": self._posX, "y": self._posY},
            "locked": self._isLocked
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except:
            pass
    
    def load_config(self):
        """Cargar configuración"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    pos = config.get("position", {"x": 100, "y": 100})
                    self._posX = pos.get("x", 100)
                    self._posY = pos.get("y", 100)
                    self._isLocked = config.get("locked", True)
        except:
            pass
    
    def cleanup(self):
        """Limpiar recursos"""
        if self.ws_worker:
            self.ws_worker.stop()
            self.ws_worker.wait(2000)
    
    # Properties para QML
    @pyqtProperty('QVariantList', notify=devicesChanged)
    def devices(self):
        return self._devices
    
    @pyqtProperty(bool, notify=lockStateChanged)
    def isLocked(self):
        return self._isLocked
    
    @pyqtProperty(int, notify=positionChanged)
    def posX(self):
        return self._posX
    
    @pyqtProperty(int, notify=positionChanged)
    def posY(self):
        return self._posY
    
    @pyqtProperty(bool, notify=connectionChanged)
    def isConnected(self):
        return self._isConnected


def main():
    """Punto de entrada principal"""
    
    # Usar renderizado de software para estabilidad
    os.environ['QT_QUICK_BACKEND'] = 'software'
    os.environ['QSG_RENDER_LOOP'] = 'basic'
    
    # Crear aplicación
    app = QApplication(sys.argv)
    app.setApplicationName("Gamepad Monitor")
    app.setOrganizationName("GamepadMonitor")
    app.setStyle("Fusion")
    
    # Crear engine QML
    engine = QQmlApplicationEngine()
    
    # Crear controlador
    controller = OverlayController()
    
    # Exponer controlador a QML
    engine.rootContext().setContextProperty("controller", controller)
    
    # Cargar QML principal
    qml_file = os.path.join(SCRIPT_DIR, "OverlayMain.qml")
    engine.load(QUrl.fromLocalFile(qml_file))
    
    if not engine.rootObjects():
        print("❌ Error cargando QML")
        return -1
    
    print("✅ Overlay QML v3 iniciado")
    print("   WebSocket para actualizaciones en tiempo real")
    print("   Sin parpadeos - solo actualiza cuando hay cambios")
    
    # Cleanup al salir
    app.aboutToQuit.connect(controller.cleanup)
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
