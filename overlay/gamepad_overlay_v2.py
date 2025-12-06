"""
🎮 Gamepad Monitor Overlay v2
Overlay compacto estilo Xbox Game Bar

Requisitos:
    pip install PyQt6 aiohttp keyboard

Atajos globales:
    Ctrl+Shift+G - Mostrar/Ocultar
    Ctrl+Shift+L - Bloquear/Desbloquear para mover
    Ctrl+Shift+O - Abrir panel de opciones
"""

import sys
import asyncio
import time
import os
import json
from typing import Optional, Dict, List
from enum import Enum

# ============ GPU Acceleration Setup ============
# Habilitar aceleración por GPU ANTES de crear QApplication
os.environ['QT_QUICK_BACKEND'] = 'software'  # Evitar conflictos
os.environ['QSG_RENDER_LOOP'] = 'basic'  # Loop de renderizado básico para overlay

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSystemTrayIcon, QMenu, QCheckBox, QComboBox, QPushButton,
    QGroupBox, QFrame, QSpinBox, QScrollArea, QGraphicsDropShadowEffect,
    QDialog, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint, QPointF, QPropertyAnimation, QEasingCurve, QSize, QUrl
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen, QLinearGradient,
    QIcon, QPainterPath, QPixmap, QSurfaceFormat, QImage
)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtSvg import QSvgRenderer

# WebEngine para vista detallada HTML
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    print("⚠️ PyQt6-WebEngine no instalado. Vista detallada no disponible.")

import aiohttp
import subprocess
import requests
import threading

# Windows Bluetooth API
try:
    import asyncio
    from winsdk.windows.devices.bluetooth import BluetoothLEDevice
    from winsdk.windows.devices.enumeration import DeviceInformation, DevicePairingResultStatus
    HAS_WINRT = True
except ImportError:
    HAS_WINRT = False
    print("⚠️ winsdk no instalado. Usa: pip install winsdk")

# Audio para notificaciones de conexión
try:
    import pygame
    pygame.mixer.init()
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False
    print("⚠️ pygame no instalado. Sonidos de conexión no disponibles.")

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False
    print("⚠️ 'keyboard' no instalado. Hotkeys globales deshabilitados.")


# ============ Configuration ============
API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
UPDATE_INTERVAL = 3000  # ms

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_NINTENDO = os.path.join(SCRIPT_DIR, "nintendo.svg")  # SVG para calidad
ICON_PLAYSTATION = os.path.join(SCRIPT_DIR, "ps_icon.svg")  # SVG para calidad
ICON_XBOX = os.path.join(SCRIPT_DIR, "Xbox_one_logo.svg.png")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "overlay_config.json")

# Mapeo de botones del Joy-Con (basado en input report 0x30)
JOYCON_BUTTONS = {
    # Byte 3 (Right Joy-Con)
    'Y': (3, 0x01),
    'X': (3, 0x02),
    'B': (3, 0x04),
    'A': (3, 0x08),
    'SR (R)': (3, 0x10),
    'SL (R)': (3, 0x20),
    'R': (3, 0x40),
    'ZR': (3, 0x80),
    # Byte 4 (Shared)
    'Minus': (4, 0x01),
    'Plus': (4, 0x02),
    'R Stick': (4, 0x04),
    'L Stick': (4, 0x08),
    'Home': (4, 0x10),
    'Capture': (4, 0x20),
    # Byte 5 (Left Joy-Con)
    'Down': (5, 0x01),
    'Up': (5, 0x02),
    'Right': (5, 0x04),
    'Left': (5, 0x08),
    'SR (L)': (5, 0x10),
    'SL (L)': (5, 0x20),
    'L': (5, 0x40),
    'ZL': (5, 0x80),
}


class OverlayPosition(Enum):
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


