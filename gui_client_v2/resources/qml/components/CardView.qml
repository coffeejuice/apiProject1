// CardView.qml - Matching C++ client implementation
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import ".."

Item {
    id: root
    anchors.fill: parent

    required property var cardModelAlias

    Component.onCompleted: {
        console.log("CardView loaded")
        console.log("cardModelAlias:", cardModelAlias)
        console.log("cardModelAlias type:", typeof cardModelAlias)
        if (cardModelAlias) {
            console.log("cardModelAlias length:", cardModelAlias.length)
        }
    }

    // Left panel - simple Column with standard buttons
    Column {
        id: leftPanel
        x: 10
        y: 10
        width: 120
        spacing: 10

        Text {
            text: "Manage cards:"
            font.bold: true
        }

        Button {
            text: "Append Card"
            width: parent.width
            onClicked: {
                console.log("Append Card clicked")
                console.log("processViewModel:", processViewModel)
                if (processViewModel) {
                    console.log("Calling insertBlock...")
                    processViewModel.insertBlock("text", "")
                } else {
                    console.log("ERROR: processViewModel is undefined!")
                }
            }
        }

        Button {
            text: "Remove Card"
            width: parent.width
            enabled: lv.currentIndex >= 0
            onClicked: {
                console.log("Remove Card clicked")
                if (processViewModel && lv.currentIndex >= 0) {
                    processViewModel.removeBlock(lv.currentIndex)
                }
            }
        }

        Component.onCompleted: {
            console.log("leftPanel loaded")
        }
    }

    ListView {
        id: lv
        anchors {
            left: leftPanel.right
            leftMargin: 20
            right: parent.right
            top: parent.top
            bottom: parent.bottom
        }
        spacing: 6
        focus: true
        clip: true

        highlight: Rectangle {
            color: Qt.rgba(0, 0, 0, 0.06)
        }

        model: cardModelAlias

        delegate: Draw {
            width: lv.width
            viewModel: modelData
        }

        Component.onCompleted: {
            console.log("ListView loaded")
            console.log("ListView anchors - left:", leftPanel.right, "right:", parent.right)
            console.log("ListView size:", width, "x", height)
            console.log("ListView model:", model)
            console.log("ListView count:", count)
        }

        onCountChanged: {
            console.log("ListView count changed to:", count)
        }
    }
}
