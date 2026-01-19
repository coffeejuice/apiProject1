// Cell.qml
import QtQuick
import QtQuick.Controls

Row {
    id: root
    required property int index
    required property var repeaterAlias

    required property string angleValue
    required property string heightValue

    Text { text: " (" }
    EditText { text: angleValue }
    Text { text: "°)" }
    EditText { text: heightValue }
    Text { text: index < repeaterAlias.count - 1 ? " →" : "" }
}
