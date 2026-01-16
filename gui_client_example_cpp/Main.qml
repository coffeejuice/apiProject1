// Main.qml
import QtQuick

Window {
    id: root
    width: 1000
    height: 800
    visible: true
    title: qsTr("Nested Flow")

    required property CardModel cardModel

    CardView {
        cardModelAlias: cardModel
    }
}
