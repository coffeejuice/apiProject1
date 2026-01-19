// Card_Footer.qml
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: footerRect

    height: Math.max(0,
                     blocksView.height
                     - (blocksView.headerItem ? blocksView.headerItem.height : 0)
                     - blocksView.lastItem
                     )
    width: parent ? parent.width : 0
    // border.color: "black"
    // color: "mistyrose"
    Rectangle {
        id: footerAddNew
        x: 5; y: 5
        height: labelAddNew.implicitHeight + 10
        width: parent.width - 10
        radius: 5
        border.color: "gray"
        Label {
            id: labelAddNew
            anchors.centerIn: parent
            text: "+"
        }
    }
}
