// Card_BaseLayout.qml
import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: root

    property bool held: false // for mouse drag actions

    required property var imageIndex
    required property int itemIndex
    required property ItemView listView

    // Anything you put inside Card_*.qml files becomes a child of rightColumn
    default property alias details: rightColumn.data

    width: parent ? parent.width : 0
    height: content.height + 10

    enabled: root.listView.parent.viewInteraction // && (root.listView.currentIndex !== root.itemIndex)

    Rectangle {
        id: content

        property bool pointerInside: false
        readonly property bool cornerActionsVisible: pointerInside || actionPopup.visible || reorderHandler.active

        DropArea {
            anchors {
                fill: parent
                margins: 10}
            // QAbstractItemModel-based move during a drag enter over a delegate
            onEntered: (drag) => {
                const from = drag.source.index              // row of the dragged item (expose this on the drag source)
                const to = root.itemIndex                   // row of the hovered item (already available)
                if (from === undefined || to === undefined) return
                root.listView.model.moveRowTo(from, to)     // call your model’s move helper
            }
        }

        MouseArea {
            id: dragArea
            z: -1
            anchors.fill: parent
            drag.target: held ? content : undefined
            drag.axis: Drag.YAxis
            onPressAndHold: held = true
            onReleased: {
                held = false
                if (enabled) root.listView.currentIndex = root.itemIndex
                content.parent = content.Drag.target !== null ? content.Drag.target : root
            }
            hoverEnabled: true
            propagateComposedEvents: true
            acceptedButtons: enabled ? Qt.LeftButton | Qt.RightButton : Qt.NoButton
            preventStealing: enabled

            // onPressed: if (enabled) content.color = "gray"
            onEntered: if (enabled) content.pointerInside = true
            onExited: if (enabled) content.pointerInside = false
            onCanceled: content.pointerInside = false
            onEnabledChanged: if (!enabled) content.pointerInside = false
        }

        states: State {
            when: root.held

            ParentChange {
                target: content
                parent: root.listView.parent
            }
            AnchorChanges {
                target: content
                anchors {horizontalCenter: undefined; verticalCenter: undefined}
            }
        }

        // Provide drag meta so DropArea can accept and reorder
        Drag.active: root.held
        Drag.source: root
        Drag.hotSpot.x: width / 2 // reorderHandler.centroid.position.x    // use scene position of handler centroid
        Drag.hotSpot.y: height / 2 // reorderHandler.centroid.position.y
        // Drag.mimeData: ({ "application/x-item-index": root.itemIndex })
        // Drag.dragType: Drag.Automatic
        // Drag.supportedActions: Qt.MoveAction | Qt.CopyAction
        // (No Drag.dragDelegate here to avoid the error)

        z: 1
        x: 5; y: 5
        anchors {
            horizontalCenter: parent.horizontalCenter
            verticalCenter: parent.verticalCenter}
        height: Math.max(left.height, rightColumn.height) + 10
        width: root.width - 10

        border.width: 1
        border.color: "lightsteelblue"
        color: root.held ? "lightsteelblue" : "white"
        Behavior on color { ColorAnimation { duration: 100 } }
        radius: 5

        // Left image
        Rectangle {
            id: left
            width: 50; height: 50; x: 5; y: 5
            color: "transparent"
            Image {
                anchors.fill: parent
                fillMode: Image.PreserveAspectFit
                source: Qt.resolvedUrl("../assets/" + root.imageIndex)
                smooth: true
            }
            Rectangle {
                width: 10; height: 20
                color: "white"
                Label {anchors.top: parent.top; anchors.left: parent.left; text: itemIndex}
            }

        }

        // Corner action row (plus + dots)
        Row {
            id: cornerActions
            spacing: 6
            anchors.top: content.top
            anchors.right: content.right
            anchors.topMargin: 15
            anchors.rightMargin: 10
            z: 2
            visible: content.cornerActionsVisible
            opacity: visible ? 1 : 0
            Behavior on opacity {
                NumberAnimation {
                    duration: 120
                    easing.type: Easing.OutQuad
                }
            }

            Item {
                id: plusIconOverlay
                width: 18
                height: 18

                // Position overlay exactly where the dots icon is
                // anchors.verticalCenter: parent.verticalCenter
                // anchors.right: dragGripOverlay.left
                // anchors.rightMargin: 5

                Image {
                    id: plusIcon
                    anchors.fill: parent
                    source: Qt.resolvedUrl("../assets/plus.svg")
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    antialiasing: true
                }

                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    gesturePolicy: TapHandler.DragThreshold
                    onTapped: actionPopup.open()
                    onPressedChanged: plusIcon.opacity = pressed ? 0.7 : 1
                    cursorShape: Qt.PointingHandCursor
                }
            }

            // Transparent overlay exactly on top of the dots icon to capture drag,
            // so the visible icon never moves.
            Item {
                id: dragGripOverlay
                width: 18
                height: 18

                // Position overlay exactly where the dots icon is
                // anchors.verticalCenter: parent.verticalCenter
                // anchors.right: parent.right

                // Visible icon (not moved by handler)
                Image {
                    id: dotsIcon
                    anchors.fill: parent
                    source: Qt.resolvedUrl("../assets/dots.svg")
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    antialiasing: true
                }

                // Capture drag on the overlay only
                DragHandler {
                    id: reorderHandler
                    target: content    // do not move any visual item
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchScreen
                    acceptedButtons: Qt.LeftButton
                    grabPermissions: PointerHandler.CanTakeOverFromAnything
                    cursorShape: active ? Qt.ClosedHandCursor : Qt.OpenHandCursor

                    onActiveChanged: {
                        if (active) {
                            root.Drag.start()
                        } else {
                            root.Drag.drop()
                            // Ensure no accumulated translation on overlay
                            reorderHandler.translation = Qt.point(0, 0)
                        }
                    }
                }
            }
        }

        // Right content
        Rectangle {
            id: right
            anchors.left: left.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 5
            color: "#333"
            border.color: Qt.lighter(color, 1.2)

            Column {
                id: rightColumn
                spacing: 6
            }
        }

        // The popup opened by the plus icon
        Popup {
            id: actionPopup
            x: parent.width - width - 5
            y: cornerActions.y + cornerActions.height + 4
            modal: false
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            contentItem: Rectangle {
                implicitWidth: 180
                implicitHeight: 90
                radius: 8
                color: "#ffffff"
                border.color: "#bfc4cc"
                Text {
                    text: "Hello from item " + index
                    anchors.centerIn: parent
                }
            }
        }
    }
}
