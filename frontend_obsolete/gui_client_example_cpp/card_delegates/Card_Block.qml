// Card_Block.qml
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic

import cardmix

Card_BaseLayout {
    id: root
    // required property var listModel
    required property var a
    required property var b
    required property var c
    required property var d
    required property var e
    required property var f
    required property var g
    required property var h
    required property var i
    required property var j
    required property var k
    required property var l
    required property int index            // ListView's row index

    listView: ListView.view
    itemIndex: index
    imageIndex: "blocktype_unknown_yellow_inkspace.svg"

    Column {
        id: blockColumn
        spacing: 6
        Label { text: "Begin Block"; font.bold: true }
        Row {
            spacing: 8
            Label { text: "Block Number: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: a; placeholderText: "Enter block number"; onEditingFinished: listView.model.setField(index,"a",text) }
        }
        Row {
            spacing: 8
            Label { text: "Press ID: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: b; placeholderText: "Enter press name"; onEditingFinished: listView.model.setField(index,"b",text) }
        }
        Row {
            spacing: 8
            Label { text: "Die assembly ID: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: c; placeholderText: "Enter die assembly name"; onEditingFinished: listView.model.setField(index,"c",text) }
        }
        Row {
            spacing: 8
            Label { text: "Top die ID: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: d; placeholderText: "Enter die name"; onEditingFinished: listView.model.setField(index,"d",text) }
        }
        Row {
            spacing: 8
            Label { text: "Bottom die ID: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: e; placeholderText: "Enter die name"; onEditingFinished: listView.model.setField(index,"e",text) }
        }
        Row {
            spacing: 8
            Label { text: "Feed direction ID: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: f; placeholderText: "Enter <-- or -->"; onEditingFinished: listView.model.setField(index,"f",text) }
        }
        Row {
            spacing: 8
            Label { text: "Feed first [mm]: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: g; placeholderText: "Enter feed"; onEditingFinished: listView.model.setField(index,"g",text) }
        }
        Row {
            spacing: 8
            Label { text: "Feed middle [mm]: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: h; placeholderText: "Enter feed"; onEditingFinished: listView.model.setField(index,"h",text) }
        }
        Row {
            spacing: 8
            Label { text: "Feed last [mm]: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: i; placeholderText: "Enter feed"; onEditingFinished: listView.model.setField(index,"i",text) }
        }
        Row {
            spacing: 8
            Label { text: "Speed upsetting [mm]: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: j; placeholderText: "Enter speed"; onEditingFinished: listView.model.setField(index,"j",text) }
        }
        Row {
            spacing: 8
            Label { text: "Speed prolongation [mm]: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: k; placeholderText: "Enter speed"; onEditingFinished: listView.model.setField(index,"k",text) }
        }
        Row {
            spacing: 8
            Label { text: "Speed full die [mm]: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: l; placeholderText: "Enter speed"; onEditingFinished: listView.model.setField(index,"l",text) }
        }
    }
    // MouseArea { width: parent.width; height: implicitHeight; onClicked: view.currentIndex = index }
}
