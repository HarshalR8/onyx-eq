import QtQuick
import QtQuick.Controls.Basic
import "../theme"

// Round button showing a text glyph: "power", "undo", "redo", "more", "plus", "close", or any literal text.
AbstractButton {
    id: control
    property string glyph: "more"
    property color tint: Theme.textPrimary
    property color fill: Theme.surface2
    implicitWidth: Theme.controlHeight
    implicitHeight: Theme.controlHeight
    hoverEnabled: true
    focusPolicy: Qt.NoFocus
    opacity: enabled ? 1 : 0.35

    background: Rectangle {
        radius: width / 2
        color: control.fill
        opacity: control.down ? 0.7 : control.hovered ? 0.9 : 1
    }
    contentItem: Item {
        Text {
            anchors.centerIn: parent
            text: ({ "power": "⏻", "undo": "↶", "redo": "↷", "more": "•••",
                     "plus": "+", "close": "✕", "chevron": "⌄" })[control.glyph] || control.glyph
            color: control.tint
            font.family: Theme.fontFamily
            font.pixelSize: control.glyph === "more" ? Theme.smallSize : Theme.headlineSize
            font.weight: Theme.weightSemibold
        }
    }
}
