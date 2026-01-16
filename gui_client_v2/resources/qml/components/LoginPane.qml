import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    Layout.preferredWidth: 250
    Layout.minimumWidth: 220
    Layout.preferredHeight: 180

    Column {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        Text {
            text: "Login"
            font.bold: true
            font.pixelSize: 14
        }

        TextField {
            width: parent.width - 20
            placeholderText: "Username"
            text: authViewModel.username
            onTextChanged: authViewModel.username = text
        }

        TextField {
            width: parent.width - 20
            placeholderText: "Password"
            text: authViewModel.password
            echoMode: TextField.Password
            onTextChanged: authViewModel.password = text
        }

        Button {
            width: parent.width - 20
            text: "LOGIN"
            onClicked: {
                console.log("LOGIN CLICKED: " + authViewModel.username)
                authViewModel.login()
            }
        }

        Text {
            width: parent.width - 20
            text: authViewModel.isLoggedIn ? "Status: Connected" : authViewModel.errorMessage
            color: authViewModel.isLoggedIn ? "green" : "red"
            font.pixelSize: 10
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
