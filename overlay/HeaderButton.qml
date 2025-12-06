import QtQuick 2.15
import QtQuick.Controls 2.15

// Botón del header estilo PyQt6
Item {
    id: root
    width: 16
    height: 16
    
    property string emoji: ""
    property string tooltipText: ""
    property color textColor: "white"
    
    signal clicked()
    
    Text {
        id: buttonText
        anchors.centerIn: parent
        text: root.emoji
        color: root.textColor
        font.pixelSize: 10
        font.family: "Segoe UI Emoji"
        
        // Animación suave de escala
        Behavior on scale {
            NumberAnimation {
                duration: 100
                easing.type: Easing.OutCubic
            }
        }
    }
    
    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        
        onClicked: root.clicked()
        
        onPressed: {
            buttonText.scale = 0.85
        }
        
        onReleased: {
            buttonText.scale = mouseArea.containsMouse ? 1.1 : 1.0
        }
        
        onEntered: {
            buttonText.scale = 1.1
            buttonText.opacity = 1.0
        }
        
        onExited: {
            buttonText.scale = 1.0
            buttonText.opacity = 0.9
        }
    }
    
    // Tooltip
    ToolTip {
        visible: mouseArea.containsMouse && root.tooltipText !== ""
        text: root.tooltipText
        delay: 500
        
        background: Rectangle {
            color: "#1e1e28"
            radius: 4
            border.color: "#333"
            border.width: 1
        }
        
        contentItem: Text {
            text: root.tooltipText
            color: "white"
            font.pixelSize: 10
            font.family: "Segoe UI"
        }
    }
}
