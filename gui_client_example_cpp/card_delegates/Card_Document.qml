// Card_Document.qml
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
    required property var d
    required property var aList
    required property var bList
    required property var cList
    required property int aSelected
    required property int bSelected
    required property int cSelected
    required property int index            // ListView's row index

    listView: ListView.view
    itemIndex: index
    imageIndex: "red_danger.svg"

    Column {
        id: documentColumn
        // width: parent.width
        spacing: 6
        Label { text: "Document"; font.bold: true }
        Row {
            spacing: 8
            focus: true
            focusPolicy: Qt.StrongFocus
            onActiveFocusChanged: if (activeFocus) root.listView.currentIndex = root.itemIndex
            Label { text: "Document Number: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: a; placeholderText: "Enter document number"; onEditingFinished: listView.model.setField(index,"a",text) }
        }
        Row {
            spacing: 8
            focus: true
            focusPolicy: Qt.StrongFocus
            onActiveFocusChanged: if (activeFocus) root.listView.currentIndex = root.itemIndex
            Label { text: "Material: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: b; placeholderText: "Enter document number"; onEditingFinished: listView.model.setField(index,"b",text) }
        }
        Row {
            spacing: 8
            focus: true
            focusPolicy: Qt.StrongFocus
            onActiveFocusChanged: if (activeFocus) root.listView.currentIndex = root.itemIndex
            Label { text: "Mesh elements along width: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: c; placeholderText: "Enter document number"; onEditingFinished: listView.model.setField(index,"c",text) }
        }

        Row {
            spacing: 8
            focus: true
            focusPolicy: Qt.StrongFocus
            onActiveFocusChanged: if (activeFocus) root.listView.currentIndex = root.itemIndex
            Label { text: "Weight [kg]: "; width: 110; horizontalAlignment: Text.AlignRight }
            TextField { text: d; placeholderText: "Enter document number"; onEditingFinished: listView.model.setField(index,"d",text) }
        }

        // Selector A
        Column {
            spacing: 4
            Label { text: "Selector A:" }
            ListView {
                id: selectorA
                height: 60
                width: documentColumn.width - 20
                orientation: ListView.Horizontal
                spacing: 6
                model: aList
                interactive: listView.parent.viewInteraction
                clip: true
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: 50; height: 50
                    radius: 4
                    border.width: 2
                    border.color: index === aSelected ? "#33AA33" : "#666"
                    color: index === aSelected ? "#2233AA33" : "transparent"
                    Image {
                        anchors.fill: parent
                        fillMode: Image.PreserveAspectFit
                        source: Qt.resolvedUrl("../assets/" + modelData)
                        smooth: true
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: selectorA.interactive
                        onClicked: listView.model.setSelectorSelected(root.itemIndex, "a", index)
                    }
                }
            }
        }

        // Selector B
        Column {
            spacing: 4
            Label { text: "Selector B:" }
            ListView {
                id: selectorB
                height: 60
                width: documentColumn.width - 20
                orientation: ListView.Horizontal
                spacing: 6
                model: bList
                interactive: listView.parent.viewInteraction
                clip: true
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: 50; height: 50
                    radius: 4
                    border.width: 2
                    border.color: index === bSelected ? "#33AA33" : "#666"
                    color: index === bSelected ? "#2233AA33" : "transparent"
                    Image {
                        anchors.fill: parent
                        fillMode: Image.PreserveAspectFit
                        source: Qt.resolvedUrl("../assets/" + modelData)
                        smooth: true
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: selectorB.interactive
                        onClicked: listView.model.setSelectorSelected(root.itemIndex, "b", index)
                    }
                }
            }
        }

        // Selector C
        Column {
            spacing: 4
            Label { text: "Selector C:" }
            ListView {
                id: selectorC
                height: 60
                width: documentColumn.width - 20
                orientation: ListView.Horizontal
                spacing: 6
                model: cList
                interactive: listView.parent.viewInteraction
                clip: true
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: 50; height: 50
                    radius: 4
                    border.width: 2
                    border.color: index === cSelected ? "#33AA33" : "#666"
                    color: index === cSelected ? "#2233AA33" : "transparent"
                    Image {
                        anchors.fill: parent
                        fillMode: Image.PreserveAspectFit
                        source: Qt.resolvedUrl("../assets/" + modelData)
                        smooth: true
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: selectorC.interactive
                        onClicked: listView.model.setSelectorSelected(root.itemIndex, "c", index)
                    }
                }
            }
        }
    }
}
