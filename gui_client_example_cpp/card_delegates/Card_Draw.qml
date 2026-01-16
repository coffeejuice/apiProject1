// Card_Draw.qml
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic

import cardmix

Card_BaseLayout {
    id: root
    // required property var blockContent
    // required property var listModel
    required property var a
    required property int index            // ListView's row index

    listView: ListView.view
    itemIndex: index
    imageIndex: "image1.jpg"

    Column {
        id: drawColumn
        spacing: 6
        Row {
            spacing: 8
            Label { text: "Drawing operations: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: a; placeholderText: "(500)->450->(90)480->(45)435"; onEditingFinished: listView.model.setField(index,"a",text) }
        }
    }
    // MouseArea { width: parent.width; height: implicitHeight; onClicked: view.currentIndex = index }
}
