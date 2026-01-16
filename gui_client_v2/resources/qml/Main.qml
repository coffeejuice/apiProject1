import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "./components"

ApplicationWindow {
    visible: true
    width: 1280
    height: 800
    title: "Techno-Notion Client v2"

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Left Pane (Login + Document List)
        ColumnLayout {
            Layout.fillHeight: true
            Layout.preferredWidth: 250
            Layout.minimumWidth: 250
            Layout.maximumWidth: 250
            spacing: 0

            LoginPane {
                Layout.fillWidth: true
            }

            Sidebar {
                Layout.fillHeight: true
                Layout.fillWidth: true
            }
        }

        // Right Pane (C++ Client Style - Card/Block Editor)
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "white"

            CardView {
                anchors.fill: parent
                cardModelAlias: processViewModel.blocks
            }
        }
    }

    Component.onCompleted: {
        processViewModel.load()
    }
}
