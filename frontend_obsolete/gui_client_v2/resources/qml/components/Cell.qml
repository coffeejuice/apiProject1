// Cell.qml - Matching C++ client implementation
import QtQuick 2.15
import QtQuick.Controls 2.15

Row {
    id: root
    required property int index
    required property var repeaterAlias

    required property string angleValue
    required property string heightValue

    spacing: 2

    Text {
        text: " ("
        color: "black"
        font.pixelSize: 14
        verticalAlignment: Text.AlignVCenter
    }

    TextField {
        text: angleValue
        width: 60
        implicitHeight: 30
        font.pixelSize: 14

        onEditingFinished: {
            // Update model when editing is finished
            if (repeaterAlias.model) {
                repeaterAlias.model.setData(
                    repeaterAlias.model.index(index, 0),
                    text,
                    repeaterAlias.model.AngleValueRole
                )
            }
        }
    }

    Text {
        text: "°)"
        color: "black"
        font.pixelSize: 14
        verticalAlignment: Text.AlignVCenter
    }

    TextField {
        text: heightValue
        width: 80
        implicitHeight: 30
        font.pixelSize: 14

        onEditingFinished: {
            // Update model when editing is finished
            if (repeaterAlias.model) {
                repeaterAlias.model.setData(
                    repeaterAlias.model.index(index, 0),
                    text,
                    repeaterAlias.model.HeightValueRole
                )
            }
        }
    }

    Text {
        text: index < repeaterAlias.count - 1 ? " →" : ""
        color: "gray"
        font.pixelSize: 14
        verticalAlignment: Text.AlignVCenter
    }
}
