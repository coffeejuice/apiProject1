// Card_Upset.qml
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic

import cardmix

Card_BaseLayout {
    id: root
    // required property var listModel
    required property var a
    required property int index            // ListView's row index

    listView: ListView.view
    itemIndex: index
    imageIndex: "image4.jpg"

    Column {
        id: upsetColumn
        spacing: 6
        Row {
            spacing: 8
            Label { text: "Upsetting operations: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: a; placeholderText: "(1400)->1100->900"; onEditingFinished: listView.model.setField(index,"a",text) }
        }
    }
    // MouseArea { width: parent.width; height: implicitHeight; onClicked: view.currentIndex = index }
}
