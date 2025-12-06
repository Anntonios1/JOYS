"""
Gamepad Monitor - GUI con PyQt6
Aplicación de escritorio simple con consola de debug y estado de servicios
"""

import sys
import os
import threading
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QTextEdit, QPushButton, QLabel, QHBoxLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor
import uvicorn
import socket
from datetime import datetime


def get_resource_path(relative_path):
    """Obtener ruta absoluta de recursos (funciona empaquetado y no empaquetado)"""
    try:
        # PyInstaller crea una carpeta temporal en _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Modo desarrollo
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


class ServerThread(QThread):
    """Thread para correr el servidor FastAPI"""
    log_signal = pyqtSignal(str)
    
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.running = True
    
    def run(self):
        """Ejecutar servidor FastAPI"""
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        self.log_signal.emit("✅ Servidor FastAPI iniciado en puerto 8000")
        server.run()
    
    def stop(self):
        """Detener servidor"""
        self.running = False
        self.quit()
        self.wait()


class GamepadMonitorGUI(QMainWindow):
    """Ventana principal de la aplicación"""
    
    def __init__(self):
        super().__init__()
        self.server_thread = None
        self.init_ui()
        self.start_server()
        
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        self.setWindowTitle("🎮 Gamepad Monitor Pro")
        self.setGeometry(100, 100, 800, 600)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # === HEADER ===
        header_layout = QHBoxLayout()
        
        title_label = QLabel("🎮 Gamepad Monitor Pro")
        title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Estado del servidor
        self.status_label = QLabel("⚫ Detenido")
        status_font = QFont("Segoe UI", 10)
        self.status_label.setFont(status_font)
        header_layout.addWidget(self.status_label)
        
        layout.addLayout(header_layout)
        
        # === INFORMACIÓN DEL SERVIDOR ===
        info_layout = QVBoxLayout()
        
        # IP Local
        local_ip = self.get_local_ip()
        self.ip_label = QLabel(f"📡 Servidor Local: http://localhost:8000")
        self.ip_label.setFont(QFont("Segoe UI", 10))
        info_layout.addWidget(self.ip_label)
        
        self.network_label = QLabel(f"🌐 Red Local: http://{local_ip}:8000")
        self.network_label.setFont(QFont("Segoe UI", 10))
        info_layout.addWidget(self.network_label)
        
        layout.addLayout(info_layout)
        
        # === BOTONES DE ACCIÓN ===
        buttons_layout = QHBoxLayout()
        
        self.open_browser_btn = QPushButton("🌐 Abrir en Navegador")
        self.open_browser_btn.clicked.connect(self.open_browser)
        self.open_browser_btn.setMinimumHeight(40)
        buttons_layout.addWidget(self.open_browser_btn)
        
        self.clear_log_btn = QPushButton("🗑️ Limpiar Log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.clear_log_btn.setMinimumHeight(40)
        buttons_layout.addWidget(self.clear_log_btn)
        
        layout.addLayout(buttons_layout)
        
        # === ESTADÍSTICAS ===
        stats_layout = QHBoxLayout()
        
        self.devices_label = QLabel("📱 Dispositivos: 0")
        self.devices_label.setFont(QFont("Segoe UI", 10))
        stats_layout.addWidget(self.devices_label)
        
        self.ws_label = QLabel("🔌 WebSockets: 0")
        self.ws_label.setFont(QFont("Segoe UI", 10))
        stats_layout.addWidget(self.ws_label)
        
        self.cache_label = QLabel("💾 Caché: 0 entradas")
        self.cache_label.setFont(QFont("Segoe UI", 10))
        stats_layout.addWidget(self.cache_label)
        
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)
        
        # === CONSOLA DE DEBUG ===
        log_label = QLabel("📋 Consola de Debug:")
        log_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.log_text)
        
        # Timer para actualizar estadísticas
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(5000)  # Cada 5 segundos
        
        # Aplicar estilos
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QLabel {
                color: #333;
            }
        """)
    
    def get_local_ip(self):
        """Obtener IP local de la máquina"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "localhost"
    
    def start_server(self):
        """Iniciar servidor FastAPI en thread separado"""
        try:
            # Agregar ruta de api_v2 al path
            api_v2_path = get_resource_path('api_v2')
            if api_v2_path not in sys.path:
                sys.path.insert(0, api_v2_path)
            
            # Importar la app de FastAPI
            from main import app, device_manager, active_websockets
            
            self.app = app
            self.device_manager = device_manager
            self.active_websockets = active_websockets
            
            # Crear y arrancar thread del servidor
            self.server_thread = ServerThread(app)
            self.server_thread.log_signal.connect(self.append_log)
            self.server_thread.start()
            
            # Actualizar estado
            self.status_label.setText("🟢 Servidor Activo")
            self.status_label.setStyleSheet("color: #107c10; font-weight: bold;")
            
            self.append_log("="*60)
            self.append_log("🎮 Gamepad Monitor Pro v2.0")
            self.append_log("="*60)
            self.append_log(f"📅 Iniciado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.append_log(f"📡 Servidor: http://localhost:8000")
            self.append_log(f"🌐 Red Local: http://{self.get_local_ip()}:8000")
            self.append_log(f"📖 API Docs: http://localhost:8000/docs")
            self.append_log("="*60)
            self.append_log("")
            
        except Exception as e:
            self.append_log(f"❌ Error iniciando servidor: {e}")
            self.status_label.setText("🔴 Error")
            self.status_label.setStyleSheet("color: #d13438; font-weight: bold;")
    
    def append_log(self, message):
        """Agregar mensaje al log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Auto-scroll al final
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_log(self):
        """Limpiar consola de debug"""
        self.log_text.clear()
        self.append_log("🗑️ Log limpiado")
    
    def open_browser(self):
        """Abrir frontend en navegador"""
        webbrowser.open("http://localhost:8000")
        self.append_log("🌐 Frontend abierto en navegador")
    
    def update_stats(self):
        """Actualizar estadísticas en tiempo real"""
        try:
            if hasattr(self, 'device_manager'):
                devices_count = len(self.device_manager.devices)
                self.devices_label.setText(f"📱 Dispositivos: {devices_count}")
                
                ws_count = len(self.active_websockets)
                self.ws_label.setText(f"🔌 WebSockets: {ws_count}")
                
                cache_stats = self.device_manager.cache.get_stats()
                cache_entries = cache_stats.get('total_entries', 0)
                self.cache_label.setText(f"💾 Caché: {cache_entries} entradas")
        except Exception as e:
            pass
    
    def closeEvent(self, event):
        """Manejar cierre de aplicación"""
        self.append_log("🛑 Cerrando aplicación...")
        
        if self.server_thread:
            self.server_thread.stop()
        
        event.accept()


def main():
    """Punto de entrada de la aplicación"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = GamepadMonitorGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
