"""
🎮 Gamepad Monitor Overlay
Overlay estilo Xbox Game Bar para monitorear Joy-Cons en tiempo real

Requisitos:
    pip install PyQt6 aiohttp

Uso:
    python gamepad_overlay.py
    
Atajos:
    Ctrl+Shift+G - Mostrar/Ocultar overlay
    Ctrl+Shift+M - Mover overlay (arrastrando)
    Ctrl+Shift+Q - Cerrar overlay
"""

import sys
import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSystemTrayIcon, QMenu, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPoint, QPropertyAnimation,
    QEasingCurve, QSize
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen, QLinearGradient,
    QIcon, QAction, QKeySequence, QShortcut, QPainterPath, QPixmap
)

import aiohttp


# ============ Configuration ============
API_BASE = "http://localhost:8000"
UPDATE_INTERVAL = 5000  # ms (5 seconds for display, battery comes from scheduler)
OVERLAY_OPACITY = 0.92


# ============ API Worker Thread ============
class APIWorker(QThread):
    """Thread para consultar la API sin bloquear la UI"""
    data_received = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = True
    
    def run(self):
        """Loop principal del worker"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                devices = loop.run_until_complete(self.fetch_devices())
                self.data_received.emit(devices)
            except Exception as e:
                self.error_occurred.emit(str(e))
            
            # Sleep en el thread
            self.msleep(UPDATE_INTERVAL)
        
        loop.close()
    
    async def fetch_devices(self) -> list:
        """Obtener datos de dispositivos desde la API"""
        devices = []
        
        async with aiohttp.ClientSession() as session:
            # Obtener lista de dispositivos
            async with session.get(f"{API_BASE}/api/devices") as resp:
                if resp.status == 200:
                    device_list = await resp.json()
                    
                    # Obtener info detallada de cada dispositivo
                    for device in device_list:
                        device_id = device.get('id')
                        if device_id:
                            async with session.get(f"{API_BASE}/api/device/{device_id}") as detail_resp:
                                if detail_resp.status == 200:
                                    info = await detail_resp.json()
                                    devices.append(info)
        
        return devices
    
    def stop(self):
        self.running = False


# ============ Device Widget ============
class DeviceWidget(QWidget):
    """Widget individual para cada dispositivo"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_data: Optional[Dict[str, Any]] = None
        self.body_color = QColor("#0ea5e9")  # Default cyan
        self.button_color = QColor("#0284c7")
        self.setMinimumSize(280, 90)
        self.setMaximumSize(320, 110)
    
    def update_data(self, data: Dict[str, Any]):
        """Actualizar datos del dispositivo"""
        self.device_data = data
        
        # Extraer colores del SPI
        colors = data.get('colors', {})
        body_hex = colors.get('body', {}).get('hex', '#0ea5e9')
        button_hex = colors.get('buttons', {}).get('hex', '#0284c7')
        
        self.body_color = QColor(body_hex)
        self.button_color = QColor(button_hex)
        
        self.update()  # Trigger repaint
    
    def paintEvent(self, event):
        """Dibujar el widget personalizado"""
        if not self.device_data:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dimensiones
        w, h = self.width(), self.height()
        margin = 8
        
        # ===== Fondo con glassmorphism =====
        path = QPainterPath()
        path.addRoundedRect(margin, margin, w - 2*margin, h - 2*margin, 16, 16)
        
        # Gradiente con color del Joy-Con
        gradient = QLinearGradient(0, 0, w, h)
        color1 = QColor(self.body_color)
        color1.setAlpha(180)
        color2 = QColor(self.body_color)
        color2.setAlpha(100)
        color3 = QColor(self.button_color)
        color3.setAlpha(80)
        
        gradient.setColorAt(0, color1)
        gradient.setColorAt(0.5, color2)
        gradient.setColorAt(1, color3)
        
        painter.fillPath(path, QBrush(gradient))
        
        # Borde sutil
        border_color = QColor(self.body_color)
        border_color.setAlpha(150)
        painter.setPen(QPen(border_color, 1.5))
        painter.drawPath(path)
        
        # ===== Efecto gloss en la parte superior =====
        gloss_path = QPainterPath()
        gloss_path.addRoundedRect(margin, margin, w - 2*margin, (h - 2*margin) / 2, 16, 16)
        
        gloss_gradient = QLinearGradient(0, margin, 0, h/2)
        gloss_gradient.setColorAt(0, QColor(255, 255, 255, 40))
        gloss_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillPath(gloss_path, QBrush(gloss_gradient))
        
        # ===== Información del dispositivo =====
        battery = self.device_data.get('battery', {})
        battery_pct = battery.get('percentage', 0)
        charging = battery.get('charging', False)
        voltage = battery.get('voltage', 0)
        
        polling = self.device_data.get('polling', {})
        polling_rate = polling.get('rate_hz', 0)
        
        name = self.device_data.get('name', 'Unknown')
        is_left = '(L)' in name or self.device_data.get('side') == 'Left'
        
        # ===== Icono del Joy-Con =====
        icon_rect_x = margin + 12
        icon_rect_y = margin + 15
        icon_size = 45
        
        # Fondo del icono
        icon_gradient = QLinearGradient(icon_rect_x, icon_rect_y, 
                                         icon_rect_x + icon_size, icon_rect_y + icon_size)
        icon_gradient.setColorAt(0, self.body_color)
        icon_gradient.setColorAt(1, self.button_color)
        
        icon_path = QPainterPath()
        icon_path.addRoundedRect(icon_rect_x, icon_rect_y, icon_size, icon_size, 10, 10)
        painter.fillPath(icon_path, QBrush(icon_gradient))
        
        # Emoji del Joy-Con
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Segoe UI Emoji", 22))
        painter.drawText(icon_rect_x, icon_rect_y, icon_size, icon_size, 
                        Qt.AlignmentFlag.AlignCenter, "🕹️" if is_left else "🎮")
        
        # ===== Texto del nombre =====
        text_x = icon_rect_x + icon_size + 12
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.drawText(text_x, margin + 22, name)
        
        # ===== Batería =====
        battery_y = margin + 40
        
        # Icono de batería/carga
        painter.setFont(QFont("Segoe UI Emoji", 10))
        battery_icon = "⚡" if charging else "🔋"
        painter.drawText(text_x, battery_y, battery_icon)
        
        # Barra de batería
        bar_x = text_x + 22
        bar_width = 80
        bar_height = 14
        
        # Fondo de la barra
        bar_bg = QPainterPath()
        bar_bg.addRoundedRect(bar_x, battery_y - 11, bar_width, bar_height, 4, 4)
        painter.fillPath(bar_bg, QBrush(QColor(0, 0, 0, 80)))
        
        # Barra de progreso
        if battery_pct > 0:
            fill_width = (bar_width - 4) * (battery_pct / 100)
            bar_fill = QPainterPath()
            bar_fill.addRoundedRect(bar_x + 2, battery_y - 9, fill_width, bar_height - 4, 3, 3)
            
            # Color según nivel
            if battery_pct >= 75:
                bar_color = QColor("#10b981")  # Green
            elif battery_pct >= 25:
                bar_color = QColor("#fbbf24")  # Yellow
            else:
                bar_color = QColor("#ef4444")  # Red
            
            painter.fillPath(bar_fill, QBrush(bar_color))
        
        # Porcentaje
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(bar_x + bar_width + 8, battery_y, f"{battery_pct}%")
        
        # ===== Stats inferiores =====
        stats_y = margin + 62
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(255, 255, 255, 200))
        
        stats_text = []
        if voltage > 0:
            stats_text.append(f"⚡ {voltage:.2f}V")
        if polling_rate > 0:
            stats_text.append(f"📊 {polling_rate:.1f}Hz")
        
        painter.drawText(text_x, stats_y, "  •  ".join(stats_text))
        
        # ===== Línea de acento superior =====
        accent_path = QPainterPath()
        accent_path.addRoundedRect(margin + 2, margin, w - 2*margin - 4, 3, 2, 2)
        
        accent_gradient = QLinearGradient(margin, 0, w - margin, 0)
        accent_gradient.setColorAt(0, self.body_color)
        accent_gradient.setColorAt(1, self.button_color)
        painter.fillPath(accent_path, QBrush(accent_gradient))


