// Draw.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: lvDelegate
    width: lv.implicitWidth
    height: lvContent.implicitHeight
    Column {
        width: implicitWidth
        id: lvContent
        RowLayout {
            id: lvButtons
            x: 10
            Text { text: qsTr("Manage items:"); font.bold: true}
            Button { text: qsTr("+"); onClicked: rp.model++}
            Button { text: qsTr("-"); onClicked: rp.model--; enabled: rp.count>=0}
        }
        Flow {
            id: flow
            x: 10
            width: root.width - leftPannel.width - 10
            Repeater {
                id: rp
                model: model.cellModel  // 'model.cellModel' is a role, but this role represent the c++ model
                delegate: Cell { repeaterAlias: rp }  //angleValue: String("90"); heightValue: String(100 + index * 50); repeaterAlias: rp}
            }
        }
    }
}
