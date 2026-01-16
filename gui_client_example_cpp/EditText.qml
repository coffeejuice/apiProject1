// DynamicTextField.qml
import QtQuick
import QtQuick.Controls

Item {
    id: root
    required property string text

    width: field.width
    height: field.height

    Rectangle {
        anchors.fill: parent
        radius: 3
        color: field.enabled ? "transparent" : "#353637"
        border.color: field.enabled ? "#21be2b" : "transparent"
        border.width: (field.focus || field.hovered) ? 1 : 0
    }

    TextField {
        id: field
        text: root.text
        placeholderText: qsTr("0")
        readOnly: false
        padding: 2
        leftPadding: 2
        rightPadding: 2
        width: contentWidth + leftPadding + rightPadding
        anchors.margins: 2
        hoverEnabled: true       // this one is valid here
        color: "black"
        background: null

        Keys.onReturnPressed: {
            root.focusNextField(index, 0)    // row index, column 0
        }
    }
}
