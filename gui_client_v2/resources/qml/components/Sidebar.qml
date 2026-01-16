import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        Text {
            text: "Documents"
            font.bold: true
            font.pixelSize: 14
            Layout.fillWidth: true
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Column {
                width: 230
                spacing: 5

                Repeater {
                    model: documentListViewModel.documents
                    delegate: Button {
                        width: 230
                        height: 40
                        text: modelData.title
                        highlighted: modelData.process_id === documentListViewModel.currentDocId
                        onClicked: documentListViewModel.selectDocument(modelData.process_id)
                    }
                }
            }
        }
    }
}
