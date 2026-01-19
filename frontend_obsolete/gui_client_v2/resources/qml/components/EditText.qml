import QtQuick 2.15
import QtQuick.Controls 2.15
import ".."

FocusScope {
    id: root
    width: 200 // Default width, usually overridden or auto-sized
    height: 40
    
    property alias text: input.text
    property alias placeholderText: input.placeholderText
    property alias color: input.color
    property alias font: input.font
    property alias readOnly: input.readOnly
    
    // Auto-size width to content if needed, though usually handled by layout
    implicitWidth: Math.max(100, input.contentWidth + 20)
    implicitHeight: 40

    Rectangle {
        id: background
        anchors.fill: parent
        color: Theme.inputBackground
        border.color: input.activeFocus || root.activeFocus ? Theme.primary : Theme.inputBorder
        border.width: input.activeFocus || root.activeFocus ? 2 : 1
        radius: 4
        
        // Dynamic visual feedback (e.g. slight glow or shadow could go here)
    }

    TextField {
        id: input
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        
        color: Theme.text
        font.pixelSize: Theme.fontSizeBody
        
        verticalAlignment: Text.AlignVCenter
        
        background: Item {} // Remove default background
        
        onActiveFocusChanged: {
            if (activeFocus) root.forceActiveFocus()
        }
    }
}
