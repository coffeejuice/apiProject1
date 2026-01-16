// Card_Header.qml
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic

import cardmix

Rectangle {
    id: root
    required property var imageIndex
    required property int itemIndex
    required property ItemView listView
    // required property var blockContent
    // required property int index            // ListView's row index

    // listView: ListView.view
    // itemIndex: index
    imageIndex: "check_list_bw.svg"

    width: parent ? parent.width : 0
    height: contourRect.height + 10
    z: blocksView.z + 2

    Rectangle {
        id: contourRect

        width: parent.width - 10
        height: Math.max(left.height, rightColumn.height) + 10
        y: 5
        x: 5
        radius: 5
        border.color: "gray"

        // Left image
        Rectangle {
            id: left
            width: 50; height: 50; x: 5; y: 5
            color: "transparent"
            Image {
                anchors.fill: parent
                fillMode: Image.PreserveAspectFit
                source: Qt.resolvedUrl("../assets/" + root.imageIndex)
                smooth: true
            }
        }

        // Right content
        Rectangle {
            id: right
            anchors.left: left.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 5
            color: "#333"
            border.color: Qt.lighter(color, 1.2)

            Column {
                id: rightColumn
                spacing: 6
                Label { text: "Document"; font.bold: true }
                // Label { text: "Document Number: " + (blockContent?.documentNumber ?? "") }
                // Label { text: "Material: " + (blockContent?.material ?? "") }
                // Label { text: "Mesh density: " + (blockContent?.meshDensity ?? "") }
            }
        }

        // MouseArea {
        //     anchors.fill: parent
        //     hoverEnabled: true
        //     enabled: root.listView.parent.viewInteraction
        //
        //     onReleased: {
        //         root.listView.currentIndex = root.itemIndex
        //         contourRect.color = "white"
        //     }
        //
        //     onPressed: {
        //         contourRect.color = "gray"
        //     }
        //
        //     onEntered: {
        //         contourRect.color = "lightgray"
        //     }
        //
        //     onExited: {
        //         contourRect.color = "white"
        //     }
        // }
    }
}
