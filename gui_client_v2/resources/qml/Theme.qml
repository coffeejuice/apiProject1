import QtQuick 2.15

pragma Singleton

QtObject {
    // Colors
    readonly property color background: "#0F172A"
    readonly property color surface: "#1E293B"
    readonly property color primary: "#38BDF8"
    readonly property color accent: "#818CF8"
    readonly property color text: "#F8FAFC"
    readonly property color textSecondary: "#94A3B8"
    readonly property color border: "#334155"
    readonly property color inputBackground: "#FFFFFF" 
    readonly property color inputBorder: "#000000"
    readonly property color inputText: "#000000"

    // Spacing
    readonly property int paddingLarge: 24
    readonly property int paddingMedium: 16
    readonly property int paddingSmall: 8

    // Typography
    readonly property int fontSizeTitle: 24
    readonly property int fontSizeHeader: 18
    readonly property int fontSizeBody: 14
    readonly property int fontSizeSmall: 12

    // Borders
    readonly property int radius: 8
}
