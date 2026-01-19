// Card_Heat.qml
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic

import cardmix

Card_BaseLayout {
    id: root
    // required property var blockContent
    // required property var listModel
    required property var a
    required property var b
    required property var c
    required property int index            // ListView's row index

    listView: ListView.view
    itemIndex: index
    imageIndex: "fire.svg"

    Column {
        id: heatColumn
        spacing: 6
        Label { text: "Heat"; font.bold: true }
        Row {
            spacing: 8
            Label { text: "Heat Number: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: a; placeholderText: "Enter heat number"; onEditingFinished: listView.model.setField(index,"a",text) }
        }
        Row {
            spacing: 8
            Label { text: "Time units: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: b; placeholderText: "day/hour/min/sec"; onEditingFinished: listView.model.setField(index,"b",text) }
        }
        Row {
            spacing: 8
            Label { text: "Temperature table [time/temp.]: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: c; placeholderText: "0, 980; 350, 980"; onEditingFinished: listView.model.setField(index,"c",text) }
        }
    }
    // MouseArea { width: parent.width; height: implicitHeight; onClicked: view.currentIndex = index }
}