# ============ Main Overlay Window ============
class GamepadOverlay(QMainWindow):
    """Ventana principal del overlay"""
    
    def __init__(self):
        super().__init__()
        
        self.devices: Dict[str, DeviceWidget] = {}
        self.drag_position: Optional[QPoint] = None
        self.is_locked = True  # Locked = click-through
        
        self.setup_ui()
        self.setup_worker()
        self.setup_tray()
        self.setup_shortcuts()
        
        # Posición inicial (esquina superior derecha)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 20, 80)
    
    def setup_ui(self):
        """Configurar la interfaz"""
        # Flags de ventana para overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # No aparece en taskbar
        )
        
        # Fondo transparente
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Widget central
        central = QWidget()
        self.setCentralWidget(central)
        
        # Layout principal
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)
        
        # Header minimalista
        self.header = self.create_header()
        self.main_layout.addWidget(self.header)
        
        # Contenedor de dispositivos
        self.devices_container = QWidget()
        self.devices_layout = QVBoxLayout(self.devices_container)
        self.devices_layout.setContentsMargins(0, 0, 0, 0)
        self.devices_layout.setSpacing(4)
        self.main_layout.addWidget(self.devices_container)
        
        # Placeholder mientras carga
        self.placeholder = QLabel("🎮 Conectando...")
        self.placeholder.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 12px;
                padding: 20px;
            }
        """)
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.devices_layout.addWidget(self.placeholder)
        
        self.setMinimumWidth(300)
        self.adjustSize()
    
    def create_header(self) -> QWidget:
        """Crear header del overlay"""
        header = QWidget()
        header.setFixedHeight(28)
        header.setStyleSheet("""
            QWidget {
                background: rgba(0, 0, 0, 0.5);
                border-radius: 8px;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 4, 12, 4)
        
        # Título
        title = QLabel("🎮 Gamepad Monitor")
        title.setStyleSheet("color: white; font-size: 11px; font-weight: bold;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Indicador de estado
        self.status_label = QLabel("●")
        self.status_label.setStyleSheet("color: #10b981; font-size: 10px;")
        layout.addWidget(self.status_label)
        
        # Botón de lock/unlock
        self.lock_btn = QLabel("🔒")
        self.lock_btn.setStyleSheet("font-size: 12px; cursor: pointer;")
        self.lock_btn.mousePressEvent = lambda e: self.toggle_lock()
        layout.addWidget(self.lock_btn)
        
        return header
    
    def setup_worker(self):
        """Configurar el worker de API"""
        self.worker = APIWorker()
        self.worker.data_received.connect(self.on_data_received)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()
    
    def setup_tray(self):
        """Configurar el icono de sistema"""
        self.tray = QSystemTrayIcon(self)
        
        # Crear icono simple
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#0ea5e9"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Segoe UI Emoji", 12))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🎮")
        painter.end()
        
        self.tray.setIcon(QIcon(pixmap))
        self.tray.setToolTip("Gamepad Monitor Overlay")
        
        # Menú del tray
        menu = QMenu()
        
        show_action = QAction("Mostrar/Ocultar", self)
        show_action.triggered.connect(self.toggle_visibility)
        menu.addAction(show_action)
        
        lock_action = QAction("Bloquear/Desbloquear", self)
        lock_action.triggered.connect(self.toggle_lock)
        menu.addAction(lock_action)
        
        menu.addSeparator()
        
        quit_action = QAction("Cerrar", self)
        quit_action.triggered.connect(self.close_app)
        menu.addAction(quit_action)
        
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()
    
    def setup_shortcuts(self):
        """Configurar atajos de teclado globales"""
        # Nota: Los shortcuts globales requieren bibliotecas adicionales
        # Por ahora usamos shortcuts locales cuando la ventana tiene foco
        pass
    
    def toggle_visibility(self):
        """Mostrar/ocultar overlay"""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
    
    def toggle_lock(self):
        """Bloquear/desbloquear para mover"""
        self.is_locked = not self.is_locked
        
        if self.is_locked:
            self.lock_btn.setText("🔒")
            # Click-through cuando está bloqueado
            self.setWindowFlags(
                self.windowFlags() | Qt.WindowType.WindowTransparentForInput
            )
        else:
            self.lock_btn.setText("🔓")
            # Permitir interacción cuando está desbloqueado
            self.setWindowFlags(
                self.windowFlags() & ~Qt.WindowType.WindowTransparentForInput
            )
        
        self.show()  # Necesario después de cambiar flags
    
    def on_tray_activated(self, reason):
        """Manejar clic en el tray"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()
    
    def on_data_received(self, devices: list):
        """Procesar datos recibidos de la API"""
        self.status_label.setStyleSheet("color: #10b981; font-size: 10px;")
        
        if not devices:
            self.placeholder.setText("🎮 Sin dispositivos")
            self.placeholder.show()
            return
        
        self.placeholder.hide()
        
        # Actualizar o crear widgets de dispositivos
        current_ids = set()
        
        for device_data in devices:
            device_id = device_data.get('id', '')
            current_ids.add(device_id)
            
            if device_id not in self.devices:
                # Crear nuevo widget
                widget = DeviceWidget()
                self.devices[device_id] = widget
                self.devices_layout.addWidget(widget)
            
            # Actualizar datos
            self.devices[device_id].update_data(device_data)
        
        # Eliminar dispositivos desconectados
        for device_id in list(self.devices.keys()):
            if device_id not in current_ids:
                widget = self.devices.pop(device_id)
                widget.deleteLater()
        
        self.adjustSize()
    
    def on_error(self, error: str):
        """Manejar errores de la API"""
        self.status_label.setStyleSheet("color: #ef4444; font-size: 10px;")
        print(f"API Error: {error}")
    
    def mousePressEvent(self, event):
        """Iniciar arrastre"""
        if not self.is_locked and event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Mover ventana"""
        if not self.is_locked and event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """Finalizar arrastre"""
        self.drag_position = None
    
    def close_app(self):
        """Cerrar aplicación"""
        self.worker.stop()
        self.worker.wait()
        self.tray.hide()
        QApplication.quit()
    
    def closeEvent(self, event):
        """Manejar cierre de ventana"""
        event.ignore()
        self.hide()  # Ocultar en lugar de cerrar


# ============ Main ============
def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # No cerrar al ocultar ventana
    
    # Estilo global
    app.setStyle("Fusion")
    
    overlay = GamepadOverlay()
    overlay.show()
    
    print("🎮 Gamepad Monitor Overlay iniciado")
    print("   • Clic derecho en el icono del sistema para opciones")
    print("   • Clic en 🔒 para desbloquear y mover")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