# ============ Settings Manager ============
class SettingsManager:
    """Gestiona la configuración persistente del overlay"""
    
    DEFAULT_SETTINGS = {
        'show_color_bar': True,
        'show_notifications': True,
        'show_graphs': True,
        'toggle_button': 'Capture',  # Botón para mostrar/ocultar overlay
        'toggle_enabled': False,  # Si está habilitado el toggle por botón
        'position': 'top_right',
    }
    
    def __init__(self):
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.load()
    
    def load(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    saved = json.load(f)
                    self.settings.update(saved)
        except Exception as e:
            print(f"⚠️ Error cargando configuración: {e}")
    
    def save(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error guardando configuración: {e}")
    
    def get(self, key, default=None):
        return self.settings.get(key, default)
    
    def set(self, key, value):
        self.settings[key] = value
        self.save()


# ============ Device Numbering System ============
class DeviceNumberManager:
    """Gestiona la asignación de números a dispositivos (Player 1, 2, etc.)"""
    
    def __init__(self):
        self._device_numbers: Dict[str, int] = {}  # device_id -> número
        self._next_number = 1
        self._type_counters: Dict[str, int] = {}  # tipo -> contador
    
    def get_number(self, device_id: str, device_type: str = "") -> int:
        """Obtener o asignar número a un dispositivo"""
        if device_id in self._device_numbers:
            return self._device_numbers[device_id]
        
        # Asignar nuevo número
        number = self._next_number
        self._device_numbers[device_id] = number
        self._next_number += 1
        return number
    
    def get_type_number(self, device_id: str, device_type: str) -> int:
        """Obtener número específico por tipo (ej: Joy-Con #1, DualSense #2)"""
        # Normalizar tipo
        type_key = self._normalize_type(device_type)
        
        # Si ya tiene número asignado para este dispositivo
        key = f"{type_key}:{device_id}"
        if key in self._device_numbers:
            return self._device_numbers[key]
        
        # Asignar nuevo número para este tipo
        if type_key not in self._type_counters:
            self._type_counters[type_key] = 0
        
        self._type_counters[type_key] += 1
        number = self._type_counters[type_key]
        self._device_numbers[key] = number
        return number
    
    def _normalize_type(self, device_type: str) -> str:
        """Normalizar tipo de dispositivo"""
        dt = device_type.lower()
        if 'joycon' in dt or 'joy-con' in dt:
            if '(l)' in dt or '_l' in dt or 'left' in dt:
                return 'joycon_l'
            elif '(r)' in dt or '_r' in dt or 'right' in dt:
                return 'joycon_r'
            return 'joycon'
        elif 'dualsense' in dt:
            return 'dualsense'
        elif 'dualshock' in dt or 'ds4' in dt:
            return 'dualshock4'
        elif 'xbox' in dt:
            return 'xbox'
        return 'controller'
    
    def remove_device(self, device_id: str):
        """Remover dispositivo (no reasigna números)"""
        # No removemos para mantener consistencia de números
        pass
    
    def clear(self):
        """Limpiar todos los números"""
        self._device_numbers.clear()
        self._type_counters.clear()
        self._next_number = 1


# Instancia global del manager de números
device_number_manager = DeviceNumberManager()


class DeviceNumbering:
    """Clase estática para acceder al sistema de numeración de dispositivos"""
    
    @staticmethod
    def get_clean_name(device_id: str) -> str:
        """Obtener nombre limpio del dispositivo con número (ej: 'DualSense #1')"""
        device_id_lower = device_id.lower()
        
        # Detectar tipo de dispositivo
        if 'joycon_l' in device_id_lower or ('joy-con' in device_id_lower and '(l)' in device_id_lower):
            device_type = 'Joy-Con (L)'
            type_key = 'joycon_l'
        elif 'joycon_r' in device_id_lower or ('joy-con' in device_id_lower and '(r)' in device_id_lower):
            device_type = 'Joy-Con (R)'
            type_key = 'joycon_r'
        elif 'dualsense' in device_id_lower:
            device_type = 'DualSense'
            type_key = 'dualsense'
        elif 'dualshock' in device_id_lower or 'ds4' in device_id_lower:
            device_type = 'DualShock 4'
            type_key = 'dualshock4'
        elif 'xbox' in device_id_lower:
            device_type = 'Xbox Controller'
            type_key = 'xbox'
        else:
            device_type = 'Controlador'
            type_key = 'controller'
        
        # Obtener número del manager
        number = device_number_manager.get_type_number(device_id, type_key)
        
        return f"{device_type} #{number}"
    
    @staticmethod
    def get_device_icon(device_id: str) -> str:
        """Obtener emoji/icono según el tipo de dispositivo"""
        device_id_lower = device_id.lower()
        
        if 'joycon' in device_id_lower or 'joy-con' in device_id_lower:
            if '(l)' in device_id_lower or '_l' in device_id_lower:
                return '🕹️'  # Joy-Con L
            elif '(r)' in device_id_lower or '_r' in device_id_lower:
                return '🎮'  # Joy-Con R
            return '🕹️'
        elif 'dualsense' in device_id_lower:
            return '🎮'  # PlayStation 5
        elif 'dualshock' in device_id_lower or 'ds4' in device_id_lower:
            return '🎮'  # PlayStation 4
        elif 'xbox' in device_id_lower:
            return '🎮'  # Xbox
        else:
            return '🎮'  # Genérico
    
    @staticmethod
    def remove_device(device_id: str):
        """Remover dispositivo del sistema de numeración"""
        device_number_manager.remove_device(device_id)


def get_device_icon(device_type: str, device_id: str = "") -> str:
    """Obtener emoji/icono según el tipo de dispositivo"""
    dt = device_type.lower() if device_type else device_id.lower()
    
    if 'joycon' in dt or 'joy-con' in dt:
        if '(l)' in dt or '_l' in dt or 'left' in dt:
            return '🕹️'  # Joy-Con izquierdo
        elif '(r)' in dt or '_r' in dt or 'right' in dt:
            return '🎮'  # Joy-Con derecho
        return '🎮'
    elif 'dualsense' in dt or 'ps5' in dt:
        return '🎮'  # PlayStation 5
    elif 'dualshock' in dt or 'ds4' in dt or 'ps4' in dt:
        return '🎮'  # PlayStation 4
    elif 'xbox' in dt:
        return '🎮'  # Xbox
    elif 'pro controller' in dt:
        return '🎮'  # Pro Controller
    return '🎮'  # Genérico


def get_clean_device_name(device_id: str, device_type: str = "", include_number: bool = True) -> str:
    """
    Obtener nombre limpio del dispositivo
    Ej: 'dualsense_31170a78' -> 'DualSense #1'
        'joycon_l_3033307d' -> 'Joy-Con (L) #1'
    """
    dt = device_type.lower() if device_type else device_id.lower()
    
    # Determinar tipo base
    if 'joycon_l' in dt or ('joycon' in dt and '(l)' in dt) or ('joy-con' in dt and '(l)' in dt):
        base_name = 'Joy-Con (L)'
        type_key = 'Joy-Con (L)'
    elif 'joycon_r' in dt or ('joycon' in dt and '(r)' in dt) or ('joy-con' in dt and '(r)' in dt):
        base_name = 'Joy-Con (R)'
        type_key = 'Joy-Con (R)'
    elif 'dualsense' in dt:
        base_name = 'DualSense'
        type_key = 'DualSense'
    elif 'dualshock' in dt or 'ds4' in dt:
        base_name = 'DualShock 4'
        type_key = 'DualShock 4'
    elif 'xbox' in dt:
        base_name = 'Xbox Controller'
        type_key = 'Xbox'
    elif 'pro controller' in dt:
        base_name = 'Pro Controller'
        type_key = 'Pro Controller'
    else:
        base_name = 'Controlador'
        type_key = 'Controller'
    
    if include_number:
        number = device_number_manager.get_type_number(device_id, type_key)
        return f"{base_name} #{number}"
    
    return base_name


def get_device_brand_icon_path(device_type: str, device_id: str = "") -> str:
    """Obtener ruta del icono de marca para notificaciones"""
    dt = device_type.lower() if device_type else device_id.lower()
    
    if 'joycon' in dt or 'joy-con' in dt or 'nintendo' in dt:
        return f"{API_BASE}/frontend/icons/nintendo.png"
    elif 'dualsense' in dt or 'dualshock' in dt or 'playstation' in dt or 'ps4' in dt or 'ps5' in dt:
        return f"{API_BASE}/frontend/icons/PlayStation-Logo.wine.png"
    elif 'xbox' in dt:
        return f"{API_BASE}/frontend/icons/Xbox_one_logo.svg.png"
    return ""


# ============ Detailed View Window (HTML Cards) ============
class DetailedViewWindow(QDialog):
    """Ventana con vista detallada HTML de las tarjetas del frontend"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📱 Vista Detallada")
        self.setMinimumSize(450, 600)
        self.resize(450, 700)
        self.devices = []
        self.selected_device_id = None
        
        # Estilo oscuro para la ventana
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
            }
            QComboBox {
                background-color: #1e293b;
                color: white;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                min-width: 200px;
            }
            QComboBox:hover {
                border-color: #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: white;
                selection-background-color: #3b82f6;
                border: 1px solid #334155;
                border-radius: 4px;
            }
            QLabel {
                color: white;
            }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Barra superior compacta
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet("background-color: #1e293b; border-bottom: 1px solid #334155;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(6)
        
        # Selector de dispositivos compacto
        self.device_combo = QComboBox()
        self.device_combo.setFixedHeight(26)
        self.device_combo.setStyleSheet("""
            QComboBox {
                background-color: #334155;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #94a3b8;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: white;
                selection-background-color: #3b82f6;
            }
        """)
        self.device_combo.setPlaceholderText("Dispositivo...")
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)
        header_layout.addWidget(self.device_combo, 1)
        
        # Botón Gestor Bluetooth
        bluetooth_btn = QPushButton("📡")
        bluetooth_btn.setFixedSize(26, 26)
        bluetooth_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        bluetooth_btn.setToolTip("Gestor Bluetooth")
        bluetooth_btn.clicked.connect(lambda: self.window().show_bluetooth_manager() if hasattr(self.window(), 'show_bluetooth_manager') else None)
        header_layout.addWidget(bluetooth_btn)
        
        # Botón refrescar compacto
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(26, 26)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        refresh_btn.setToolTip("Actualizar")
        refresh_btn.clicked.connect(self.refresh_devices)
        header_layout.addWidget(refresh_btn)
        
        layout.addWidget(header)
        
        # WebEngineView para renderizar HTML con aceleración GPU
        if HAS_WEBENGINE:
            self.web_view = QWebEngineView()
            self.web_view.setStyleSheet("background-color: #0f172a;")
            
            # Configurar settings para GPU y rendimiento
            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
            
            # Forzar aceleración por hardware en canvas
            self.web_view.page().profile().settings().setAttribute(
                QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True
            )
            self.web_view.page().profile().settings().setAttribute(
                QWebEngineSettings.WebAttribute.WebGLEnabled, True
            )
            
            # Fondo transparente para el webview
            self.web_view.page().setBackgroundColor(QColor("#0f172a"))
            layout.addWidget(self.web_view)
            
            # Cargar HTML inicial
            self.load_empty_state()
        else:
            error_label = QLabel("❌ PyQt6-WebEngine no instalado\n\npip install PyQt6-WebEngine")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("color: #ef4444; font-size: 16px; padding: 40px;")
            layout.addWidget(error_label)
        
        # Timer para actualización automática (menos frecuente para evitar lag)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refresh_current_device)
        self.update_timer.start(10000)  # Actualizar cada 10 segundos
        
        # Flag para evitar peticiones duplicadas
        self._fetching = False
    
    def load_empty_state(self):
        """Cargar estado vacío"""
        html = self._generate_html(None)
        self.web_view.setHtml(html)
    
    def refresh_devices(self):
        """Refrescar lista de dispositivos desde la API (async)"""
        import threading
        def fetch():
            try:
                response = requests.get(f"{API_BASE}/api/devices", timeout=5)
                if response.status_code == 200:
                    # Usar QTimer para volver al hilo principal
                    self.devices = response.json()
                    QTimer.singleShot(0, self._update_combo_and_select)
            except Exception as e:
                print(f"❌ Error: {e}")
        threading.Thread(target=fetch, daemon=True).start()
    
    def _update_combo_and_select(self):
        """Actualizar combo y auto-seleccionar"""
        self._update_combo()
        if not self.selected_device_id and len(self.devices) > 0:
            self.device_combo.setCurrentIndex(0)
    
    def _on_device_loaded(self, device):
        """Callback cuando se carga un dispositivo"""
        try:
            print(f"📱 Device loaded: {device.get('name', 'Unknown')} - {device.get('id', '')}")
            if HAS_WEBENGINE:
                html = self._generate_html(device)
                print(f"📄 HTML length: {len(html)} chars")
                self.web_view.setHtml(html, QUrl("http://localhost/"))
                print(f"✅ HTML set!")
        except Exception as e:
            print(f"❌ Error in _on_device_loaded: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_combo(self):
        """Actualizar el combo con los dispositivos"""
        current_id = self.selected_device_id
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        
        for device in self.devices:
            device_type = device.get('type', '')
            device_id = device.get('id', '')
            # Usar name, o type, o id como fallback
            device_name = device.get('name') or device_type or device_id or 'Unknown'
            
            # Emoji según tipo
            type_lower = device_type.lower() if device_type else ''
            if 'joy-con' in type_lower or 'joycon' in device_id.lower():
                if '(L)' in device_type or device.get('side') == 'Left' or '_l_' in device_id.lower():
                    emoji = "🔵"
                else:
                    emoji = "🔴"
            elif 'dualshock' in type_lower or 'dualsense' in type_lower or 'ds4' in device_id.lower() or 'ds5' in device_id.lower():
                emoji = "🎮"
            elif 'xbox' in type_lower:
                emoji = "🟢"
            else:
                emoji = "🎮"
            
            self.device_combo.addItem(f"{emoji} {device_name}", device_id)
        
        # Restaurar selección
        if current_id:
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == current_id:
                    self.device_combo.setCurrentIndex(i)
                    break
        
        self.device_combo.blockSignals(False)
    
    def on_device_selected(self, index):
        """Cuando se selecciona un dispositivo"""
        if index >= 0:
            self.selected_device_id = self.device_combo.itemData(index)
            print(f"📱 Selected: {self.selected_device_id}")
            self.refresh_current_device()
    
    def refresh_current_device(self):
        """Actualizar la tarjeta del dispositivo seleccionado (obteniendo info completa)"""
        if not self.selected_device_id or not HAS_WEBENGINE:
            return
        
        # Evitar peticiones duplicadas
        if hasattr(self, '_fetching') and self._fetching:
            return
        self._fetching = True
        
        device_id = self.selected_device_id
        
        import threading
        def fetch_full_device():
            try:
                # Usar /api/device/{id} (singular) para obtener info completa
                url = f"{API_BASE}/api/device/{device_id}"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    device_data = response.json()
                    # Guardar en variable de instancia y llamar desde timer
                    self._pending_device = device_data
                    QTimer.singleShot(0, self._process_pending_device)
                else:
                    self._fetching = False
            except Exception as e:
                self._fetching = False
                print(f"❌ Error fetching device: {e}")
        
        threading.Thread(target=fetch_full_device, daemon=True).start()
    
    def _process_pending_device(self):
        """Procesar el dispositivo pendiente en el hilo principal"""
        self._fetching = False
        if hasattr(self, '_pending_device') and self._pending_device:
            self._on_device_loaded(self._pending_device)
            self._pending_device = None
    
    def _generate_html(self, device):
        """Generar HTML completo con la tarjeta del dispositivo"""
        if not device:
            return self._get_base_html("""
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; color: #64748b;">
                    <div style="font-size: 64px; margin-bottom: 20px;">🎮</div>
                    <div style="font-size: 18px;">Selecciona un dispositivo</div>
                </div>
            """)
        
        return self._get_base_html(self._render_device_card(device))
    
    def _get_base_html(self, content):
        """HTML base con estilos"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        html {{
            scroll-behavior: smooth;
        }}
        body {{
            background: #0f172a;
            min-height: 100vh;
            padding: 16px;
            color: white;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
        }}
        
        /* Optimización GPU para scroll */
        .device-card {{
            border-radius: 16px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            transform: translateZ(0);
            will-change: transform;
            backface-visibility: hidden;
            transition: transform 0.3s ease;
        }}
        
        .accent-bar {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
        }}
        
        .glossy {{
            position: absolute;
            inset: 0;
            pointer-events: none;
            background: linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.05) 40%, transparent 60%);
            border-radius: inherit;
        }}
        
        .header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            margin-bottom: 24px;
        }}
        
        .device-icon {{
            width: 56px;
            height: 56px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
        }}
        
        .device-icon img {{
            width: 32px;
            height: 32px;
            object-fit: contain;
        }}
        
        .device-info {{
            margin-left: 16px;
        }}
        
        .device-name {{
            font-size: 20px;
            font-weight: 700;
            color: white;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }}
        
        .device-id {{
            font-size: 12px;
            color: rgba(255,255,255,0.6);
            margin-top: 2px;
        }}
        
        .battery-ring {{
            position: relative;
            width: 64px;
            height: 64px;
        }}
        
        .battery-ring svg {{
            transform: rotate(-90deg);
        }}
        
        .battery-text {{
            position: absolute;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
            color: white;
        }}
        
        .charging-icon {{
            position: absolute;
            top: -4px;
            right: -4px;
            font-size: 16px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }}
        
        .stat-card {{
            background: rgba(0,0,0,0.25);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 12px;
        }}
        
        .stat-label {{
            font-size: 11px;
            color: rgba(255,255,255,0.5);
            margin-bottom: 4px;
        }}
        
        .stat-value {{
            font-size: 18px;
            font-weight: 600;
        }}
        
        .stat-value.yellow {{ color: #fde047; }}
        .stat-value.green {{ color: #86efac; }}
        .stat-value.cyan {{ color: #67e8f9; }}
        .stat-value.orange {{ color: #fdba74; }}
        .stat-value.purple {{ color: #c4b5fd; }}
        .stat-value.red {{ color: #fca5a5; }}
        
        .smart-battery {{
            background: rgba(0,0,0,0.2);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 16px;
        }}
        
        .smart-battery-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 12px;
            padding: 4px 0;
        }}
        
        .smart-battery-label {{
            color: rgba(255,255,255,0.5);
        }}
        
        .status-badge {{
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        
        .intelligence-panel {{
            background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(59,130,246,0.1));
            border: 1px solid rgba(139,92,246,0.3);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        }}
        
        .intelligence-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 12px;
        }}
        
        .intelligence-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            font-size: 12px;
        }}
        
        .intelligence-item {{
            display: flex;
            flex-direction: column;
        }}
        
        .intelligence-label {{
            color: rgba(255,255,255,0.5);
            font-size: 11px;
        }}
        
        .intelligence-value {{
            font-size: 14px;
            font-weight: 600;
        }}
        
        .connection-badge {{
            position: absolute;
            top: 12px;
            right: 12px;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.6; }}
        }}
        
        .charging-pulse {{
            animation: pulse 1.5s ease-in-out infinite;
        }}
        
        .chart-container {{
            background: rgba(0,0,0,0.25);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 16px;
            margin-top: 16px;
        }}
        
        .chart-title {{
            font-size: 12px;
            font-weight: 600;
            color: rgba(255,255,255,0.7);
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
    </style>
</head>
<body>
    {content}
</body>
</html>
"""
    
    def _render_device_card(self, device):
        """Renderizar tarjeta de dispositivo"""
        device_type = device.get('type', '').lower()
        device_name = device.get('name', 'Unknown')
        device_id = device.get('id', '')
        
        # Determinar tipo
        is_joycon = 'joy-con' in device_type
        is_ds4 = 'dualshock' in device_type
        is_dualsense = 'dualsense' in device_type
        is_playstation = is_ds4 or is_dualsense
        is_xbox = 'xbox' in device_type
        
        # Colores
        if is_playstation:
            body_color = '#1a1a2e'
            button_color = '#0066cc'
        elif is_xbox:
            body_color = '#107C10'
            button_color = '#0E6B0E'
        else:
            colors = device.get('colors', {})
            body_color = colors.get('body', {}).get('hex', '#0ea5e9')
            button_color = colors.get('buttons', {}).get('hex', '#0284c7')
        
        # Convertir hex a rgb
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        rgb = hex_to_rgb(body_color)
        rgb_btn = hex_to_rgb(button_color)
        
        # Batería (con manejo de None)
        battery_data = device.get('battery') or {}
        battery = battery_data.get('percentage') or 0
        charging = battery_data.get('charging') or False
        voltage = battery_data.get('voltage') or 0
        
        # Color batería
        if battery >= 75:
            battery_color = '#10b981'
        elif battery >= 25:
            battery_color = '#fbbf24'
        else:
            battery_color = '#ef4444'
        
        # Polling (con manejo de None)
        polling_data = device.get('polling') or {}
        polling_rate = polling_data.get('rate_hz') or 0
        
        # Conexión
        connection_type = device.get('connection_type', '')
        
        # Iconos PNG desde el servidor
        nintendo_icon = f'{API_BASE}/frontend/icons/nintendo.png'
        playstation_icon = f'{API_BASE}/frontend/icons/PlayStation-Logo.wine.png'
        xbox_icon = f'{API_BASE}/frontend/icons/Xbox_one_logo.svg.png'
        
        # Icono según tipo (32px)
        if is_joycon:
            device_icon = f'<img src="{nintendo_icon}" alt="Nintendo" style="width: 32px; height: 32px; object-fit: contain; filter: brightness(0) invert(1);">'
        elif is_playstation:
            device_icon = f'<img src="{playstation_icon}" alt="PlayStation" style="width: 32px; height: 32px; object-fit: contain;">'
        elif is_xbox:
            device_icon = f'<img src="{xbox_icon}" alt="Xbox" style="width: 32px; height: 32px; object-fit: contain;">'
        else:
            device_icon = "🎮"
        
        # Botones para Joy-Cons (Desconectar, Vibrar, Desemparejar)
        action_buttons = ""
        if is_joycon:
            action_buttons = f'''
                <div style="display: flex; gap: 8px; margin-top: 16px;">
                    <button onclick="vibrateDevice('{device_id}')" style="
                        flex: 1;
                        background: linear-gradient(135deg, #8b5cf6, #7c3aed);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 10px 12px;
                        font-size: 12px;
                        font-weight: 600;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 6px;
                        transition: all 0.2s ease;
                        box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3);
                    " onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
                        📳 Vibrar
                    </button>
                    <button onclick="disconnectDevice('{device_id}')" style="
                        flex: 1;
                        background: linear-gradient(135deg, #f97316, #ea580c);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 10px 12px;
                        font-size: 12px;
                        font-weight: 600;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 6px;
                        transition: all 0.2s ease;
                        box-shadow: 0 2px 8px rgba(249, 115, 22, 0.3);
                    " onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
                        🔌 Desconectar
                    </button>
                </div>
                <div style="margin-top: 8px;">
                    <button onclick="unpairDevice('{device_id}')" style="
                        width: 100%;
                        background: linear-gradient(135deg, #dc2626, #b91c1c);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 10px 16px;
                        font-size: 12px;
                        font-weight: 600;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 6px;
                        transition: all 0.2s ease;
                        box-shadow: 0 2px 8px rgba(220, 38, 38, 0.3);
                    " onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
                        🗑️ Desemparejar
                    </button>
                </div>
            '''
        
        # Connection badge
        connection_badge = ""
        if is_playstation and connection_type:
            if connection_type == 'USB':
                connection_badge = f'''
                    <div class="connection-badge" style="background: rgba(34,197,94,0.3); border: 1px solid rgba(34,197,94,0.5); color: #22c55e;">
                        🔌 USB
                    </div>
                '''
            else:
                connection_badge = f'''
                    <div class="connection-badge" style="background: rgba(59,130,246,0.3); border: 1px solid rgba(59,130,246,0.5); color: #3b82f6;">
                        📶 BT
                    </div>
                '''
        
        # Stats
        usage_hours = device.get('usage_time_hours', 0) or 0
        usage_minutes = device.get('usage_time_minutes', 0) or 0
        autonomy = device.get('estimated_autonomy_hours', 0) or 0
        battery_consumed = device.get('battery_consumed', 0) or 0
        
        # Smart battery (con manejo de None)
        smart_battery = device.get('smart_battery') or {}
        # Intelligence está dentro de smart_battery
        battery_intelligence = smart_battery.get('intelligence') or {}
        
        # Construir stats HTML
        stats_html = ""
        
        if voltage and voltage > 0:
            stats_html += f'''
                <div class="stat-card">
                    <div class="stat-label">Voltaje</div>
                    <div class="stat-value yellow">{voltage:.2f}V</div>
                </div>
            '''
        
        if polling_rate and polling_rate > 0:
            stats_html += f'''
                <div class="stat-card">
                    <div class="stat-label">Polling Rate</div>
                    <div class="stat-value green">{polling_rate:.1f} Hz</div>
                </div>
            '''
        
        if usage_hours > 0 or usage_minutes > 0:
            time_str = f"{usage_hours:.1f}h" if usage_hours >= 1 else f"{int(usage_minutes)}min"
            stats_html += f'''
                <div class="stat-card">
                    <div class="stat-label">Tiempo de uso</div>
                    <div class="stat-value cyan">{time_str}</div>
                </div>
            '''
        
        if autonomy > 0:
            stats_html += f'''
                <div class="stat-card">
                    <div class="stat-label">Autonomía</div>
                    <div class="stat-value green">{autonomy:.1f}h</div>
                </div>
            '''
        
        # Salud de batería
        health_html = ""
        if smart_battery and smart_battery.get('health_reliable'):
            health = smart_battery.get('battery_health', 0)
            health_color = '#10b981' if health >= 80 else '#fbbf24' if health >= 50 else '#ef4444'
            health_html = f'<div class="stat-value" style="color: {health_color}">{health:.0f}%</div>'
        else:
            samples = smart_battery.get('health_samples', 0) if smart_battery else 0
            health_html = f'''
                <div class="stat-value" style="color: rgba(255,255,255,0.4)">--</div>
                <div style="font-size: 10px; color: rgba(255,255,255,0.4); margin-top: 2px;">
                    {'📊 ' + str(samples) + '/3 muestras' if samples > 0 else '⏳ Recopilando...'}
                </div>
            '''
        
        stats_html += f'''
            <div class="stat-card">
                <div class="stat-label">❤️ Salud Batería</div>
                {health_html}
            </div>
        '''
        
        # Smart battery panel
        smart_battery_html = ""
        if smart_battery:
            status = smart_battery.get('status', '')
            drain_rate = smart_battery.get('drain_rate_per_hour', 0)
            est_minutes = smart_battery.get('estimated_minutes_remaining', 0)
            
            status_colors = {
                'Critical': ('rgba(239,68,68,0.3)', '#fca5a5'),
                'Low': ('rgba(251,191,36,0.3)', '#fde047'),
                'Full': ('rgba(16,185,129,0.3)', '#6ee7b7'),
            }
            bg, color = status_colors.get(status, ('rgba(59,130,246,0.3)', '#93c5fd'))
            
            smart_battery_html = f'''
                <div class="smart-battery">
                    <div class="smart-battery-row">
                        <span class="smart-battery-label">Estado</span>
                        <span class="status-badge" style="background: {bg}; color: {color};">{status}</span>
                    </div>
            '''
            if drain_rate > 0:
                smart_battery_html += f'''
                    <div class="smart-battery-row">
                        <span class="smart-battery-label">Descarga</span>
                        <span style="color: #fdba74;">{drain_rate:.1f}%/h</span>
                    </div>
                '''
            if est_minutes > 0:
                hours = int(est_minutes // 60)
                mins = int(est_minutes % 60)
                smart_battery_html += f'''
                    <div class="smart-battery-row">
                        <span class="smart-battery-label">Tiempo restante</span>
                        <span style="color: #67e8f9;">{hours}h {mins}m</span>
                    </div>
                '''
            smart_battery_html += '</div>'
        
        # Battery Intelligence panel
        intelligence_html = ""
        if battery_intelligence:
            soc = battery_intelligence.get('soc_precise', 0)
            cycles = battery_intelligence.get('equivalent_cycles', 0)
            soh = battery_intelligence.get('soh_percent')
            health_status = battery_intelligence.get('health_status', '')
            confidence = battery_intelligence.get('confidence', '')
            data_points = battery_intelligence.get('data_points', 0)
            
            has_voltage = battery_intelligence.get('has_voltage_data', False)
            voltage_badge = '<span style="background: rgba(16,185,129,0.2); color: #6ee7b7; padding: 2px 6px; border-radius: 4px; font-size: 10px;">⚡ Voltaje</span>' if has_voltage else '<span style="background: rgba(59,130,246,0.2); color: #93c5fd; padding: 2px 6px; border-radius: 4px; font-size: 10px;">📊 Estimado</span>'
            
            soh_color = '#10b981' if soh and soh >= 80 else '#fbbf24' if soh and soh >= 50 else '#ef4444' if soh else 'rgba(255,255,255,0.4)'
            soh_text = f"{soh:.0f}%" if soh else '--'
            
            status_colors = {
                'excellent': '#10b981', 'Excelente': '#10b981',
                'good': '#22c55e', 'Buena': '#22c55e',
                'fair': '#fbbf24', 'Aceptable': '#fbbf24',
                'poor': '#f97316', 'Degradada': '#f97316',
                'critical': '#ef4444', 'Crítica': '#ef4444',
            }
            status_color = status_colors.get(health_status, 'rgba(255,255,255,0.5)')
            
            intelligence_html = f'''
                <div class="intelligence-panel">
                    <div class="intelligence-header">
                        <span style="font-size: 14px;">🧠</span>
                        <span style="font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.8);">Battery Intelligence</span>
                        <span style="margin-left: auto;">{voltage_badge}</span>
                    </div>
                    <div class="intelligence-grid">
                        <div class="intelligence-item">
                            <span class="intelligence-label">SOC Preciso</span>
                            <span class="intelligence-value" style="color: #c4b5fd;">{soc:.1f}%</span>
                        </div>
                        <div class="intelligence-item">
                            <span class="intelligence-label">Ciclos</span>
                            <span class="intelligence-value" style="color: #67e8f9;">{cycles:.1f}</span>
                        </div>
                        <div class="intelligence-item">
                            <span class="intelligence-label">SoH</span>
                            <span class="intelligence-value" style="color: {soh_color};">{soh_text}</span>
                        </div>
                        <div class="intelligence-item">
                            <span class="intelligence-label">Estado</span>
                            <span class="intelligence-value" style="color: {status_color};">{health_status or '--'}</span>
                        </div>
                    </div>
                    <div style="margin-top: 12px; display: flex; justify-content: space-between; font-size: 10px; color: rgba(255,255,255,0.4);">
                        <span>Confianza: {confidence or 'baja'}</span>
                        <span>📊 {data_points} muestras</span>
                    </div>
                </div>
            '''
        
        # Charging icon
        charging_icon = '<div class="charging-icon charging-pulse">⚡</div>' if charging else ''
        
        # Arc calculation
        arc_offset = 163.4 - (163.4 * battery / 100)
        
        # Datos del historial para la gráfica (usar cache si existe)
        chart_data_json = '{"labels": ["Actual"], "values": [' + str(battery) + ']}'
        if hasattr(self, '_history_cache') and device_id in self._history_cache:
            chart_data_json = self._history_cache[device_id]
        else:
            # Cargar historial en background para la próxima vez
            self._load_history_async(device_id, battery)
        
        return f'''
            <div class="device-card" style="
                background: linear-gradient(135deg, 
                    rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.4) 0%,
                    rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.2) 50%,
                    rgba({rgb_btn[0]}, {rgb_btn[1]}, {rgb_btn[2]}, 0.15) 100%);
                border: 1px solid rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.3);
                box-shadow: 0 8px 32px rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.2);
            ">
                {connection_badge}
                <div class="glossy"></div>
                <div class="accent-bar" style="background: linear-gradient(90deg, {body_color}, {button_color}); box-shadow: 0 0 20px rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.5);"></div>
                
                <div style="position: relative;">
                    <!-- Header -->
                    <div class="header">
                        <div style="display: flex; align-items: center;">
                            <div class="device-icon" style="background: linear-gradient(135deg, {button_color}ee, {button_color}99); border: 1px solid rgba(255,255,255,0.2); box-shadow: 0 4px 15px rgba({rgb_btn[0]}, {rgb_btn[1]}, {rgb_btn[2]}, 0.4);">
                                {device_icon}
                            </div>
                            <div class="device-info">
                                <div class="device-name">{device_name}</div>
                                <div class="device-id">{device.get('serial', device_id)}</div>
                            </div>
                        </div>
                        
                        <!-- Battery Ring -->
                        <div class="battery-ring">
                            <svg width="64" height="64">
                                <circle cx="32" cy="32" r="26" stroke="rgba(255,255,255,0.15)" stroke-width="6" fill="none"/>
                                <circle cx="32" cy="32" r="26" stroke="{battery_color}" stroke-width="6" fill="none" stroke-linecap="round"
                                        stroke-dasharray="163.4" stroke-dashoffset="{arc_offset}"
                                        style="filter: drop-shadow(0 0 6px {battery_color});"/>
                            </svg>
                            <div class="battery-text">{battery}%</div>
                            {charging_icon}
                        </div>
                    </div>
                    
                    <!-- Stats Grid -->
                    <div class="stats-grid">
                        {stats_html}
                    </div>
                    
                    <!-- Smart Battery -->
                    {smart_battery_html}
                    
                    <!-- Battery Intelligence -->
                    {intelligence_html}
                    
                    <!-- Battery History Chart -->
                    <div class="chart-container">
                        <div class="chart-title">📊 Historial de Batería</div>
                        <div style="position: relative; height: 180px;">
                            <canvas id="batteryChart"></canvas>
                        </div>
                    </div>
                    
                    <!-- Action Buttons (Joy-Con: Vibrar, Desconectar, Desemparejar) -->
                    {action_buttons}
                </div>
            </div>
            
            <script>
                const API_BASE = 'http://localhost:8000';
                
                // Función para vibrar dispositivo
                async function vibrateDevice(deviceId) {{
                    const btn = event.target;
                    const originalText = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '⏳ Vibrando...';
                    
                    try {{
                        const response = await fetch(`${{API_BASE}}/api/device/${{deviceId}}/vibrate`, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ duration: 1.0, intensity: 0.7 }})
                        }});
                        
                        if (response.ok) {{
                            btn.innerHTML = '✅ Vibró';
                            setTimeout(() => {{
                                btn.innerHTML = originalText;
                                btn.disabled = false;
                            }}, 1500);
                        }} else {{
                            throw new Error('Error al vibrar');
                        }}
                    }} catch (e) {{
                        btn.innerHTML = '❌ Error';
                        setTimeout(() => {{
                            btn.innerHTML = originalText;
                            btn.disabled = false;
                        }}, 1500);
                    }}
                }}
                
                // Función para desconectar dispositivo
                async function disconnectDevice(deviceId) {{
                    const btn = event.target;
                    const originalBg = btn.style.background;
                    btn.disabled = true;
                    btn.innerHTML = '⏳ Desconectando...';
                    
                    try {{
                        const response = await fetch(`${{API_BASE}}/api/device/${{deviceId}}/disconnect`, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }}
                        }});
                        
                        if (response.ok) {{
                            btn.innerHTML = '✅ Desconectado';
                            btn.style.background = 'linear-gradient(135deg, #22c55e, #16a34a)';
                            setTimeout(() => {{
                                btn.innerHTML = '🔌 Desconectar';
                                btn.style.background = originalBg;
                                btn.disabled = false;
                            }}, 2000);
                        }} else {{
                            throw new Error('Error al desconectar');
                        }}
                    }} catch (e) {{
                        btn.innerHTML = '❌ Error';
                        setTimeout(() => {{
                            btn.innerHTML = '🔌 Desconectar';
                            btn.style.background = originalBg;
                            btn.disabled = false;
                        }}, 2000);
                    }}
                }}
                
                // Función para desemparejar dispositivo
                async function unpairDevice(deviceId) {{
                    if (!confirm('¿Deseas desemparejar este dispositivo? Tendrás que volver a emparejarlo.')) {{
                        return;
                    }}
                    
                    const btn = event.target;
                    const originalBg = btn.style.background;
                    btn.disabled = true;
                    btn.innerHTML = '⏳ Desemparejando...';
                    
                    try {{
                        const response = await fetch(`${{API_BASE}}/api/device/${{deviceId}}/unpair`, {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }}
                        }});
                        
                        if (response.ok) {{
                            btn.innerHTML = '✅ Desemparejado';
                            btn.style.background = 'linear-gradient(135deg, #22c55e, #16a34a)';
                            // No restaurar, el dispositivo desaparecerá
                        }} else {{
                            throw new Error('Error al desemparejar');
                        }}
                    }} catch (e) {{
                        btn.innerHTML = '❌ Error';
                        setTimeout(() => {{
                            btn.innerHTML = '🗑️ Desemparejar';
                            btn.style.background = originalBg;
                            btn.disabled = false;
                        }}, 2000);
                    }}
                }}
                
                // Inicializar gráfica cuando el DOM esté listo
                document.addEventListener('DOMContentLoaded', function() {{
                    initChart();
                }});
                // También intentar inmediatamente por si el DOM ya está listo
                if (document.readyState === 'complete') {{
                    initChart();
                }}
                
                function initChart() {{
                    const canvas = document.getElementById('batteryChart');
                    if (!canvas) return;
                    
                    const ctx = canvas.getContext('2d');
                    
                    // Datos del historial (se llenarán con datos reales)
                    const historyData = {chart_data_json};
                    
                    new Chart(ctx, {{
                        type: 'line',
                        data: {{
                            labels: historyData.labels,
                            datasets: [{{
                                label: 'Batería (%)',
                                data: historyData.values,
                                borderColor: '#10b981',
                                backgroundColor: 'rgba(16, 185, 129, 0.15)',
                                borderWidth: 2,
                                pointRadius: 2,
                                pointHoverRadius: 5,
                                pointBackgroundColor: '#10b981',
                                tension: 0.3,
                                fill: true
                            }}]
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            interaction: {{
                                mode: 'index',
                                intersect: false
                            }},
                            scales: {{
                                y: {{
                                    beginAtZero: true,
                                    max: 100,
                                    ticks: {{
                                        color: 'rgba(255,255,255,0.5)',
                                        callback: function(value) {{
                                            return value + '%';
                                        }}
                                    }},
                                    grid: {{ color: 'rgba(255,255,255,0.1)' }}
                                }},
                                x: {{
                                    ticks: {{
                                        color: 'rgba(255,255,255,0.5)',
                                        maxRotation: 45,
                                        minRotation: 45
                                    }},
                                    grid: {{ color: 'rgba(255,255,255,0.1)' }}
                                }}
                            }},
                            plugins: {{
                                legend: {{ display: false }},
                                tooltip: {{
                                    backgroundColor: 'rgba(17, 24, 39, 0.95)',
                                    titleColor: '#fff',
                                    bodyColor: '#fff',
                                    borderColor: '#374151',
                                    borderWidth: 1,
                                    callbacks: {{
                                        label: function(context) {{
                                            return '🔋 ' + context.parsed.y + '%';
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }});
                }}
            </script>
        '''
    
    def showEvent(self, event):
        """Al mostrar la ventana, refrescar dispositivos"""
        super().showEvent(event)
        self.refresh_devices()
    
    def _load_history_async(self, device_id, current_battery):
        """Cargar historial en background y cachear"""
        import threading
        import json
        
        def fetch_history():
            try:
                response = requests.get(f"{API_BASE}/api/device/{device_id}/history?limit=30", timeout=3)
                if response.status_code == 200:
                    history_data = response.json()
                    metrics = history_data.get('metrics', [])
                    if metrics:
                        sorted_data = sorted(metrics, key=lambda x: x.get('timestamp', ''))
                        labels = []
                        values = []
                        for m in sorted_data:
                            ts = m.get('timestamp', '')
                            if ts:
                                try:
                                    from datetime import datetime
                                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                    labels.append(dt.strftime('%H:%M'))
                                except:
                                    labels.append('')
                            values.append(m.get('battery_level', 0))
                        
                        if not hasattr(self, '_history_cache'):
                            self._history_cache = {}
                        self._history_cache[device_id] = json.dumps({'labels': labels, 'values': values})
            except:
                pass
        
        threading.Thread(target=fetch_history, daemon=True).start()


# ============ WebSocket Data Worker Thread ============
class WebSocketDataWorker(QThread):
    """Worker que usa WebSocket para recibir actualizaciones de dispositivos en tiempo real"""
    data_received = pyqtSignal(list)
    device_connected = pyqtSignal(dict)
    device_disconnected = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 30.0
    
    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                loop.run_until_complete(self._websocket_loop())
            except Exception as e:
                self.error_occurred.emit(str(e))
                self.connection_status.emit(False)
            
            if self.running:
                # Esperar antes de reconectar
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
        
        loop.close()
    
    async def _websocket_loop(self):
        """Conexión WebSocket principal"""
        import aiohttp
        
        ws_url = API_BASE.replace('http://', 'ws://').replace('https://', 'wss://') + '/api/ws'
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.ws_connect(ws_url, heartbeat=30) as ws:
                    self.connection_status.emit(True)
                    self._reconnect_delay = 1.0  # Reset delay on successful connection
                    print(f"📡 WebSocket conectado: {ws_url}")
                    
                    async for msg in ws:
                        if not self.running:
                            break
                        
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = msg.json()
                                await self._handle_message(data)
                            except Exception as e:
                                print(f"Error procesando mensaje WS: {e}")
                        
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            print(f"WebSocket error: {ws.exception()}")
                            break
                        
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            print("WebSocket cerrado por servidor")
                            break
            
            except aiohttp.ClientError as e:
                print(f"Error conectando WebSocket: {e}")
                self.connection_status.emit(False)
    
    async def _handle_message(self, data: dict):
        """Procesar mensaje del WebSocket"""
        msg_type = data.get('type', '')
        
        if msg_type == 'devices_update':
            # Actualización periódica de todos los dispositivos
            devices = data.get('devices', [])
            
            # Añadir graph_data si viene en el mensaje (siempre viene ahora)
            graph_data = data.get('graph_data', {})
            for device in devices:
                device_id = device.get('id')
                if device_id and device_id in graph_data:
                    # Soportar ambos nombres: data_points (nuevo) o history (antiguo)
                    history = graph_data[device_id].get('data_points') or graph_data[device_id].get('history', [])
                    # Mantener estructura completa con timestamps
                    device['graph_points'] = [
                        {
                            'percentage': m.get('battery_level', 0),
                            'timestamp': m.get('timestamp', '')
                        } 
                        for m in history if m.get('battery_level') is not None
                    ]
                    # También agregar drain_rate y drain_analysis
                    device['drain_rate'] = graph_data[device_id].get('drain_rate')
                    device['drain_analysis'] = graph_data[device_id].get('drain_analysis')
                
                # Los datos de uso ya vienen en device desde el servidor
                # (usage_time_hours, usage_time_minutes, battery_consumed, estimated_autonomy_hours)
                # No necesitamos sobrescribirlos
            
            self.data_received.emit(devices)
        
        elif msg_type == 'device_connected':
            # Nuevo dispositivo conectado - notificar inmediatamente
            device_data = data.get('data', {})
            print(f"🎮 Dispositivo conectado: {device_data.get('device_id')}")
            self.device_connected.emit(device_data)
        
        elif msg_type == 'device_disconnected':
            # Dispositivo desconectado
            device_data = data.get('data', {})
            device_id = device_data.get('device_id', '')
            print(f"❌ Dispositivo desconectado: {device_id}")
            self.device_disconnected.emit(device_id)
        
        elif msg_type == 'battery_update':
            # Actualización de batería individual (ya viene en devices_update)
            pass
        
        elif msg_type == 'charging_change':
            # Cambio de estado de carga
            pass
    
    def stop(self):
        self.running = False


# ============ Fallback API Worker Thread (HTTP) ============
class APIWorker(QThread):
    """Worker HTTP de fallback cuando WebSocket no está disponible"""
    data_received = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = True
    
    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                devices = loop.run_until_complete(self.fetch_devices())
                self.data_received.emit(devices)
            except Exception as e:
                self.error_occurred.emit(str(e))
            
            self.msleep(UPDATE_INTERVAL)
        
        loop.close()
    
    async def fetch_devices(self) -> list:
        devices = []
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/api/devices", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    device_list = await resp.json()
                    for device in device_list:
                        device_id = device.get('id')
                        if device_id:
                            try:
                                # Obtener detalles del dispositivo (incluye usage_time, autonomy, etc.)
                                async with session.get(f"{API_BASE}/api/device/{device_id}") as detail_resp:
                                    if detail_resp.status == 200:
                                        info = await detail_resp.json()
                                        
                                        # Obtener historial para la gráfica (igual que el frontend)
                                        try:
                                            async with session.get(f"{API_BASE}/api/device/{device_id}/history?limit=50") as history_resp:
                                                if history_resp.status == 200:
                                                    history_data = await history_resp.json()
                                                    metrics = history_data.get('metrics', [])
                                                    # Convertir a puntos de gráfica (battery_level)
                                                    info['graph_points'] = [
                                                        {'percentage': m.get('battery_level', 0)} 
                                                        for m in metrics if m.get('battery_level') is not None
                                                    ]
                                        except:
                                            info['graph_points'] = []
                                        
                                        devices.append(info)
                            except:
                                pass
        return devices
    
    def stop(self):
        self.running = False


# ============ Battery History (from API) ============
class BatteryHistory:
    def __init__(self, max_points: int = 100):
        self.max_points = max_points
        self.data: Dict[str, List[dict]] = {}  # {device_id: [{percentage, timestamp}, ...]}
    
    def set_points(self, device_id: str, points: List[dict]):
        """Establecer puntos desde la API (lista de {timestamp, battery_level})"""
        if points:
            # Guardar porcentaje y timestamp, limitado a max_points
            formatted = []
            for p in points[-self.max_points:]:
                percentage = p.get('battery_level', p.get('percentage', 0))
                timestamp = p.get('timestamp', '')
                formatted.append({'percentage': percentage, 'timestamp': timestamp})
            self.data[device_id] = formatted
    
    def add_point(self, device_id: str, battery: int):
        """Agregar punto local (fallback)"""
        from datetime import datetime
        if device_id not in self.data:
            self.data[device_id] = []
        self.data[device_id].append({
            'percentage': battery,
            'timestamp': datetime.now().isoformat()
        })
        if len(self.data[device_id]) > self.max_points:
            self.data[device_id] = self.data[device_id][-self.max_points:]
    
    def get_points(self, device_id: str) -> List[dict]:
        """Obtener puntos con porcentaje y timestamp"""
        return self.data.get(device_id, [])


# ============ Helper Functions ============
def get_brand_info(device_type: str, device_name: str) -> dict:
    device_type_lower = device_type.lower() if device_type else ''
    device_name_lower = device_name.lower() if device_name else ''
    
    if 'joy-con' in device_name_lower or 'joycon' in device_type_lower or 'switch' in device_type_lower:
        return {'brand': 'nintendo', 'icon_path': ICON_NINTENDO, 
                'colors': {'primary': '#E60012', 'secondary': '#C8102E'}}
    elif 'dualsense' in device_type_lower or 'dualshock' in device_type_lower or 'ds4' in device_type_lower:
        return {'brand': 'playstation', 'icon_path': ICON_PLAYSTATION,
                'colors': {'primary': '#1a1a2e', 'secondary': '#0f3460'}}
    elif 'xbox' in device_type_lower or 'xbox' in device_name_lower:
        return {'brand': 'xbox', 'icon_path': ICON_XBOX,
                'colors': {'primary': '#107C10', 'secondary': '#0E6B0E'}}
    else:
        return {'brand': 'generic', 'icon_path': None,
                'colors': {'primary': '#6B7280', 'secondary': '#4B5563'}}


# ============ Device Widget ============
class DeviceWidget(QWidget):
    def __init__(self, battery_history: BatteryHistory, parent=None):
        super().__init__(parent)
        self.device_data: Optional[Dict] = None
        self.battery_history = battery_history
        self.body_color = QColor("#0ea5e9")
        self.button_color = QColor("#0284c7")
        self.brand_icon: Optional[QPixmap] = None
        self.brand_info = None
        self.show_graph = True
        self.setFixedSize(170, 195)
        
        # Animación
        self.battery_anim_value = 0
        self.target_battery = 0
        self.pulse_phase = 0.0
        self.is_charging = False
        
        # Datos de la API (ya no calculamos localmente)
        self.usage_time_hours = 0
        self.usage_time_minutes = 0
        self.estimated_autonomy_hours = 0
        self.battery_consumed = 0
        
        # Smart battery status
        self.smart_battery = None  # {status, battery_health, drain_rate_per_hour, estimated_minutes_remaining, capacity_mah}
        
        # Battery Intelligence (datos avanzados)
        self.battery_intelligence = None  # {soc_precise, equivalent_cycles, soh_percent, health_status, ...}
        
        # Tipo de conexión (Bluetooth/USB)
        self.connection_type = None
        
        # Timer para animación (60 FPS para fluidez)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate)
        self.anim_timer.start(16)  # ~60 FPS (1000ms / 60 = 16.67ms)
        
        # Habilitar composición optimizada
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
    
    def set_show_graph(self, show: bool):
        self.show_graph = show
        if show:
            # Aumentar altura si hay battery_intelligence para mostrar datos extra
            base_height = 195 if not self.battery_intelligence else 220
            self.setFixedSize(170, base_height)
        else:
            self.setFixedSize(170, 55)
        self.update()
    
    def _animate(self):
        import math
        changed = False
        
        # Interpolación más suave (easing) para 60 FPS
        # Factor 0.08 en vez de 0.15 para animación más gradual
        diff = self.target_battery - self.battery_anim_value
        if abs(diff) > 0.1:
            # Usar easing exponencial para suavidad
            self.battery_anim_value += diff * 0.08
            changed = True
        elif abs(diff) > 0:
            # Snap al valor final cuando está muy cerca
            self.battery_anim_value = self.target_battery
            changed = True
        
        # Fase de pulso más suave (velocidad reducida para 60 FPS)
        self.pulse_phase = (self.pulse_phase + 0.05) % (math.pi * 2)
        if self.is_charging:
            changed = True
        
        if changed:
            self.update()
    
    def update_data(self, data: Dict):
        self.device_data = data
        
        device_type = data.get('type', '')
        device_name = data.get('name', '')
        self.brand_info = get_brand_info(device_type, device_name)
        
        # Cargar icono SVG con alta calidad (HiDPI aware) en BLANCO
        if self.brand_info['icon_path'] and os.path.exists(self.brand_info['icon_path']):
            icon_path = self.brand_info['icon_path']
            # Obtener device pixel ratio para pantallas HiDPI
            dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 2.0
            icon_size = int(24 * dpr)
            
            if icon_path.endswith('.svg'):
                # Renderizar SVG a alta resolución
                renderer = QSvgRenderer(icon_path)
                img = QImage(icon_size, icon_size, QImage.Format.Format_ARGB32)
                img.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(img)
                renderer.render(painter)
                painter.end()
                
                # Convertir a blanco (reemplazar todos los colores por blanco)
                for y in range(img.height()):
                    for x in range(img.width()):
                        pixel = img.pixelColor(x, y)
                        if pixel.alpha() > 0:
                            img.setPixelColor(x, y, QColor(255, 255, 255, pixel.alpha()))
                
                self.brand_icon = QPixmap.fromImage(img)
            else:
                # Fallback para PNG
                original = QPixmap(icon_path)
                self.brand_icon = original.scaled(
                    icon_size, icon_size, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
            
            self.brand_icon.setDevicePixelRatio(dpr)
        
        # Colores dinámicos desde la API (igual que el frontend)
        colors_data = data.get('colors') or {}
        body_hex = None
        button_hex = None
        
        # Extraer colores del Joy-Con desde la API
        if colors_data:
            body_info = colors_data.get('body') or {}
            button_info = colors_data.get('buttons') or {}
            body_hex = body_info.get('hex')
            button_hex = button_info.get('hex')
        
        # Usar colores de la API si están disponibles
        if body_hex:
            self.body_color = QColor(body_hex)
            # Si no hay color de botones, oscurecer el body color
            if button_hex:
                self.button_color = QColor(button_hex)
            else:
                self.button_color = self.body_color.darker(120)
        elif self.brand_info['brand'] == 'playstation':
            self.body_color = QColor("#1a1a2e")
            self.button_color = QColor("#0f3460")
        else:
            self.body_color = QColor(self.brand_info['colors']['primary'])
            self.button_color = QColor(self.brand_info['colors']['secondary'])
        
        # Historial batería desde la API
        device_id = data.get('id', '')
        battery_data = data.get('battery') or {}
        battery = battery_data.get('percentage', 0)
        
        # Usar puntos de la gráfica desde la API (historial de DB)
        graph_points = data.get('graph_points', [])
        if graph_points:
            self.battery_history.set_points(device_id, graph_points)
            print(f"📊 {device_id}: {len(graph_points)} puntos en gráfica")
        else:
            # Fallback: agregar punto local
            self.battery_history.add_point(device_id, battery)
        
        # Datos de uso directamente de la API (igual que el frontend)
        self.usage_time_hours = data.get('usage_time_hours', 0) or 0
        self.usage_time_minutes = data.get('usage_time_minutes', 0) or 0
        self.estimated_autonomy_hours = data.get('estimated_autonomy_hours', 0) or 0
        self.battery_consumed = data.get('battery_consumed', 0) or 0
        
        # Smart battery status (nuevo sistema inteligente)
        self.smart_battery = data.get('smart_battery')
        if self.smart_battery:
            # Preferir la estimación inteligente si está disponible
            smart_mins = self.smart_battery.get('estimated_minutes_remaining', 0)
            if smart_mins and smart_mins > 0:
                self.estimated_autonomy_hours = smart_mins / 60.0
            
            # Extraer battery_intelligence si está incluido
            old_bi = self.battery_intelligence
            self.battery_intelligence = self.smart_battery.get('intelligence')
            
            # Si battery_intelligence cambia, actualizar tamaño del widget
            if self.show_graph and bool(self.battery_intelligence) != bool(old_bi):
                base_height = 195 if not self.battery_intelligence else 220
                self.setFixedSize(170, base_height)
        
        # Tipo de conexión
        self.connection_type = data.get('connection_type')
        
        # Debug - mostrar datos recibidos
        if self.usage_time_hours > 0 or self.usage_time_minutes > 0:
            print(f"⏱️ {device_id}: uso={self.usage_time_hours:.1f}h ({self.usage_time_minutes:.0f}m), autonomía={self.estimated_autonomy_hours}h")
        
        self.target_battery = battery
        self.is_charging = battery_data.get('charging', False)
        self.update()
    
    def paintEvent(self, event):
        if not self.device_data:
            return
        
        import math
        painter = QPainter(self)
        
        # Habilitar todos los hints de renderizado para máxima calidad
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        w, h = self.width(), self.height()
        battery = self.device_data.get('battery') or {}
        battery_pct = self.battery_anim_value
        charging = self.is_charging
        polling_data = self.device_data.get('polling') or {}
        polling = polling_data.get('rate_hz', 0)
        name = self.device_data.get('name', 'Unknown')
        device_id = self.device_data.get('id', '')
        
        pulse = 0.5 + 0.5 * math.sin(self.pulse_phase)
        
        # Fondo
        path = QPainterPath()
        path.addRoundedRect(1, 1, w-2, h-2, 12, 12)
        
        gradient = QLinearGradient(0, 0, w, h)
        c1 = QColor(self.body_color); c1.setAlpha(220)
        c2 = QColor(self.button_color); c2.setAlpha(180)
        gradient.setColorAt(0, c1)
        gradient.setColorAt(1, c2)
        painter.fillPath(path, QBrush(gradient))
        
        # Icono de marca
        if self.brand_icon and not self.brand_icon.isNull():
            painter.drawPixmap(8, 8, self.brand_icon)
        else:
            painter.setPen(Qt.GlobalColor.white)
            painter.setFont(QFont("Segoe UI Emoji", 12))
            painter.drawText(8, 8, 20, 20, Qt.AlignmentFlag.AlignCenter, "🎮")
        
        # Offset X para texto (Nintendo tiene icono más ancho)
        text_x = 38 if self.brand_info and self.brand_info.get('brand') == 'nintendo' else 32
        
        # Nombre
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        short_name = name.replace("DualShock 4", "DS4").replace("DualSense", "DS5")
        painter.drawText(text_x, 16, short_name)
        
        # Polling y tipo de conexión
        if polling > 0:
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor(255, 255, 255, 180))
            # Mostrar polling + tipo de conexión
            conn_icon = ""
            if self.connection_type:
                if "bluetooth" in self.connection_type.lower() or "bt" in self.connection_type.lower():
                    conn_icon = "📶"  # Bluetooth
                elif "usb" in self.connection_type.lower():
                    conn_icon = "🔌"  # USB
            polling_text = f"{polling:.0f}Hz {conn_icon}".strip()
            painter.drawText(text_x, 28, polling_text)
        
        # Tiempo de uso (desde la API)
        if self.usage_time_hours > 0 or self.usage_time_minutes > 0:
            if self.usage_time_hours >= 1:
                time_str = f"⏱ {self.usage_time_hours:.1f}h"
            else:
                time_str = f"⏱ {int(self.usage_time_minutes)}m"
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor(255, 255, 255, 200))
            painter.drawText(8, 42, time_str)
        
        # Autonomía estimada (desde la API - preferir smart battery)
        if self.estimated_autonomy_hours > 0 and not charging:
            if self.estimated_autonomy_hours < 1:
                autonomy_str = f"~{int(self.estimated_autonomy_hours * 60)}m left"
            else:
                autonomy_str = f"~{self.estimated_autonomy_hours:.1f}h left"
            
            # Color basado en estado inteligente de batería
            if self.smart_battery:
                status = self.smart_battery.get('status', 'Normal')
                if status == 'Critical':
                    status_color = QColor(255, 100, 100, 255)  # Rojo
                elif status == 'Low':
                    status_color = QColor(255, 200, 100, 220)  # Naranja
                else:
                    status_color = QColor(150, 255, 150, 220)  # Verde
            else:
                status_color = QColor(255, 200, 100, 220)  # Naranja por defecto
            
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(status_color)
            painter.drawText(70, 42, autonomy_str)
        
        # Mostrar salud de batería si está disponible (debajo del polling)
        if self.smart_battery and not charging:
            health = self.smart_battery.get('battery_health', 0)
            if health > 0:
                # Solo mostrar si hay suficiente espacio (cuando no hay tiempo de uso)
                if self.usage_time_hours == 0 and self.usage_time_minutes == 0:
                    # Mostrar salud de Battery Intelligence si disponible (más preciso)
                    if self.battery_intelligence and self.battery_intelligence.get('soh_percent'):
                        bi_health = self.battery_intelligence['soh_percent']
                        bi_cycles = self.battery_intelligence.get('equivalent_cycles', 0)
                        health_str = f"❤ {bi_health:.0f}% ({bi_cycles:.1f} ciclos)"
                        health = bi_health  # Usar para el color
                    else:
                        health_str = f"❤ {health:.0f}%"
                    painter.setFont(QFont("Segoe UI", 7))
                    if health >= 80:
                        painter.setPen(QColor(100, 255, 150, 200))  # Verde
                    elif health >= 50:
                        painter.setPen(QColor(255, 200, 100, 200))  # Naranja
                    else:
                        painter.setPen(QColor(255, 100, 100, 200))  # Rojo
                    painter.drawText(8, 42, health_str)
        
        # Batería circular
        ring_x, ring_y = w - 42, 5
        ring_size = 34
        
        painter.setPen(QPen(QColor(255, 255, 255, 50), 4))
        painter.drawArc(ring_x, ring_y, ring_size, ring_size, 0, 360 * 16)
        
        arc_color = QColor("#10b981") if battery_pct >= 50 else \
                   QColor("#fbbf24") if battery_pct >= 20 else QColor("#ef4444")
        
        if charging:
            glow_color = QColor(arc_color)
            glow_color.setAlpha(int(40 + 60 * pulse))
            painter.setPen(QPen(glow_color, 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            span = int(360 * 16 * battery_pct / 100)
            painter.drawArc(ring_x, ring_y, ring_size, ring_size, 90 * 16, -span)
            arc_color = arc_color.lighter(int(100 + 30 * pulse))
        
        painter.setPen(QPen(arc_color, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span = int(360 * 16 * battery_pct / 100)
        painter.drawArc(ring_x, ring_y, ring_size, ring_size, 90 * 16, -span)
        
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(ring_x, ring_y, ring_size, ring_size,
                        Qt.AlignmentFlag.AlignCenter, f"{int(battery_pct)}")
        
        # Punto de estado de batería (indicador LED)
        status_dot_size = 8
        status_dot_x = ring_x + ring_size - 4  # Esquina superior derecha del anillo
        status_dot_y = ring_y + 2
        
        # Determinar color del punto según el estado de SALUD de la batería (SoH)
        # Priorizar battery_intelligence con datos reales > fallback a gris
        status_color = None
        
        if self.battery_intelligence:
            health_status = self.battery_intelligence.get('health_status', '')
            soh = self.battery_intelligence.get('soh_percent', 0)
            confidence = self.battery_intelligence.get('confidence', 0)
            
            # Solo usar health_status si tenemos datos suficientes (confidence > 0)
            if confidence > 0 and health_status and health_status != 'Sin datos suficientes':
                if health_status == 'Crítica':
                    status_color = QColor(255, 60, 60, 255)  # Rojo - crítica
                elif health_status == 'Degradada':
                    status_color = QColor(255, 140, 60, 255)  # Naranja oscuro - degradada
                elif health_status == 'Aceptable':
                    status_color = QColor(255, 200, 60, 255)  # Amarillo - aceptable
                elif health_status == 'Buena':
                    status_color = QColor(120, 255, 120, 255)  # Verde claro - buena
                elif health_status == 'Excelente':
                    status_color = QColor(60, 255, 100, 255)  # Verde brillante - excelente
            elif soh > 0 and soh < 100:
                # Usar SoH directamente si está disponible
                if soh >= 90:
                    status_color = QColor(60, 255, 100, 255)  # Verde - excelente
                elif soh >= 80:
                    status_color = QColor(120, 255, 120, 255)  # Verde claro - buena
                elif soh >= 70:
                    status_color = QColor(255, 200, 60, 255)  # Amarillo - aceptable
                elif soh >= 50:
                    status_color = QColor(255, 140, 60, 255)  # Naranja - degradada
                else:
                    status_color = QColor(255, 60, 60, 255)  # Rojo - crítica
        
        # Si no tenemos datos de salud, mostrar gris (sin datos)
        if status_color is None:
            status_color = QColor(120, 120, 130, 200)  # Gris - sin datos de salud
        
        # Si está cargando, hacer el punto pulsante
        if charging:
            base_alpha = status_color.alpha()
            status_color.setAlpha(int(base_alpha * 0.7 + base_alpha * 0.3 * pulse))
        
        # Dibujar sombra/glow del punto
        glow_color = QColor(status_color)
        glow_color.setAlpha(60)
        painter.setBrush(QBrush(glow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(status_dot_x - 2, status_dot_y - 2, status_dot_size + 4, status_dot_size + 4)
        
        # Dibujar punto de estado
        painter.setBrush(QBrush(status_color))
        painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
        painter.drawEllipse(status_dot_x, status_dot_y, status_dot_size, status_dot_size)
        
        # GRÁFICO (solo si está habilitado)
        if not self.show_graph:
            return
            
        graph_x, graph_y = 8, 52
        graph_w, graph_h = w - 16, h - 60
        
        graph_path = QPainterPath()
        graph_path.addRoundedRect(graph_x, graph_y, graph_w, graph_h, 8, 8)
        graph_gradient = QLinearGradient(graph_x, graph_y, graph_x, graph_y + graph_h)
        graph_gradient.setColorAt(0, QColor(0, 0, 0, 100))
        graph_gradient.setColorAt(1, QColor(0, 0, 0, 50))
        painter.fillPath(graph_path, QBrush(graph_gradient))
        
        # Línea de batería
        points = self.battery_history.get_points(device_id)
        if len(points) >= 2:
            step = graph_w / max(len(points) - 1, 1)
            
            # Extraer valores de porcentaje
            percentages = [p.get('percentage', 0) if isinstance(p, dict) else p for p in points]
            
            # Área
            area_path = QPainterPath()
            area_path.moveTo(graph_x, graph_y + graph_h - 2)
            for i, pct in enumerate(percentages):
                x = graph_x + i * step
                y = graph_y + graph_h - (pct / 100 * (graph_h - 18)) - 14
                area_path.lineTo(x, y)
            area_path.lineTo(graph_x + (len(percentages) - 1) * step, graph_y + graph_h - 2)
            area_path.closeSubpath()
            
            area_color = QColor(self.body_color)
            area_color.setAlpha(60)
            painter.fillPath(area_path, QBrush(area_color))
            
            # Línea
            line_path = QPainterPath()
            point_positions = []  # Guardar posiciones para dibujar puntos después
            for i, pct in enumerate(percentages):
                x = graph_x + i * step
                y = graph_y + graph_h - (pct / 100 * (graph_h - 18)) - 14
                point_positions.append((x, y, i))
                if i == 0:
                    line_path.moveTo(x, y)
                else:
                    line_path.lineTo(x, y)
            
            # Usar blanco para PlayStation (colores oscuros)
            if self.brand_info and self.brand_info['brand'] == 'playstation':
                line_color = QColor("#ffffff")
            else:
                line_color = QColor(self.body_color)
            line_color.setAlpha(255)
            painter.setPen(QPen(line_color, 2.5, Qt.PenStyle.SolidLine, 
                               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(line_path)
            
            # Dibujar puntos en cada posición (como en el frontend)
            for px, py, idx in point_positions:
                is_last = (idx == len(point_positions) - 1)
                
                if is_last:
                    # Punto actual más grande con glow
                    glow_color = QColor(line_color)
                    glow_color.setAlpha(80)
                    painter.setBrush(QBrush(glow_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QPointF(px, py), 5, 5)
                    
                    painter.setBrush(QBrush(Qt.GlobalColor.white))
                    painter.setPen(QPen(line_color, 2))
                    painter.drawEllipse(QPointF(px, py), 3, 3)
                else:
                    # Puntos intermedios más pequeños
                    point_color = QColor(line_color)
                    point_color.setAlpha(200)
                    painter.setBrush(QBrush(Qt.GlobalColor.white))
                    painter.setPen(QPen(point_color, 1.5))
                    painter.drawEllipse(QPointF(px, py), 2, 2)
            
            # Dibujar etiquetas de tiempo (horas) en el eje X
            painter.setFont(QFont("Segoe UI", 6))
            painter.setPen(QColor(255, 255, 255, 150))
            
            # Mostrar hora del primer y último punto
            if len(points) > 0:
                first_point = points[0]
                last_point = points[-1]
                
                # Hora del primer punto (izquierda)
                if isinstance(first_point, dict) and first_point.get('timestamp'):
                    try:
                        from datetime import datetime
                        ts = first_point['timestamp']
                        if 'T' in ts:
                            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                            time_str = dt.strftime('%H:%M')
                            painter.drawText(int(graph_x), int(graph_y + graph_h - 2), time_str)
                    except:
                        pass
                
                # Hora del último punto (derecha)
                if isinstance(last_point, dict) and last_point.get('timestamp'):
                    try:
                        ts = last_point['timestamp']
                        if 'T' in ts:
                            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                            time_str = dt.strftime('%H:%M')
                            text_width = 25
                            painter.drawText(int(graph_x + graph_w - text_width), int(graph_y + graph_h - 2), time_str)
                    except:
                        pass
        
        # Battery Intelligence - mostrar debajo del gráfico si está disponible
        if self.battery_intelligence:
            bi = self.battery_intelligence
            info_y = graph_y + graph_h + 8
            
            painter.setFont(QFont("Segoe UI", 6))
            
            # SOC preciso y ciclos
            soc = bi.get('soc_precise', 0)
            cycles = bi.get('equivalent_cycles', 0)
            
            # Icono de tipo de datos (voltaje real vs estimado)
            if bi.get('has_voltage_data'):
                type_icon = "⚡"  # Voltaje real
                type_color = QColor(100, 255, 150, 200)
            else:
                type_icon = "📊"  # Estimado
                type_color = QColor(100, 180, 255, 200)
            
            painter.setPen(type_color)
            info_text = f"{type_icon} SOC: {soc:.1f}% | Ciclos: {cycles:.1f}"
            painter.drawText(graph_x + 2, int(info_y + 8), info_text)
            
            # SoH y estado
            soh = bi.get('soh_percent')
            status = bi.get('health_status', 'unknown')
            
            status_colors = {
                'excellent': QColor(100, 255, 150, 200),
                'good': QColor(150, 255, 150, 200),
                'fair': QColor(255, 200, 100, 200),
                'poor': QColor(255, 150, 100, 200),
                'critical': QColor(255, 100, 100, 200),
                'unknown': QColor(150, 150, 150, 200)
            }
            status_names = {
                'excellent': 'Excelente',
                'good': 'Bueno',
                'fair': 'Regular',
                'poor': 'Pobre',
                'critical': 'Crítico',
                'unknown': '?'
            }
            
            painter.setPen(status_colors.get(status, status_colors['unknown']))
            if soh is not None:
                soh_text = f"SoH: {soh:.0f}% - {status_names.get(status, '?')}"
            else:
                soh_text = f"SoH: -- - {status_names.get(status, '?')}"
            painter.drawText(graph_x + 2, int(info_y + 18), soh_text)


# ============ Main Overlay Window ============
# ============ Top Screen Color Bar (Independent Window) ============
class TopColorBar(QMainWindow):
    """Barra independiente en la parte superior de la pantalla que muestra animaciones de color al conectar dispositivos"""
    def __init__(self):
        super().__init__()
        
        self.connected_devices: Dict[str, QColor] = {}  # device_id -> color
        self.animation_queue: List[tuple] = []  # [(color, progress), ...]
        self.current_animation: Optional[tuple] = None  # (color, progress 0-1)
        self.bar_height = 4
        self.animation_duration = 800  # ms
        
        self.setup_window()
        
        # Timer para animación
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate)
        self.anim_timer.start(16)  # ~60fps
        
        # Tiempo de inicio de animación actual
        self.anim_start_time = 0
    
    def setup_window(self):
        # Ventana invisible, siempre arriba, sin bordes
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Posicionar en la parte superior de la pantalla
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), self.bar_height)
        
        self.show()
    
    def trigger_animation(self, device_id: str, color: QColor):
        """Disparar animación cuando se conecta un nuevo dispositivo"""
        if device_id not in self.connected_devices:
            self.connected_devices[device_id] = color
            # Agregar a cola de animaciones
            self.animation_queue.append((color, device_id))
            
            # Si no hay animación en curso, iniciar
            if self.current_animation is None:
                self._start_next_animation()
    
    def remove_device(self, device_id: str):
        """Remover dispositivo de la lista"""
        if device_id in self.connected_devices:
            del self.connected_devices[device_id]
    
    def _start_next_animation(self):
        if self.animation_queue:
            color, device_id = self.animation_queue.pop(0)
            self.current_animation = (color, 0.0)
            self.anim_start_time = time.time() * 1000
    
    def _animate(self):
        if self.current_animation is None:
            return
        
        color, _ = self.current_animation
        elapsed = (time.time() * 1000) - self.anim_start_time
        progress = min(elapsed / self.animation_duration, 1.0)
        
        self.current_animation = (color, progress)
        self.update()
        
        if progress >= 1.0:
            # Animación completada, esperar un poco y desvanecer
            QTimer.singleShot(200, self._fade_out)
    
    def _fade_out(self):
        self.current_animation = None
        self.update()
        # Iniciar siguiente animación si hay en cola
        self._start_next_animation()
    
    def paintEvent(self, event):
        if self.current_animation is None:
            return
        
        color, progress = self.current_animation
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        w, h = self.width(), self.height()
        
        # Animación: la barra crece desde el centro hacia los lados
        # y luego se desvanece
        if progress < 0.6:
            # Fase 1: Crecer desde el centro (0 -> 0.6)
            grow_progress = progress / 0.6
            # Easing ease-out
            grow_progress = 1 - (1 - grow_progress) ** 3
            
            bar_width = w * grow_progress
            x = (w - bar_width) / 2
            
            c = QColor(color)
            c.setAlpha(255)
            
            # Gradiente con brillo en el centro
            gradient = QLinearGradient(x, 0, x + bar_width, 0)
            c_transparent = QColor(color)
            c_transparent.setAlpha(0)
            c_bright = QColor(color).lighter(130)
            
            gradient.setColorAt(0, c_transparent)
            gradient.setColorAt(0.3, c)
            gradient.setColorAt(0.5, c_bright)
            gradient.setColorAt(0.7, c)
            gradient.setColorAt(1, c_transparent)
            
            painter.fillRect(int(x), 0, int(bar_width), h, gradient)
        else:
            # Fase 2: Desvanecer (0.6 -> 1.0)
            fade_progress = (progress - 0.6) / 0.4
            alpha = int(255 * (1 - fade_progress))
            
            c = QColor(color)
            c.setAlpha(alpha)
            
            gradient = QLinearGradient(0, 0, w, 0)
            c_transparent = QColor(color)
            c_transparent.setAlpha(0)
            c_center = QColor(color)
            c_center.setAlpha(alpha)
            
            gradient.setColorAt(0, c_transparent)
            gradient.setColorAt(0.3, c_center)
            gradient.setColorAt(0.5, c_center)
            gradient.setColorAt(0.7, c_center)
            gradient.setColorAt(1, c_transparent)
            
            painter.fillRect(0, 0, w, h, gradient)
        
        painter.end()


# ============ WebSocket Worker for Notifications ============
class WebSocketWorker(QThread):
    """Worker para escuchar WebSocket y recibir notificaciones en tiempo real"""
    notification_received = pyqtSignal(dict)
    connection_changed = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.running = True
    
    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                loop.run_until_complete(self._connect_websocket())
            except Exception as e:
                print(f"⚠️ WebSocket error: {e}")
                self.connection_changed.emit(False)
            
            # Reintentar conexión después de 5 segundos
            if self.running:
                self.msleep(5000)
        
        loop.close()
    
    async def _connect_websocket(self):
        import aiohttp
        async with aiohttp.ClientSession() as session:
            try:
                async with session.ws_connect(f"{WS_BASE}/api/ws") as ws:
                    self.connection_changed.emit(True)
                    print("✅ WebSocket conectado para notificaciones")
                    
                    async for msg in ws:
                        if not self.running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = msg.json()
                                msg_type = data.get('type', '')
                                
                                # Filtrar solo eventos de notificación
                                if msg_type in ['device_disconnected', 'device_reconnected', 
                                                'charging_change', 'battery_update']:
                                    self.notification_received.emit(data)
                            except:
                                pass
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
            except Exception as e:
                self.connection_changed.emit(False)
                raise
    
    def stop(self):
        self.running = False


# ============ Notification Toast Widget ============
class NotificationToast(QWidget):
    """Widget de notificación tipo toast con iconos SVG"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.notifications: List[dict] = []  # Cola de notificaciones
        self.current_notification: Optional[dict] = None
        self.animation_progress = 0.0
        self.animation_phase = 'idle'  # idle, show, visible, hide
        self.visible_time = 0
        
        # Cache de iconos SVG renderizados
        self._icon_cache: Dict[str, QPixmap] = {}
        
        # Anti-duplicados: {device_id: timestamp}
        self._last_notification: Dict[str, float] = {}
        self._duplicate_cooldown = 3.0  # segundos
        
        self.setFixedSize(280, 60)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Posicionar en la esquina superior derecha
        self._update_position()
        
        # Timer para animación
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate)
        self.anim_timer.start(16)
        
        self.show()
    
    def _update_position(self):
        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 20
        y = 50
        self.move(x, y)
    
    def _get_icon_for_device(self, device_id: str) -> str:
        """Obtener ruta del icono SVG según el tipo de dispositivo (mismos que las tarjetas)"""
        device_id_lower = device_id.lower()
        
        # Usar los mismos iconos que las tarjetas pequeñas (SCRIPT_DIR)
        if 'joycon' in device_id_lower or 'joy-con' in device_id_lower:
            return ICON_NINTENDO
        elif 'dualsense' in device_id_lower or 'dualshock' in device_id_lower or 'ds4' in device_id_lower or 'ds5' in device_id_lower:
            return ICON_PLAYSTATION
        elif 'xbox' in device_id_lower:
            return ICON_XBOX
        else:
            return ICON_PLAYSTATION  # Default
    
    def _load_icon(self, icon_path: str, size: int = 28) -> Optional[QPixmap]:
        """Cargar y cachear icono SVG/PNG en BLANCO con HiDPI (igual que las tarjetas)"""
        if not icon_path or not os.path.exists(icon_path):
            return None
        
        # Obtener device pixel ratio para pantallas HiDPI
        dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 2.0
        render_size = int(size * dpr)
        
        cache_key = f"{icon_path}_{render_size}_white_hidpi"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        try:
            if icon_path.lower().endswith('.svg'):
                from PyQt6.QtSvg import QSvgRenderer
                renderer = QSvgRenderer(icon_path)
                
                # Renderizar a alta resolución para HiDPI
                img = QImage(render_size, render_size, QImage.Format.Format_ARGB32)
                img.fill(Qt.GlobalColor.transparent)
                painter = QPainter(img)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                renderer.render(painter)
                painter.end()
                
                # Convertir a blanco (igual que en DeviceWidget)
                for y in range(img.height()):
                    for x in range(img.width()):
                        pixel = img.pixelColor(x, y)
                        if pixel.alpha() > 0:
                            img.setPixelColor(x, y, QColor(255, 255, 255, pixel.alpha()))
                
                pixmap = QPixmap.fromImage(img)
                pixmap.setDevicePixelRatio(dpr)
            else:
                # PNG con escalado de alta calidad
                original = QPixmap(icon_path)
                pixmap = original.scaled(
                    render_size, render_size, 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                pixmap.setDevicePixelRatio(dpr)
            
            self._icon_cache[cache_key] = pixmap
            return pixmap
        except Exception as e:
            print(f"Error cargando icono {icon_path}: {e}")
            return None
    
    def _is_duplicate(self, device_id: str, notif_type: str) -> bool:
        """Verificar si es una notificación duplicada"""
        key = f"{device_id}:{notif_type}"
        now = time.time()
        
        if key in self._last_notification:
            elapsed = now - self._last_notification[key]
            if elapsed < self._duplicate_cooldown:
                print(f"⚠️ Notificación duplicada ignorada: {key} (hace {elapsed:.1f}s)")
                return True
        
        self._last_notification[key] = now
        return False
    
    def add_notification(self, notif_type: str, title: str, message: str, 
                        color: QColor = None, icon: str = "🔔", 
                        device_id: str = "", icon_path: str = ""):
        """Añadir una notificación a la cola"""
        # Verificar duplicados si hay device_id
        if device_id and self._is_duplicate(device_id, notif_type):
            return
        
        # Si no hay icon_path explícito, obtenerlo del device_id
        if not icon_path and device_id:
            icon_path = self._get_icon_for_device(device_id)
        
        self.notifications.append({
            'type': notif_type,
            'title': title,
            'message': message,
            'color': color or QColor("#3b82f6"),
            'icon': icon,
            'icon_path': icon_path
        })
        
        # Si no hay notificación activa, iniciar
        if self.animation_phase == 'idle':
            self._show_next()
    
    def _show_next(self):
        if not self.notifications:
            self.animation_phase = 'idle'
            self.current_notification = None
            self.update()
            return
        
        self.current_notification = self.notifications.pop(0)
        self.animation_phase = 'show'
        self.animation_progress = 0.0
        self.visible_time = 0
    
    def _animate(self):
        if self.animation_phase == 'idle':
            return
        
        if self.animation_phase == 'show':
            self.animation_progress += 0.08
            if self.animation_progress >= 1.0:
                self.animation_progress = 1.0
                self.animation_phase = 'visible'
            self.update()
        
        elif self.animation_phase == 'visible':
            self.visible_time += 16
            if self.visible_time >= 3000:  # 3 segundos visible
                self.animation_phase = 'hide'
        
        elif self.animation_phase == 'hide':
            self.animation_progress -= 0.08
            if self.animation_progress <= 0:
                self.animation_progress = 0
                self._show_next()
            self.update()
    
    def paintEvent(self, event):
        if self.current_notification is None or self.animation_phase == 'idle':
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        w, h = self.width(), self.height()
        notif = self.current_notification
        
        # Animación de entrada/salida desde la derecha
        offset_x = int((1 - self.animation_progress) * (w + 20))
        
        # Fondo
        path = QPainterPath()
        path.addRoundedRect(offset_x, 0, w - 10, h - 5, 10, 10)
        
        # Sombra
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(offset_x + 2, 3, w - 10, h - 5, 10, 10)
        painter.fillPath(shadow_path, QBrush(QColor(0, 0, 0, 50)))
        
        # Fondo principal
        gradient = QLinearGradient(offset_x, 0, offset_x + w, 0)
        gradient.setColorAt(0, QColor(30, 30, 40, 240))
        gradient.setColorAt(1, QColor(40, 40, 55, 240))
        painter.fillPath(path, QBrush(gradient))
        
        # Borde de color
        color = notif['color']
        border_path = QPainterPath()
        border_path.addRoundedRect(offset_x, 0, 4, h - 5, 2, 2)
        painter.fillPath(border_path, QBrush(color))
        
        # Icono (SVG/PNG o emoji fallback)
        icon_path = notif.get('icon_path', '')
        icon_pixmap = self._load_icon(icon_path, 28) if icon_path else None
        
        if icon_pixmap:
            # Dibujar icono SVG/PNG
            icon_x = offset_x + 12
            icon_y = (h - 5 - 28) // 2
            painter.drawPixmap(icon_x, icon_y, icon_pixmap)
        else:
            # Fallback a emoji
            painter.setFont(QFont("Segoe UI Emoji", 16))
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(offset_x + 12, 10, 30, 30, Qt.AlignmentFlag.AlignCenter, notif['icon'])
        
        # Título
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(offset_x + 45, 8, w - 60, 20, Qt.AlignmentFlag.AlignLeft, notif['title'])
        
        # Mensaje
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(200, 200, 200))
        painter.drawText(offset_x + 45, 28, w - 60, 20, Qt.AlignmentFlag.AlignLeft, notif['message'])
        
        painter.end()


# ============ Header Widget con fondo pintado ============
class HeaderWidget(QWidget):
    """Widget de header con fondo semi-transparente pintado correctamente"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        
        # Dibujar fondo redondeado
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 8, 8)
        painter.fillPath(path, QColor(30, 30, 40, 220))
        
        painter.end()


# ============ Button Input Worker ============
class ButtonInputWorker(QThread):
    """Worker para detectar pulsación de botones del Joy-Con"""
    button_pressed = pyqtSignal(str)  # Emite el nombre del botón presionado
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.target_button = None  # Botón a monitorear
        self.target_device = "any"  # Dispositivo específico o "any"
        self.button_byte = 0
        self.button_mask = 0
        self.last_state = {}  # {device_id: bool}
        self.has_joycons = False  # Flag para saber si hay Joy-Cons
        self.error_count = 0  # Contador de errores consecutivos
        self.max_errors = 5  # Máximo de errores antes de pausar
        self.pause_duration = 5000  # Pausa en ms cuando hay muchos errores
    
    def set_target_button(self, button_name: str):
        """Configurar qué botón monitorear"""
        if button_name in JOYCON_BUTTONS:
            self.target_button = button_name
            self.button_byte, self.button_mask = JOYCON_BUTTONS[button_name]
            self.last_state = {}
            print(f"🎮 Monitoreando botón: {button_name}")
    
    def set_target_device(self, device_id: str):
        """Configurar qué dispositivo monitorear"""
        self.target_device = device_id
        self.last_state = {}
    
    def set_has_joycons(self, has_joycons: bool):
        """Indicar si hay Joy-Cons conectados"""
        self.has_joycons = has_joycons
        if has_joycons:
            self.error_count = 0  # Reset errores cuando hay nuevos dispositivos
    
    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            # Solo hacer polling si hay un botón configurado Y hay Joy-Cons
            if self.target_button and self.has_joycons:
                try:
                    loop.run_until_complete(self._check_button())
                    self.error_count = 0  # Reset en éxito
                except Exception as e:
                    self.error_count += 1
                    if self.error_count >= self.max_errors:
                        # Pausar por un tiempo si hay muchos errores
                        self.msleep(self.pause_duration)
                        self.error_count = 0
                self.msleep(50)  # Chequear cada 50ms
            else:
                # Sin Joy-Cons o sin botón configurado, esperar más
                self.msleep(500)
        
        loop.close()
    
    async def _check_button(self):
        """Consultar el estado del botón vía API"""
        if not self.has_joycons:
            return
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_BASE}/api/buttons",
                    timeout=aiohttp.ClientTimeout(total=1)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Si no hay datos de Joy-Cons, marcar que no hay
                        joycon_found = False
                        
                        # Buscar en los dispositivos conectados
                        for device_id, buttons in data.items():
                            if 'joycon' not in device_id.lower():
                                continue
                            
                            joycon_found = True
                            
                            # Filtrar por dispositivo si se especificó uno
                            if self.target_device != "any" and device_id != self.target_device:
                                continue
                            
                            # Verificar si el botón está presionado
                            current_state = buttons.get(self.target_button, False)
                            prev_state = self.last_state.get(device_id, False)
                            
                            # Detectar flanco de subida (presión)
                            if current_state and not prev_state:
                                self.button_pressed.emit(self.target_button)
                            
                            self.last_state[device_id] = current_state
                            
                            # Si es "any", solo necesitamos detectar en uno
                            if self.target_device == "any" and current_state and not prev_state:
                                break
                        
                        # Actualizar flag si no se encontraron Joy-Cons
                        if not joycon_found:
                            self.has_joycons = False
                    elif resp.status == 404:
                        # No hay endpoint o no hay dispositivos
                        self.has_joycons = False
        except aiohttp.ClientError:
            # Error de conexión, incrementar contador
            raise
        except Exception:
            pass
    
    def stop(self):
        self.running = False


# ============ Bluetooth Manager Window ============
class BluetoothManagerWindow(QMainWindow):
    """Ventana para gestionar dispositivos Bluetooth con descubrimiento real"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.refresh_devices()
    
    def setup_ui(self):
        self.setWindowTitle("📡 Gestor de Bluetooth")
        self.setFixedSize(700, 600)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        # Estilo oscuro mejorado
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
            }
            QPushButton:pressed {
                background: #1d4ed8;
            }
            QPushButton:disabled {
                background: #334155;
                color: #64748b;
            }
            QGroupBox {
                background: #1e293b;
                border: 2px solid #334155;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 12px;
                background: #0f172a;
                border-radius: 6px;
            }
            QListWidget {
                background: #1e293b;
                color: white;
                border: 2px solid #334155;
                border-radius: 10px;
                padding: 8px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 12px;
                border-radius: 6px;
                margin: 3px 0;
                border: 1px solid transparent;
            }
            QListWidget::item:hover {
                background: #334155;
                border: 1px solid #475569;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
                border: 1px solid #60a5fa;
            }
        """)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Título
        title = QLabel("📡 Gestor de Dispositivos Bluetooth")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Botones de control
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        refresh_btn = QPushButton("🔄 Actualizar Lista")
        refresh_btn.clicked.connect(self.refresh_devices)
        buttons_layout.addWidget(refresh_btn)
        
        pair_new_btn = QPushButton("➕ Emparejar Nuevo Dispositivo")
        pair_new_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #10b981, stop:1 #059669);
                padding: 12px 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #059669, stop:1 #047857);
            }
        """)
        pair_new_btn.clicked.connect(self.open_windows_bluetooth)
        buttons_layout.addWidget(pair_new_btn)
        
        layout.addLayout(buttons_layout)
        
        # Grupo de dispositivos conectados
        connected_group = QGroupBox("✅ Dispositivos Conectados")
        connected_layout = QVBoxLayout(connected_group)
        connected_layout.setContentsMargins(10, 15, 10, 10)
        connected_layout.setSpacing(8)
        
        self.connected_list = QListWidget()
        self.connected_list.setMinimumHeight(160)
        connected_layout.addWidget(self.connected_list)
        
        # Botones para dispositivos conectados
        connected_buttons = QHBoxLayout()
        connected_buttons.setSpacing(8)
        self.disconnect_btn = QPushButton("🔌 Desconectar")
        self.disconnect_btn.clicked.connect(self.disconnect_selected)
        self.disconnect_btn.setEnabled(False)
        connected_buttons.addWidget(self.disconnect_btn)
        
        self.unpair_btn = QPushButton("🗑️ Desemparejar")
        self.unpair_btn.clicked.connect(self.unpair_selected)
        self.unpair_btn.setEnabled(False)
        connected_buttons.addWidget(self.unpair_btn)
        
        connected_layout.addLayout(connected_buttons)
        layout.addWidget(connected_group)
        
        # Información útil
        info_label = QLabel(
            "💡 <b>Para emparejar un nuevo Joy-Con o controlador:</b><br>"
            "   1. Haz clic en 'Emparejar Nuevo Dispositivo'<br>"
            "   2. Pon tu dispositivo en modo emparejamiento<br>"
            "   3. Selecciónalo en la ventana de Windows<br><br>"
            "   <i>Nota: Los Joy-Con pueden requerir reconexión manual debido a las Link Keys.</i>"
        )
        info_label.setStyleSheet("""
            QLabel {
                background: #1e293b;
                border: 2px solid #334155;
                border-radius: 10px;
                padding: 15px;
                font-size: 11px;
                color: #cbd5e1;
            }
        """)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Conectar señales de selección
        self.connected_list.itemSelectionChanged.connect(self._on_connected_selection)
        
        # Botón cerrar
        close_btn = QPushButton("✕ Cerrar")
        close_btn.setStyleSheet("background: #ef4444; padding: 8px;")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
    
    def _on_connected_selection(self):
        has_selection = len(self.connected_list.selectedItems()) > 0
        self.disconnect_btn.setEnabled(has_selection)
        self.unpair_btn.setEnabled(has_selection)
    
    def open_windows_bluetooth(self):
        """Abrir configuración de Bluetooth de Windows"""
        try:
            import subprocess
            subprocess.Popen(["explorer.exe", "ms-settings:bluetooth"], shell=True)
            QMessageBox.information(
                self,
                "🔗 Emparejar Dispositivo",
                "✅ Se abrió la configuración de Bluetooth.\n\n"
                "💡 Para emparejar un Joy-Con:\n"
                "   1. Mantén presionado el botón SYNC 3+ segundos\n"
                "   2. Los LEDs parpadearán verde\n"
                "   3. En Windows: 'Agregar dispositivo' → Bluetooth\n"
                "   4. Selecciona 'Joy-Con (L)' o 'Joy-Con (R)'\n\n"
                "Luego haz clic en 'Actualizar Lista' aquí."
            )
        except Exception as e:
            QMessageBox.critical(self, "❌ Error", f"No se pudo abrir Bluetooth: {str(e)}")
    
    def refresh_devices(self):
        """Actualizar lista de dispositivos"""
        self.connected_list.clear()
        
        try:
            import requests
            
            # Obtener dispositivos conectados
            response = requests.get(f"{API_BASE}/api/devices", timeout=3)
            if response.status_code == 200:
                devices = response.json()
                for device in devices:
                    device_id = device.get('id', '')
                    device_type = device.get('type', 'Unknown')
                    model = device.get('model', device_id)
                    battery = device.get('battery', 0)
                    
                    # Crear item con icono según tipo
                    icon = "🎮"
                    if 'joycon' in device_type.lower() or 'joy-con' in device_type.lower():
                        icon = "🕹️"
                    elif 'dualsense' in device_type.lower():
                        icon = "🎮"
                    elif 'dualshock' in device_type.lower():
                        icon = "🎮"
                    elif 'xbox' in device_type.lower():
                        icon = "🎮"
                    
                    item_text = f"{icon} {model} - {battery}% | {device_id}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, device_id)
                    self.connected_list.addItem(item)
            
            # Mostrar mensaje si no hay dispositivos
            if self.connected_list.count() == 0:
                placeholder = QListWidgetItem("ℹ️ No hay dispositivos conectados")
                placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
                self.connected_list.addItem(placeholder)
            
        except Exception as e:
            print(f"Error actualizando dispositivos: {e}")
            error_item = QListWidgetItem(f"❌ Error: {str(e)}")
            error_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.connected_list.addItem(error_item)
    
    def disconnect_selected(self):
        """Desconectar dispositivo seleccionado"""
        selected = self.connected_list.selectedItems()
        if not selected:
            return
        
        device_id = selected[0].data(Qt.ItemDataRole.UserRole)
        
        try:
            import requests
            response = requests.post(f"{API_BASE}/api/device/{device_id}/disconnect", timeout=5)
            
            if response.status_code == 200:
                QMessageBox.information(self, "✅ Éxito", "Dispositivo desconectado correctamente")
                self.refresh_devices()
            else:
                QMessageBox.warning(self, "⚠️ Error", f"No se pudo desconectar: {response.text}")
        except Exception as e:
            QMessageBox.critical(self, "❌ Error", f"Error al desconectar: {str(e)}")
    
    def unpair_selected(self):
        """Desemparejar dispositivo seleccionado"""
        selected = self.connected_list.selectedItems()
        if not selected:
            return
        
        device_id = selected[0].data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self,
            "🗑️ Confirmar Desemparejamiento",
            f"¿Deseas desemparejar este dispositivo?\nTendrás que volver a emparejarlo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import requests
                response = requests.post(f"{API_BASE}/api/device/{device_id}/unpair", timeout=10)
                
                if response.status_code == 200:
                    QMessageBox.information(self, "✅ Éxito", "Dispositivo desemparejado correctamente")
                    self.refresh_devices()
                else:
                    result = response.json()
                    QMessageBox.warning(self, "⚠️ Error", f"No se pudo desemparejar: {result.get('detail', 'Error desconocido')}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", f"Error al desemparejar: {str(e)}")


# ============ Options Window ============
class OptionsWindow(QMainWindow):
    """Ventana de opciones del overlay"""
    
    settings_changed = pyqtSignal()
    
    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("⚙️ Opciones del Overlay")
        self.setFixedSize(400, 500)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        # Estilo oscuro
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QGroupBox {
                color: white;
                font-weight: bold;
                border: 1px solid #3b3b5c;
                border-radius: 8px;
                margin-top: 16px;
                padding: 15px 10px 10px 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QCheckBox {
                color: #e0e0e0;
                font-size: 12px;
                spacing: 10px;
                padding: 5px 0px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #555;
                background: #2a2a3e;
            }
            QCheckBox::indicator:checked {
                background: #10b981;
                border-color: #10b981;
            }
            QComboBox {
                background: #2a2a3e;
                color: white;
                border: 1px solid #3b3b5c;
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 120px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background: #2a2a3e;
                color: white;
                selection-background-color: #10b981;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 11px;
            }
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2563eb;
            }
            QPushButton:pressed {
                background: #1d4ed8;
            }
        """)
        
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Título (fuera del scroll)
        title = QLabel("⚙️ Configuración del Overlay")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold; padding: 5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #2a2a3e;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #777;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Widget contenedor para el scroll
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(20)
        
        # Grupo: Elementos visuales
        visual_group = QGroupBox("🎨 Elementos Visuales")
        visual_layout = QVBoxLayout(visual_group)
        visual_layout.setSpacing(12)
        visual_layout.setContentsMargins(10, 15, 10, 10)
        
        self.cb_color_bar = QCheckBox("Barra de conexión (animación superior)")
        self.cb_color_bar.setChecked(self.settings.get('show_color_bar', True))
        self.cb_color_bar.toggled.connect(lambda v: self._on_setting_changed('show_color_bar', v))
        visual_layout.addWidget(self.cb_color_bar)
        
        self.cb_notifications = QCheckBox("Notificaciones (toasts)")
        self.cb_notifications.setChecked(self.settings.get('show_notifications', True))
        self.cb_notifications.toggled.connect(lambda v: self._on_setting_changed('show_notifications', v))
        visual_layout.addWidget(self.cb_notifications)
        
        layout.addWidget(visual_group)
        
        # Grupo: Sonidos
        sound_group = QGroupBox("🔊 Sonidos de Notificaciones")
        sound_layout = QVBoxLayout(sound_group)
        sound_layout.setSpacing(12)
        sound_layout.setContentsMargins(10, 15, 10, 10)
        
        self.cb_sound_connect = QCheckBox("Sonido al conectar dispositivo")
        self.cb_sound_connect.setChecked(self.settings.get('sound_connect', True))
        self.cb_sound_connect.toggled.connect(lambda v: self._on_setting_changed('sound_connect', v))
        sound_layout.addWidget(self.cb_sound_connect)
        
        self.cb_sound_disconnect = QCheckBox("Sonido al desconectar dispositivo")
        self.cb_sound_disconnect.setChecked(self.settings.get('sound_disconnect', True))
        self.cb_sound_disconnect.toggled.connect(lambda v: self._on_setting_changed('sound_disconnect', v))
        sound_layout.addWidget(self.cb_sound_disconnect)
        
        self.cb_sound_reconnect = QCheckBox("Sonido al reconectar dispositivo")
        self.cb_sound_reconnect.setChecked(self.settings.get('sound_reconnect', True))
        self.cb_sound_reconnect.toggled.connect(lambda v: self._on_setting_changed('sound_reconnect', v))
        sound_layout.addWidget(self.cb_sound_reconnect)
        
        layout.addWidget(sound_group)
        
        # Grupo: Control por Joy-Con
        joycon_group = QGroupBox("🎮 Control por Joy-Con")
        joycon_layout = QVBoxLayout(joycon_group)
        joycon_layout.setSpacing(12)
        joycon_layout.setContentsMargins(10, 15, 10, 10)
        
        self.cb_toggle_enabled = QCheckBox("Habilitar toggle con botón del Joy-Con")
        self.cb_toggle_enabled.setChecked(self.settings.get('toggle_enabled', False))
        self.cb_toggle_enabled.toggled.connect(lambda v: self._on_setting_changed('toggle_enabled', v))
        joycon_layout.addWidget(self.cb_toggle_enabled)
        
        # Selector de dispositivo
        device_row = QHBoxLayout()
        device_label = QLabel("Dispositivo:")
        device_row.addWidget(device_label)
        
        self.device_combo = QComboBox()
        self.device_combo.addItem("Cualquier Joy-Con", "any")
        self.device_combo.setMinimumWidth(180)
        # Se actualizará dinámicamente con los dispositivos conectados
        current_device = self.settings.get('toggle_device', 'any')
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        device_row.addWidget(self.device_combo)
        device_row.addStretch()
        joycon_layout.addLayout(device_row)
        
        # Botón para refrescar dispositivos
        refresh_btn = QPushButton("🔄 Actualizar dispositivos")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #374151;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #4b5563;
            }
        """)
        refresh_btn.clicked.connect(self._refresh_devices)
        joycon_layout.addWidget(refresh_btn)
        
        # Selector de botón
        button_row = QHBoxLayout()
        button_label = QLabel("Botón para mostrar/ocultar:")
        button_row.addWidget(button_label)
        
        self.button_combo = QComboBox()
        # Añadir botones disponibles
        button_options = ['Capture', 'Home', 'Minus', 'Plus', 'L', 'ZL', 'R', 'ZR', 
                          'L Stick', 'R Stick', 'SL (L)', 'SR (L)', 'SL (R)', 'SR (R)']
        self.button_combo.addItems(button_options)
        current_button = self.settings.get('toggle_button', 'Capture')
        if current_button in button_options:
            self.button_combo.setCurrentText(current_button)
        self.button_combo.currentTextChanged.connect(
            lambda v: self._on_setting_changed('toggle_button', v)
        )
        button_row.addWidget(self.button_combo)
        button_row.addStretch()
        joycon_layout.addLayout(button_row)
        
        # Nota
        note = QLabel("💡 Presiona el botón seleccionado en tu Joy-Con\npara mostrar/ocultar el overlay.")
        note.setStyleSheet("color: #888; font-size: 10px;")
        joycon_layout.addWidget(note)
        
        layout.addWidget(joycon_group)
        
        # Grupo: Atajos de teclado
        hotkeys_group = QGroupBox("⌨️ Atajos de Teclado")
        hotkeys_layout = QVBoxLayout(hotkeys_group)
        
        hotkeys_info = QLabel(
            "Ctrl+Shift+G → Mostrar/Ocultar overlay\n"
            "Ctrl+Shift+L → Bloquear/Mover overlay\n"
            "Ctrl+Shift+O → Abrir estas opciones"
        )
        hotkeys_info.setStyleSheet("color: #aaa; font-size: 11px;")
        hotkeys_layout.addWidget(hotkeys_info)
        
        layout.addWidget(hotkeys_group)
        
        layout.addStretch()
        
        # Cerrar scroll content
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        
        # Botón cerrar (fuera del scroll)
        close_btn = QPushButton("✓ Cerrar")
        close_btn.clicked.connect(self.close)
        main_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Cargar dispositivos inicialmente
        self._refresh_devices()
    
    def _on_setting_changed(self, key: str, value):
        self.settings.set(key, value)
        self.settings_changed.emit()
    
    def _on_device_changed(self, index: int):
        device_id = self.device_combo.currentData()
        self.settings.set('toggle_device', device_id)
        self.settings_changed.emit()
    
    def _refresh_devices(self):
        """Actualizar lista de dispositivos conectados"""
        try:
            import requests
            response = requests.get(f"{API_BASE}/api/devices", timeout=2)
            if response.status_code == 200:
                devices = response.json()
                
                # Guardar selección actual
                current = self.device_combo.currentData()
                
                # Limpiar y recargar
                self.device_combo.clear()
                self.device_combo.addItem("Cualquier Joy-Con", "any")
                
                for device in devices:
                    device_id = device.get('id', '')
                    device_type = device.get('type', '')
                    model = device.get('model', '')
                    
                    # Solo mostrar Joy-Cons
                    if 'joycon' in device_id.lower() or 'joy-con' in device_type.lower():
                        display_name = f"{model} ({device_id[-8:]})"
                        self.device_combo.addItem(display_name, device_id)
                
                # Restaurar selección si existe
                if current:
                    for i in range(self.device_combo.count()):
                        if self.device_combo.itemData(i) == current:
                            self.device_combo.setCurrentIndex(i)
                            break
        except Exception as e:
            print(f"Error actualizando dispositivos: {e}")


class GamepadOverlayV2(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Cargar configuración
        self.settings = SettingsManager()
        
        self.position = OverlayPosition.TOP_RIGHT
        self.devices: Dict[str, DeviceWidget] = {}
        self.device_colors: Dict[str, QColor] = {}  # Colores de cada dispositivo
        self.battery_history = BatteryHistory()
        self.drag_position: Optional[QPoint] = None
        self.is_locked = True
        self.is_connected = False
        self.last_devices = []
        self.show_graph = False  # Gráficas deshabilitadas (usar Vista Detallada)
        
        # Barra de colores independiente (pantalla completa arriba)
        self.top_color_bar = TopColorBar()
        if not self.settings.get('show_color_bar', True):
            self.top_color_bar.hide()
        
        # Sistema de notificaciones
        self.notification_toast = NotificationToast()
        if not self.settings.get('show_notifications', True):
            self.notification_toast.hide()
        
        # Ventana de opciones
        self.options_window = None
        
        # Ventana de vista detallada HTML
        self.detailed_view_window = None
        
        # Ventana de gestor Bluetooth
        self.bluetooth_manager_window = None
        
        self.setup_ui()
        self.setup_worker()
        self.setup_websocket()
        self.setup_button_worker()  # Worker para botones del Joy-Con
        self.setup_tray()
        self.setup_global_hotkeys()
        
        self.apply_position()
    
    def setup_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Optimizaciones para renderizado fluido
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        
        central = QWidget()
        central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCentralWidget(central)
        
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(4)
        
        # Header
        self.header = self.create_header()
        self.main_layout.addWidget(self.header)
        
        # Contenedor de dispositivos
        self.devices_container = QWidget()
        self.devices_layout = QHBoxLayout(self.devices_container)
        self.devices_layout.setContentsMargins(0, 0, 0, 0)
        self.devices_layout.setSpacing(6)
        self.main_layout.addWidget(self.devices_container)
        
        # Placeholder
        self.placeholder = QLabel("🎮 Conectando...")
        self.placeholder.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 11px;
                padding: 15px;
                background: rgba(0, 0, 0, 0.4);
                border-radius: 10px;
            }
        """)
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.devices_layout.addWidget(self.placeholder)
    
    def create_header(self) -> QWidget:
        header = HeaderWidget()
        header.setFixedHeight(28)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(6)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #ef4444; font-size: 8px; background: transparent;")
        layout.addWidget(self.status_dot)
        
        title = QLabel("Gamepad Monitor")
        title.setStyleSheet("color: white; font-size: 10px; font-weight: bold; background: transparent;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Botón Gestor Bluetooth
        self.bluetooth_btn = QLabel("📡")
        self.bluetooth_btn.setStyleSheet("font-size: 10px; background: transparent;")
        self.bluetooth_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bluetooth_btn.setToolTip("Gestor Bluetooth")
        self.bluetooth_btn.mousePressEvent = lambda e: self.show_bluetooth_manager()
        layout.addWidget(self.bluetooth_btn)
        
        # Botón opciones
        self.options_btn = QLabel("⚙️")
        self.options_btn.setStyleSheet("font-size: 10px; background: transparent;")
        self.options_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.options_btn.setToolTip("Opciones (Ctrl+Shift+O)")
        self.options_btn.mousePressEvent = lambda e: self.show_options()
        layout.addWidget(self.options_btn)
        
        # Botón vista detallada HTML
        self.detailed_btn = QLabel("📱")
        self.detailed_btn.setStyleSheet("font-size: 10px; background: transparent;")
        self.detailed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.detailed_btn.setToolTip("Vista Detallada HTML")
        self.detailed_btn.mousePressEvent = lambda e: self.show_detailed_view()
        layout.addWidget(self.detailed_btn)
        
        self.lock_btn = QLabel("🔒")
        self.lock_btn.setStyleSheet("font-size: 10px; background: transparent;")
        self.lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lock_btn.setToolTip("Bloquear/Mover (Ctrl+Shift+L)")
        self.lock_btn.mousePressEvent = lambda e: self.toggle_lock()
        layout.addWidget(self.lock_btn)
        
        close_btn = QLabel("✕")
        close_btn.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 10px;")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Ocultar")
        close_btn.mousePressEvent = lambda e: self.hide()
        layout.addWidget(close_btn)
        
        return header
    
    def setup_worker(self):
        """Configurar worker para datos de dispositivos (WebSocket con fallback HTTP)"""
        # Usar WebSocket para actualizaciones en tiempo real
        self.worker = WebSocketDataWorker()
        self.worker.data_received.connect(self.on_data_received, Qt.ConnectionType.QueuedConnection)
        self.worker.device_connected.connect(self.on_device_connected, Qt.ConnectionType.QueuedConnection)
        self.worker.device_disconnected.connect(self.on_device_disconnected_ws, Qt.ConnectionType.QueuedConnection)
        self.worker.error_occurred.connect(self.on_error, Qt.ConnectionType.QueuedConnection)
        self.worker.connection_status.connect(self.on_ws_data_connection, Qt.ConnectionType.QueuedConnection)
        self.worker.start()
    
    def play_connection_sound(self, device_type: str, model: str = ""):
        """Reproducir sonido de conexión según el tipo de dispositivo (una sola vez)"""
        if not HAS_AUDIO:
            return
        
        try:
            device_type_lower = device_type.lower()
            model_lower = model.lower()
            
            # Rutas de sonidos - buscar en varias ubicaciones
            script_dir = os.path.dirname(os.path.abspath(__file__))
            base_path = os.path.dirname(script_dir)
            
            # Intentar varias rutas posibles
            possible_paths = [
                os.path.join(base_path, "Icosns"),
                os.path.join(os.path.dirname(base_path), "Icosns"),
                r"c:\Users\teamp\Documents\joys\Icosns",
            ]
            
            sounds_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    sounds_path = p
                    break
            
            if not sounds_path:
                return
            
            nintendo_sound = os.path.join(sounds_path, "switch-sound.mp3")
            ps5_sound = os.path.join(sounds_path, "ps5-original-trophy.mp3")
            ps4_sound = os.path.join(sounds_path, "ps4-trophy.mp3")
            
            sound_file = None
            pan = 0.0  # -1.0 = izquierda, 0.0 = centro, 1.0 = derecha
            
            # Joy-Con Nintendo (detectar en type o model)
            if 'joy-con' in device_type_lower or 'joycon' in device_type_lower or 'joy-con' in model_lower or 'joycon' in model_lower:
                sound_file = nintendo_sound
                # Pan según L o R (detectar _l, (l), left, _r, (r), right en type O model)
                combined = device_type_lower + ' ' + model_lower
                if '_l' in combined or '(l)' in combined or 'left' in combined:
                    pan = -1.0  # Solo parlante izquierdo
                elif '_r' in combined or '(r)' in combined or 'right' in combined:
                    pan = 1.0   # Solo parlante derecho
            
            # PlayStation 5 - DualSense
            elif 'dualsense' in device_type_lower or 'dualsense' in model_lower or 'ps5' in model_lower or 'playstation 5' in model_lower:
                sound_file = ps5_sound
            
            # PlayStation 4 - DualShock 4 / DS4
            elif 'dualshock' in device_type_lower or 'ds4' in device_type_lower or 'dualshock' in model_lower or 'ds4' in model_lower or 'ps4' in model_lower or 'playstation 4' in model_lower:
                sound_file = ps4_sound
            
            # PlayStation genérico
            elif 'playstation' in device_type_lower or 'sony' in device_type_lower:
                sound_file = ps5_sound
            
            print(f"🔊 Sound file seleccionado: {sound_file}, pan: {pan}")
            
            if sound_file and os.path.exists(sound_file):
                # Detener cualquier sonido anterior para evitar loops
                pygame.mixer.stop()
                
                # Cargar y reproducir UNA sola vez (loops=0 es por defecto)
                sound = pygame.mixer.Sound(sound_file)
                channel = sound.play(loops=0)  # loops=0 significa reproducir solo 1 vez
                
                if channel:
                    if pan != 0.0:
                        # Ajustar volumen L/R para simular pan
                        left_vol = 1.0 if pan <= 0 else 1.0 - pan
                        right_vol = 1.0 if pan >= 0 else 1.0 + pan
                        channel.set_volume(left_vol, right_vol)
                    else:
                        channel.set_volume(1.0, 1.0)
            
        except Exception as e:
            pass  # Silenciar errores de audio
    
    def play_disconnect_sound(self, device_id: str):
        """Reproducir sonido de desconexión según el tipo de dispositivo"""
        if not HAS_AUDIO:
            return
        
        try:
            device_id_lower = device_id.lower()
            
            # Rutas de sonidos
            script_dir = os.path.dirname(os.path.abspath(__file__))
            base_path = os.path.dirname(script_dir)
            
            possible_paths = [
                os.path.join(base_path, "Icosns"),
                os.path.join(os.path.dirname(base_path), "Icosns"),
                r"c:\Users\teamp\Documents\joys\Icosns",
            ]
            
            sounds_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    sounds_path = p
                    break
            
            if not sounds_path:
                return
            
            # Usar los mismos sonidos pero con volumen más bajo
            nintendo_sound = os.path.join(sounds_path, "switch-sound.mp3")
            ps5_sound = os.path.join(sounds_path, "ps5-original-trophy.mp3")
            ps4_sound = os.path.join(sounds_path, "ps4-trophy.mp3")
            
            sound_file = None
            pan = 0.0
            volume = 0.5  # Más bajo para desconexión
            
            # Detectar tipo de dispositivo
            if 'joycon' in device_id_lower or 'joy-con' in device_id_lower:
                sound_file = nintendo_sound
                # Pan según L o R
                if '_l' in device_id_lower or '(l)' in device_id_lower:
                    pan = -1.0
                elif '_r' in device_id_lower or '(r)' in device_id_lower:
                    pan = 1.0
            elif 'dualsense' in device_id_lower:
                sound_file = ps5_sound
            elif 'dualshock' in device_id_lower or 'ds4' in device_id_lower:
                sound_file = ps4_sound
            else:
                sound_file = ps5_sound  # Default
            
            if sound_file and os.path.exists(sound_file):
                pygame.mixer.stop()
                
                sound = pygame.mixer.Sound(sound_file)
                channel = sound.play(loops=0)
                
                if channel:
                    if pan != 0.0:
                        left_vol = volume if pan <= 0 else volume * (1.0 - pan)
                        right_vol = volume if pan >= 0 else volume * (1.0 + pan)
                        channel.set_volume(left_vol, right_vol)
                    else:
                        channel.set_volume(volume, volume)
            
        except Exception as e:
            pass  # Silenciar errores de audio
    
    def on_device_connected(self, data: dict):
        """Manejar evento de nuevo dispositivo conectado vía WebSocket"""
        device_id = data.get('device_id', '')
        info = data.get('info', {})
        print(f"🎮 Nuevo dispositivo detectado vía WS: {device_id}")
        print(f"   Info recibida: {info}")
        
        # Obtener tipo y modelo - primero de info, sino deducir del device_id
        device_type = info.get('type', '')
        model = info.get('model', '')
        
        # Si no hay tipo, deducirlo del device_id
        if not device_type:
            device_id_lower = device_id.lower()
            if 'joycon_l' in device_id_lower or 'joy-con' in device_id_lower and '(l)' in device_id_lower:
                device_type = 'Joy-Con (L)'
            elif 'joycon_r' in device_id_lower or 'joy-con' in device_id_lower and '(r)' in device_id_lower:
                device_type = 'Joy-Con (R)'
            elif 'dualsense' in device_id_lower:
                device_type = 'DualSense'
            elif 'dualshock' in device_id_lower:
                device_type = 'DualShock 4'
            else:
                device_type = 'Controlador'
        
        print(f"   Tipo detectado: {device_type}")
        
        # Animar barra de color Y reproducir sonido SIMULTÁNEAMENTE
        brand_info = get_brand_info(device_type, model)
        color = QColor(brand_info['colors']['primary'])
        
        # Sonido + animación (solo si está habilitado)
        if self.settings.get('sound_connect', True):
            self.play_connection_sound(device_type, model)
        self.top_color_bar.trigger_animation(device_id, color)
        
        # Obtener nombre limpio e icono del sistema de numeración
        clean_name = DeviceNumbering.get_clean_name(device_id)
        device_icon = DeviceNumbering.get_device_icon(device_id)
        
        # Mostrar notificación
        self.notification_toast.add_notification(
            notif_type='connect',
            title=f"{device_type} Conectado",
            message=f"{clean_name} detectado",
            color=QColor("#22c55e"),
            device_id=device_id
        )
    
    def on_device_disconnected_ws(self, device_id: str):
        """Manejar evento de dispositivo desconectado vía WebSocket"""
        print(f"❌ Dispositivo desconectado vía WS: {device_id}")
        
        # Remover widget si existe
        if device_id in self.devices:
            widget = self.devices.pop(device_id)
            widget.deleteLater()
            self.adjustSize()
            self.apply_position()
        
        # Remover de la barra de color
        self.top_color_bar.remove_device(device_id)
    
    def on_ws_data_connection(self, connected: bool):
        """Manejar cambio de estado de conexión WebSocket de datos"""
        if connected:
            print("✅ WebSocket de datos conectado")
        else:
            print("⚠️ WebSocket de datos desconectado - reintentando...")
    
    def setup_websocket(self):
        """Configurar WebSocket para notificaciones en tiempo real"""
        self.ws_worker = WebSocketWorker()
        self.ws_worker.notification_received.connect(self.on_notification, Qt.ConnectionType.QueuedConnection)
        self.ws_worker.connection_changed.connect(self.on_ws_connection_changed, Qt.ConnectionType.QueuedConnection)
        self.ws_worker.start()
    
    def setup_button_worker(self):
        """Configurar worker para detectar botones del Joy-Con"""
        self.button_worker = ButtonInputWorker()
        self.button_worker.button_pressed.connect(self.on_joycon_button, Qt.ConnectionType.QueuedConnection)
        
        # Configurar botón si está habilitado
        if self.settings.get('toggle_enabled', False):
            button = self.settings.get('toggle_button', 'Capture')
            self.button_worker.set_target_button(button)
        
        self.button_worker.start()
    
    def on_joycon_button(self, button_name: str):
        """Manejar pulsación de botón del Joy-Con"""
        if self.settings.get('toggle_enabled', False):
            print(f"🎮 Botón {button_name} presionado - Toggle overlay")
            self.toggle_visibility()
    
    def show_options(self):
        """Mostrar ventana de opciones"""
        if self.options_window is None:
            self.options_window = OptionsWindow(self.settings)
            self.options_window.settings_changed.connect(self.on_settings_changed)
        
        self.options_window.show()
        self.options_window.raise_()
        self.options_window.activateWindow()
    
    def show_detailed_view(self):
        """Mostrar ventana de vista detallada HTML"""
        if not HAS_WEBENGINE:
            print("❌ PyQt6-WebEngine no instalado. Ejecuta: pip install PyQt6-WebEngine")
            return
        
        if self.detailed_view_window is None:
            self.detailed_view_window = DetailedViewWindow()
        
        self.detailed_view_window.show()
        self.detailed_view_window.raise_()
        self.detailed_view_window.activateWindow()
    
    def show_bluetooth_manager(self):
        """Mostrar ventana de gestor Bluetooth"""
        if self.bluetooth_manager_window is None:
            self.bluetooth_manager_window = BluetoothManagerWindow()
        
        self.bluetooth_manager_window.show()
        self.bluetooth_manager_window.raise_()
        self.bluetooth_manager_window.activateWindow()
    
    def on_settings_changed(self):
        """Aplicar cambios de configuración"""
        # Barra de color
        if self.settings.get('show_color_bar', True):
            self.top_color_bar.show()
        else:
            self.top_color_bar.hide()
        
        # Notificaciones
        if self.settings.get('show_notifications', True):
            self.notification_toast.show()
        else:
            self.notification_toast.hide()
        
        # Botón del Joy-Con
        if self.settings.get('toggle_enabled', False):
            button = self.settings.get('toggle_button', 'Capture')
            device = self.settings.get('toggle_device', 'any')
            self.button_worker.set_target_button(button)
            self.button_worker.set_target_device(device)
        else:
            self.button_worker.target_button = None
    
    def on_notification(self, data: dict):
        """Manejar notificación recibida del WebSocket"""
        # Solo procesar si las notificaciones están habilitadas
        if not self.settings.get('show_notifications', True):
            return
        
        msg_type = data.get('type', '')
        event_data = data.get('data', {})
        device_id = event_data.get('device_id', 'Unknown')
        
        # Obtener color del dispositivo si está disponible
        device_color = self.device_colors.get(device_id, QColor("#3b82f6"))
        
        if msg_type == 'device_disconnected':
            # Obtener nombre limpio e icono
            clean_name = DeviceNumbering.get_clean_name(device_id)
            device_icon = DeviceNumbering.get_device_icon(device_id)
            
            # Reproducir sonido de desconexión si está habilitado
            if self.settings.get('sound_disconnect', True):
                self.play_disconnect_sound(device_id)
            
            self.notification_toast.add_notification(
                notif_type='disconnect',
                title='Dispositivo Desconectado',
                message=f'{clean_name} se ha desconectado',
                color=QColor("#ef4444"),
                device_id=device_id
            )
            
            # Remover del sistema de numeración
            DeviceNumbering.remove_device(device_id)
        
        elif msg_type == 'device_reconnected':
            # Reproducir sonido de conexión
            device_type = event_data.get('type', '')
            model = event_data.get('model', '')
            # Si no viene el tipo, intentar deducirlo del device_id
            if not device_type:
                device_id_lower = device_id.lower()
                if 'joycon_l' in device_id_lower:
                    device_type = 'joycon_l'  # Usar formato que play_connection_sound entiende
                elif 'joycon_r' in device_id_lower:
                    device_type = 'joycon_r'  # Usar formato que play_connection_sound entiende
                elif 'joy-con' in device_id_lower or 'joycon' in device_id_lower:
                    device_type = 'joycon'
                elif 'dualsense' in device_id_lower:
                    device_type = 'dualsense'
                elif 'dualshock' in device_id_lower or 'ds4' in device_id_lower:
                    device_type = 'dualshock'
            
            print(f"🔊 Reproduciendo sonido para: type={device_type}, model={model}, device_id={device_id}")
            
            # Obtener color del dispositivo
            color = self.device_colors.get(device_id, QColor("#10b981"))
            
            # Sonido + Animación SIMULTÁNEOS (solo si está habilitado)
            if self.settings.get('sound_reconnect', True):
                self.play_connection_sound(device_type, model)
            self.top_color_bar.trigger_animation(device_id, color)
            
            # Obtener nombre limpio e icono
            clean_name = DeviceNumbering.get_clean_name(device_id)
            device_icon = DeviceNumbering.get_device_icon(device_id)
            
            self.notification_toast.add_notification(
                notif_type='reconnect',
                title='Dispositivo Reconectado',
                message=f'{clean_name} está de vuelta',
                color=QColor("#10b981"),
                device_id=device_id
            )
        
        elif msg_type == 'charging_change':
            is_charging = event_data.get('charging', False)
            battery = event_data.get('battery', 0)
            
            # Obtener nombre limpio e icono
            clean_name = DeviceNumbering.get_clean_name(device_id)
            device_icon = DeviceNumbering.get_device_icon(device_id)
            
            if is_charging:
                self.notification_toast.add_notification(
                    notif_type='charging',
                    title=f'{clean_name} Cargando',
                    message=f'Batería al {battery}% - Conectado a carga',
                    color=QColor("#fbbf24"),
                    device_id=device_id
                )
            else:
                self.notification_toast.add_notification(
                    notif_type='charging',
                    title=f'{clean_name} Desconectado',
                    message=f'Batería al {battery}%',
                    color=device_color,
                    device_id=device_id
                )
        
        elif msg_type == 'battery_update':
            battery = event_data.get('battery', 0)
            # Obtener nombre limpio
            clean_name = DeviceNumbering.get_clean_name(device_id)
            
            # Solo notificar si la batería está baja
            if battery <= 15:
                self.notification_toast.add_notification(
                    notif_type='low_battery',
                    title=f'¡Batería Baja! - {clean_name}',
                    message=f'Solo queda {battery}% de batería',
                    color=QColor("#ef4444"),
                    device_id=device_id
                )
    
    def on_ws_connection_changed(self, connected: bool):
        """Manejar cambio de conexión WebSocket"""
        if connected:
            print("✅ WebSocket conectado")
        else:
            print("⚠️ WebSocket desconectado")
    
    def setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#0ea5e9"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Segoe UI Emoji", 14))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🎮")
        painter.end()
        
        self.tray.setIcon(QIcon(pixmap))
        self.tray.setToolTip("Gamepad Monitor Overlay")
        
        menu = QMenu()
        
        show_action = menu.addAction("👁️ Mostrar/Ocultar")
        show_action.triggered.connect(self.toggle_visibility)
        
        menu.addSeparator()
        
        pos_menu = menu.addMenu("📍 Posición")
        positions = [
            ("↖️ Arriba Izquierda", OverlayPosition.TOP_LEFT),
            ("↗️ Arriba Derecha", OverlayPosition.TOP_RIGHT),
            ("↙️ Abajo Izquierda", OverlayPosition.BOTTOM_LEFT),
            ("↘️ Abajo Derecha", OverlayPosition.BOTTOM_RIGHT),
        ]
        for name, pos in positions:
            action = pos_menu.addAction(name)
            action.triggered.connect(lambda checked, p=pos: self.set_position(p))
        
        menu.addSeparator()
        
        # Añadir opción de vista detallada HTML
        detailed_action = menu.addAction("📱 Vista Detallada")
        detailed_action.triggered.connect(self.show_detailed_view)
        
        # Añadir opción de gestor Bluetooth
        bluetooth_action = menu.addAction("📡 Gestor Bluetooth")
        bluetooth_action.triggered.connect(self.show_bluetooth_manager)
        
        # Añadir opción de opciones
        options_action = menu.addAction("⚙️ Opciones")
        options_action.triggered.connect(self.show_options)
        
        menu.addSeparator()
        
        quit_action = menu.addAction("❌ Cerrar")
        quit_action.triggered.connect(self.close_app)
        
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.toggle_visibility() 
                                   if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()
    
    def setup_global_hotkeys(self):
        if not HAS_KEYBOARD:
            return
        try:
            keyboard.add_hotkey('ctrl+shift+g', self.toggle_visibility)
            keyboard.add_hotkey('ctrl+shift+l', self.toggle_lock)
            keyboard.add_hotkey('ctrl+shift+o', self.show_options)
            print("✅ Hotkeys globales registrados")
        except Exception as e:
            print(f"⚠️ Error registrando hotkeys: {e}")
    
    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
    
    def toggle_lock(self):
        self.is_locked = not self.is_locked
        if self.is_locked:
            self.lock_btn.setText("🔒")
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowTransparentForInput)
        else:
            self.lock_btn.setText("🔓")
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowTransparentForInput)
        self.show()
    
    def set_position(self, position: OverlayPosition):
        self.position = position
        self.apply_position()
    
    def apply_position(self):
        screen = QApplication.primaryScreen().geometry()
        margin = 20
        self.adjustSize()
        w, h = self.width(), self.height()
        
        positions = {
            OverlayPosition.TOP_LEFT: (margin, margin + 40),
            OverlayPosition.TOP_RIGHT: (screen.width() - w - margin, margin + 40),
            OverlayPosition.BOTTOM_LEFT: (margin, screen.height() - h - margin - 50),
            OverlayPosition.BOTTOM_RIGHT: (screen.width() - w - margin, screen.height() - h - margin - 50),
        }
        
        x, y = positions[self.position]
        self.move(x, y)
    
    def on_data_received(self, devices: list):
        self.last_devices = devices
        self.is_connected = True
        self.status_dot.setStyleSheet("color: #10b981; font-size: 8px;")
        
        if not devices:
            self.placeholder.setText("🎮 Sin dispositivos")
            self.placeholder.show()
            # Notificar al button worker que no hay Joy-Cons
            if hasattr(self, 'button_worker'):
                self.button_worker.set_has_joycons(False)
            return
        
        self.placeholder.hide()
        
        current_ids = set()
        has_joycons = False  # Flag para detectar si hay Joy-Cons
        
        for device_data in devices:
            device_id = device_data.get('id', '')
            current_ids.add(device_id)
            
            # Detectar si hay Joy-Cons
            if 'joycon' in device_id.lower():
                has_joycons = True
            
            # Obtener color del dispositivo
            colors_data = device_data.get('colors') or {}
            body_info = colors_data.get('body') or {}
            body_hex = body_info.get('hex')
            
            if body_hex:
                device_color = QColor(body_hex)
            else:
                # Usar color por defecto según marca
                device_type = device_data.get('type', '')
                device_name = device_data.get('name', '')
                brand_info = get_brand_info(device_type, device_name)
                device_color = QColor(brand_info['colors']['primary'])
            
            # Si es un dispositivo nuevo, crear widget y disparar animación
            if device_id not in self.devices:
                widget = DeviceWidget(self.battery_history)
                widget.set_show_graph(False)  # Gráficas deshabilitadas
                self.devices[device_id] = widget
                self.devices_layout.addWidget(widget)
                
                # Disparar animación de la barra superior (solo si está habilitada)
                if self.settings.get('show_color_bar', True):
                    self.top_color_bar.trigger_animation(device_id, device_color)
            
            self.devices[device_id].update_data(device_data)
            self.device_colors[device_id] = device_color
        
        # Notificar al button worker si hay Joy-Cons
        if hasattr(self, 'button_worker'):
            self.button_worker.set_has_joycons(has_joycons)
        
        for device_id in list(self.devices.keys()):
            if device_id not in current_ids:
                widget = self.devices.pop(device_id)
                widget.deleteLater()
                # Remover de la barra de colores
                self.top_color_bar.remove_device(device_id)
                if device_id in self.device_colors:
                    del self.device_colors[device_id]
        
        self.adjustSize()
        
        if hasattr(self, '_last_size') and self._last_size != self.size():
            self.apply_position()
        self._last_size = self.size()
    
    def on_error(self, error: str):
        self.is_connected = False
        self.status_dot.setStyleSheet("color: #ef4444; font-size: 8px;")
    
    def mousePressEvent(self, event):
        if not self.is_locked and event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if not self.is_locked and self.drag_position and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        self.drag_position = None
    
    def close_app(self):
        if hasattr(self, 'worker'):
            self.worker.stop()
            self.worker.wait(2000)
        if hasattr(self, 'ws_worker'):
            self.ws_worker.stop()
            self.ws_worker.wait(2000)
        if hasattr(self, 'button_worker'):
            self.button_worker.stop()
            self.button_worker.wait(2000)
        if HAS_KEYBOARD:
            try:
                keyboard.unhook_all()
            except:
                pass
        QApplication.quit()
    
    def closeEvent(self, event):
        self.close_app()


def main():
    # ============ Configurar argumentos de Chromium para GPU en WebEngine ============
    import os
    # Habilitar aceleración GPU para WebEngine (Chromium) con scroll suave
    chromium_flags = ' '.join([
        '--enable-gpu-rasterization',
        '--enable-accelerated-2d-canvas',
        '--ignore-gpu-blocklist',
        '--enable-smooth-scrolling',
        '--disable-frame-rate-limit',
        '--enable-zero-copy',
        '--disable-software-rasterizer',
        '--num-raster-threads=4',
        '--enable-native-gpu-memory-buffers',
        '--canvas-oop-rasterization',
        '--enable-hardware-overlays',
    ])
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = chromium_flags
    
    # ============ Configurar formato OpenGL para aceleración GPU ============
    fmt = QSurfaceFormat()
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    fmt.setSwapInterval(1)  # VSync habilitado para evitar tearing
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setSamples(4)  # Antialiasing 4x
    QSurfaceFormat.setDefaultFormat(fmt)
    
    # Habilitar high DPI ANTES de crear QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    print("=" * 50)
    print("🎮 Gamepad Monitor Overlay v2")
    print("=" * 50)
    print("🚀 GPU Acceleration: OpenGL + VSync")
    print("\nAtajos de teclado globales:")
    print("  Ctrl+Shift+G  →  Mostrar/Ocultar")
    print("  Ctrl+Shift+L  →  Bloquear/Mover")
    print("  Ctrl+Shift+O  →  Opciones")
    print("\n💡 Clic derecho en el icono del sistema para más opciones")
    
    overlay = GamepadOverlayV2()
    overlay.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
