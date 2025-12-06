import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

// 🎮 Overlay QML v3 - Réplica del PyQt6
ApplicationWindow {
    id: mainWindow
    visible: true
    width: mainColumn.width + 16
    height: mainColumn.height + 16
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    
    // Propiedades
    property bool isLocked: true
    property var devices: []
    property bool isConnected: devices.length > 0
    property bool wsConnected: false
    
    // Posición
    x: controller ? controller.posX : 100
    y: controller ? controller.posY : 100
    
    // Conexiones al controller Python
    Connections {
        target: controller
        
        function onDevicesChanged() {
            mainWindow.devices = controller.devices
            console.log("Devices updated:", mainWindow.devices.length)
        }
        
        function onLockStateChanged() {
            mainWindow.isLocked = controller.isLocked
        }
        
        function onConnectionChanged() {
            mainWindow.wsConnected = controller.isConnected
        }
    }
    
    Component.onCompleted: {
        if (controller) {
            mainWindow.devices = controller.devices
            mainWindow.isLocked = controller.isLocked
            mainWindow.wsConnected = controller.isConnected
        }
        // Animación de entrada
        entryAnim.start()
    }
    
    // Animación de entrada
    ParallelAnimation {
        id: entryAnim
        NumberAnimation {
            target: mainColumn
            property: "opacity"
            from: 0; to: 1
            duration: 300
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: mainColumn
            property: "scale"
            from: 0.9; to: 1.0
            duration: 350
            easing.type: Easing.OutBack
        }
    }
    
    // Drag para mover
    MouseArea {
        anchors.fill: parent
        enabled: !mainWindow.isLocked
        property point clickPos
        
        onPressed: function(mouse) {
            clickPos = Qt.point(mouse.x, mouse.y)
        }
        
        onPositionChanged: function(mouse) {
            if (pressed) {
                mainWindow.x += mouse.x - clickPos.x
                mainWindow.y += mouse.y - clickPos.y
            }
        }
        
        onReleased: {
            if (controller) {
                controller.updatePosition(mainWindow.x, mainWindow.y)
            }
        }
    }
    
    // Contenedor principal
    Column {
        id: mainColumn
        x: 8
        y: 8
        spacing: 4
        
        // ============ HEADER ============
        Rectangle {
            id: header
            width: Math.max(devicesRow.childrenRect.width + 12, 180)
            height: 28
            radius: 8
            color: "#dc1e1e28"
            
            Behavior on width {
                NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
            }
            
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 6
                
                // Status dot
                Rectangle {
                    width: 6; height: 6; radius: 3
                    color: mainWindow.isConnected ? "#10b981" : (mainWindow.wsConnected ? "#fbbf24" : "#ef4444")
                    
                    Behavior on color {
                        ColorAnimation { duration: 300 }
                    }
                    
                    SequentialAnimation on opacity {
                        running: mainWindow.wsConnected
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.5; duration: 1000 }
                        NumberAnimation { to: 1.0; duration: 1000 }
                    }
                }
                
                // Título
                Text {
                    text: "Gamepad Monitor"
                    color: "white"
                    font.pixelSize: 10
                    font.weight: Font.Bold
                    font.family: "Segoe UI"
                }
                
                Item { Layout.fillWidth: true }
                
                // Botones
                HeaderButton {
                    emoji: "📡"
                    tooltipText: "Bluetooth"
                    onClicked: controller.openBluetoothManager()
                }
                
                HeaderButton {
                    emoji: "⚙️"
                    tooltipText: "Opciones"
                    onClicked: controller.openSettings()
                }
                
                HeaderButton {
                    emoji: "📱"
                    tooltipText: "Vista Detallada"
                    onClicked: controller.openDetailedView()
                }
                
                HeaderButton {
                    emoji: mainWindow.isLocked ? "🔒" : "🔓"
                    tooltipText: mainWindow.isLocked ? "Desbloquear" : "Bloquear"
                    onClicked: controller.toggleLock()
                }
                
                HeaderButton {
                    emoji: "✕"
                    tooltipText: "Ocultar"
                    textColor: "#99ffffff"
                    onClicked: mainWindow.hide()
                }
            }
        }
        
        // ============ DISPOSITIVOS ============
        Row {
            id: devicesRow
            spacing: 6
            
            // Placeholder
            Rectangle {
                id: placeholder
                visible: mainWindow.devices.length === 0
                width: 170
                height: 55
                radius: 10
                color: "#66000000"
                
                Text {
                    anchors.centerIn: parent
                    text: mainWindow.wsConnected ? "🎮 Sin dispositivos" : "🎮 Conectando..."
                    color: "#99ffffff"
                    font.pixelSize: 11
                    font.family: "Segoe UI"
                }
            }
            
            // Dispositivos
            Repeater {
                id: devicesRepeater
                model: mainWindow.devices
                
                delegate: DeviceCard {
                    deviceData: modelData
                    cardIndex: index
                }
            }
        }
    }
}
