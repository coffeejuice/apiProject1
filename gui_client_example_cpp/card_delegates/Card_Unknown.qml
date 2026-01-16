// Card_Unknown.qml
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic

import cardmix

Card_BaseLayout {
    id: root
    // required property var blockContent
    required property int index            // ListView's row index

    listView: ListView.view
    itemIndex: index
    imageIndex: "blocktype_unknown_yellow_inkspace.svg"

    Column {
        spacing: 6
        Label { text: "Unknown type: " + String(blockContent.type) ; font.bold: true }
        Text { text: JSON.stringify(obj, null, 2); font.family: "monospace" }
    }
}
