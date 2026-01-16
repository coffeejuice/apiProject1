import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components" // Correct path for EditText
import ".."

ColumnLayout {
    property var viewModel: null
    spacing: 5

    EditText {
        Layout.fillWidth: true
        text: viewModel ? viewModel.text : ""
        placeholderText: "Type something..."

        // Two-way binding
        onTextChanged: {
            if (viewModel && viewModel.text !== text) {
                viewModel.text = text
            }
        }
    }
}
