import QtQuick 2.15
import QtQuick.Layouts 1.15
import ".."

Rectangle {
    property var viewModel: null
    Layout.fillWidth: true
    height: 40
    color: "#450A0A"
    border.color: "#EF4444"
    radius: 4

    Text {
        anchors.centerIn: parent
        text: "Unknown Block Type: " + (viewModel ? viewModel.block_type : "???")
        color: "#FEE2E2"
    }
}
