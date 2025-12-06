import QtQuick 2.15
import QtQuick.Controls 2.15

// 🎮 DeviceCard - Réplica del DeviceWidget PyQt6 (170x55 compacto)
Rectangle {
    id: root
    width: 170
    height: 55
    radius: 12
    
    property var deviceData: ({})
    property int cardIndex: 0
    
    // Extraer datos de forma segura
    property string deviceName: {
        if (deviceData && typeof deviceData.name !== 'undefined') 
            return deviceData.name
        return "Unknown"
    }
    
    property string deviceId: {
        if (deviceData && typeof deviceData.id !== 'undefined') 
            return deviceData.id
        return ""
    }
    
    property real batteryPercent: {
        if (deviceData && deviceData.battery && typeof deviceData.battery.percentage !== 'undefined')
            return deviceData.battery.percentage
        return 0
    }
    
    property bool isCharging: {
        if (deviceData && deviceData.battery && typeof deviceData.battery.charging !== 'undefined')
            return deviceData.battery.charging
        return false
    }
    
    property real pollingRate: {
        if (deviceData && deviceData.polling && typeof deviceData.polling.rate_hz !== 'undefined')
            return deviceData.polling.rate_hz
        return 0
    }
    
    property string connectionType: {
        if (deviceData && typeof deviceData.connection_type !== 'undefined' && deviceData.connection_type)
            return deviceData.connection_type
        return ""
    }
    
    property real usageHours: {
        if (deviceData && typeof deviceData.usage_time_hours !== 'undefined')
            return deviceData.usage_time_hours
        return 0
    }
    
    property real usageMinutes: {
        if (deviceData && typeof deviceData.usage_time_minutes !== 'undefined')
            return deviceData.usage_time_minutes
        return 0
    }
    
    property real autonomyHours: {
        if (deviceData && typeof deviceData.estimated_autonomy_hours !== 'undefined' && deviceData.estimated_autonomy_hours)
            return deviceData.estimated_autonomy_hours
        return 0
    }
    
    property int playerNumber: {
        if (deviceData && typeof deviceData.player_number !== 'undefined' && deviceData.player_number)
            return deviceData.player_number
        return 0
    }
    
    // Color del cuerpo desde API o fallback
    property color bodyColor: {
        var id = deviceId.toLowerCase()
        
        // Joy-Cons: SOLO usar color de API (sin fallback hardcodeado)
        if (id.indexOf("joycon") >= 0 || id.indexOf("joy-con") >= 0) {
            if (deviceData && deviceData.colors && deviceData.colors.body && deviceData.colors.body.hex) {
                return deviceData.colors.body.hex
            }
            return "#0ea5e9"  // Fallback genérico si no hay API
        }
        
        // Otros mandos: color fijo según tipo
        if (id.indexOf("dualshock") >= 0 || id.indexOf("ds4") >= 0) {
            return "#003087"  // DS4 azul PS4 oscuro
        } else if (id.indexOf("dualsense") >= 0 || id.indexOf("ds5") >= 0) {
            return "#1a1a2e"  // DualSense color original
        } else if (id.indexOf("xbox") >= 0) {
            return "#107c10"
        }
        
        // Fallback genérico
        return "#0ea5e9"
    }
    
    property color buttonColor: Qt.darker(bodyColor, 1.2)
    
    // Batería animada
    property real animatedBattery: batteryPercent
    Behavior on animatedBattery {
        NumberAnimation { duration: 800; easing.type: Easing.OutCubic }
    }
    
    // Pulso para carga
    property real pulseValue: 0
    SequentialAnimation on pulseValue {
        running: root.isCharging
        loops: Animation.Infinite
        NumberAnimation { to: 1; duration: 1000; easing.type: Easing.InOutSine }
        NumberAnimation { to: 0; duration: 1000; easing.type: Easing.InOutSine }
    }
    
    // Gradiente de fondo
    gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0.0; color: Qt.rgba(root.bodyColor.r, root.bodyColor.g, root.bodyColor.b, 0.9) }
        GradientStop { position: 1.0; color: Qt.rgba(root.buttonColor.r, root.buttonColor.g, root.buttonColor.b, 0.75) }
    }
    
    // Borde sutil
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.15)
    
    // ============ ICONO ============
    Image {
        id: brandIcon
        x: 6
        y: 10
        width: 20
        height: 20
        fillMode: Image.PreserveAspectFit
        smooth: true
        antialiasing: true
        mipmap: true
        sourceSize: Qt.size(40, 40)  // 2x para nitidez
        source: {
            var id = root.deviceId.toLowerCase()
            if (id.indexOf("joycon") >= 0 || id.indexOf("joy-con") >= 0) {
                return "nintendo_white.svg"
            } else if (id.indexOf("dualsense") >= 0 || id.indexOf("dualshock") >= 0) {
                return "ps_icon_white.svg"
            } else if (id.indexOf("xbox") >= 0) {
                return "Xbox_one_logo.svg.png"
            }
            return "ps_icon_white.svg"
        }
    }
    
    // Fallback emoji si no carga imagen
    Text {
        id: iconFallback
        x: 8
        y: 8
        visible: brandIcon.status !== Image.Ready
        text: {
            var id = root.deviceId.toLowerCase()
            if (id.indexOf("joycon") >= 0 || id.indexOf("joy-con") >= 0) return "🕹️"
            if (id.indexOf("dualsense") >= 0) return "🎮"
            return "🎮"
        }
        font.pixelSize: 16
        font.family: "Segoe UI Emoji"
    }
    
    // ============ NOMBRE ============
    Text {
        id: nameText
        x: 32
        y: 6
        width: 90
        text: {
            var n = root.deviceName
            return n.replace("DualShock 4", "DS4").replace("DualSense", "DS5")
        }
        color: "white"
        font.pixelSize: 9
        font.weight: Font.Bold
        font.family: "Segoe UI"
        elide: Text.ElideRight
    }
    
    // ============ POLLING + CONEXIÓN ============
    Text {
        id: pollingText
        x: 32
        y: 18
        text: {
            var txt = ""
            if (root.pollingRate > 0) txt = root.pollingRate.toFixed(0) + "Hz"
            var conn = root.connectionType.toLowerCase()
            if (conn.indexOf("bluetooth") >= 0 || conn.indexOf("bt") >= 0) txt += " 📶"
            else if (conn.indexOf("usb") >= 0) txt += " 🔌"
            return txt.trim()
        }
        color: Qt.rgba(1, 1, 1, 0.7)
        font.pixelSize: 7
        font.family: "Segoe UI"
    }
    
    // ============ TIEMPO DE USO ============
    Text {
        id: usageText
        x: 32
        y: 28
        visible: root.usageHours > 0 || root.usageMinutes > 0
        text: root.usageHours >= 1 ? "⏱ " + root.usageHours.toFixed(1) + "h" : "⏱ " + Math.floor(root.usageMinutes) + "m"
        color: Qt.rgba(1, 1, 1, 0.8)
        font.pixelSize: 7
        font.family: "Segoe UI"
    }
    
    // ============ CONSUMO POR HORA ============
    Text {
        id: consumptionText
        x: 90
        y: 28
        visible: root.batteryPercent > 0 && root.usageHours > 0
        text: {
            var consumption = (100 - root.batteryPercent) / root.usageHours
            return "📉 " + consumption.toFixed(1) + "%/h"
        }
        color: Qt.rgba(1, 1, 1, 0.6)
        font.pixelSize: 7
        font.family: "Segoe UI"
    }
    
    // ============ BATERÍA CIRCULAR ============
    Item {
        id: batteryContainer
        x: parent.width - 44
        y: 6
        width: 38
        height: 38
        
        Canvas {
            id: batteryCanvas
            anchors.fill: parent
            
            property real battery: root.animatedBattery
            property real pulse: root.pulseValue
            property bool charging: root.isCharging
            
            onBatteryChanged: requestPaint()
            onPulseChanged: if (charging) requestPaint()
            
            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                
                var centerX = width / 2
                var centerY = height / 2
                var radius = 15
                
                // Fondo gris
                ctx.beginPath()
                ctx.arc(centerX, centerY, radius, 0, Math.PI * 2)
                ctx.strokeStyle = "rgba(255, 255, 255, 0.2)"
                ctx.lineWidth = 4
                ctx.stroke()
                
                // Color según nivel
                var batteryColor = "#10b981" // verde
                if (battery < 50) batteryColor = "#fbbf24" // amarillo
                if (battery < 20) batteryColor = "#ef4444" // rojo
                
                // Glow si cargando
                if (charging) {
                    ctx.beginPath()
                    var span = (battery / 100) * Math.PI * 2
                    ctx.arc(centerX, centerY, radius, -Math.PI / 2, -Math.PI / 2 + span)
                    ctx.strokeStyle = Qt.rgba(0.3, 1, 0.5, 0.3 + 0.3 * pulse)
                    ctx.lineWidth = 8
                    ctx.lineCap = "round"
                    ctx.stroke()
                }
                
                // Arco de batería
                ctx.beginPath()
                var span2 = (battery / 100) * Math.PI * 2
                ctx.arc(centerX, centerY, radius, -Math.PI / 2, -Math.PI / 2 + span2)
                ctx.strokeStyle = batteryColor
                ctx.lineWidth = 4
                ctx.lineCap = "round"
                ctx.stroke()
            }
        }
        
        // Porcentaje
        Text {
            anchors.centerIn: parent
            text: Math.floor(root.animatedBattery)
            color: "white"
            font.pixelSize: 10
            font.weight: Font.Bold
            font.family: "Segoe UI"
        }
        
        // Icono de carga
        Text {
            visible: root.isCharging
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.rightMargin: -2
            anchors.topMargin: -2
            text: "⚡"
            font.pixelSize: 10
            opacity: 0.5 + 0.5 * root.pulseValue
        }
    }
    
    // ============ INDICADORES DE JUGADOR (Joy-Con) ============
    Row {
        id: playerLights
        x: 8
        y: parent.height - 12
        spacing: 3
        visible: {
            var id = root.deviceId.toLowerCase()
            return (id.indexOf("joycon") >= 0 || id.indexOf("joy-con") >= 0) && root.playerNumber > 0
        }
        
        Repeater {
            model: 4
            Rectangle {
                width: 6
                height: 6
                radius: 1  // Cuadrados con esquinas ligeramente redondeadas (como Joy-Con real)
                
                // Patrones LED según jugador (1-8)
                property bool ledOn: {
                    var pnum = root.playerNumber
                    if (pnum === 1) return index === 0  // LED 1
                    if (pnum === 2) return index <= 1   // LED 1,2
                    if (pnum === 3) return index <= 2   // LED 1,2,3
                    if (pnum === 4) return true         // LED 1,2,3,4
                    if (pnum === 5) return index === 0 || index === 3  // LED 1,4
                    if (pnum === 6) return index <= 1   // LED 1,2 (parpadeo)
                    if (pnum === 7) return index === 0 || index === 2 || index === 3  // LED 1,3,4
                    if (pnum === 8) return index === 1 || index === 2  // LED 2,3
                    return false
                }
                
                color: ledOn ? "white" : "transparent"
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.3)
                
                // Parpadeo para jugador 6
                opacity: (root.playerNumber === 6 && ledOn) ? (0.3 + 0.7 * blinkAnim.blinkValue) : 1.0
                
                Behavior on color {
                    ColorAnimation { duration: 200 }
                }
            }
        }
    }
    
    // Animación de parpadeo para jugador 6
    Item {
        id: blinkAnim
        property real blinkValue: 0
        
        SequentialAnimation on blinkValue {
            running: root.playerNumber === 6
            loops: Animation.Infinite
            NumberAnimation { to: 1; duration: 500; easing.type: Easing.InOutSine }
            NumberAnimation { to: 0; duration: 500; easing.type: Easing.InOutSine }
        }
    }
}
