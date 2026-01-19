// CardView.qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    anchors.fill: parent
    required property CardModel cardModelAlias

    Column {
        id: leftPannel
        Layout.alignment: Qt.AlignTop
        width: implicitWidth
        Text { text: qsTr("Manage cards:"); font.bold: true}
        Button { text: qsTr("Append Card"); onClicked: lv.model++}
        Button { text: qsTr("Remove Card"); onClicked: lv.model--; enabled: lv.currentIndex >= 0 }
        // Button { text: qsTr("Draw"); onClicked: lv.model.appendCard("draw")}

    }
    ListView {
        id: lv
        anchors {
            left: leftPannel.right
            right: parent.right
        }
        height: parent.height
        spacing: 6
        focus: true
        highlight: Rectangle {color: Qt.rgba(0,0,0,0.06)}
        model: cardModelAlias
        delegate: DelegateChooser {
            role: "cardType"
            DelegateChoice { roleValue: CardModel.IMAGE;      delegate: Draw {} }
            DelegateChoice { roleValue: CardModel.GRAPHIC;    delegate: Draw {} }
            DelegateChoice { roleValue: CardModel.DOCUMENT;   delegate: Draw {} }
            DelegateChoice { roleValue: CardModel.BLOCK;      delegate: Draw {} }
            DelegateChoice { roleValue: CardModel.HEAT;       delegate: Draw {} }
            DelegateChoice { roleValue: CardModel.UPSET;      delegate: Draw {} }
            DelegateChoice { roleValue: CardModel.DRAW;       delegate: Draw {} }
        }
    }
}
