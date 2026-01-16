// Draw.qml - Matching C++ client implementation
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: lvDelegate
    width: ListView.view ? ListView.view.width : 800
    height: lvContent.implicitHeight

    property var viewModel: null

    Column {
        width: parent.width
        id: lvContent

        RowLayout {
            id: lvButtons
            x: 10
            width: parent.width - 20

            Text {
                text: qsTr("Manage items:")
                font.bold: true
                color: "black"
            }

            Button {
                text: qsTr("+")
                width: 40
                height: 30
                onClicked: {
                    if (viewModel) {
                        viewModel.addCell("90", "100")
                    }
                }
            }

            Button {
                text: qsTr("-")
                width: 40
                height: 30
                enabled: rp.count > 0
                onClicked: {
                    if (viewModel && rp.count > 0) {
                        viewModel.removeCell(rp.count - 1)
                    }
                }
            }
        }

        Flow {
            id: flow
            x: 10
            width: parent.width - 20
            spacing: 4

            Repeater {
                id: rp
                model: viewModel ? viewModel.cellModel : null
                delegate: Cell {
                    repeaterAlias: rp
                }
            }
        }
    }
}
