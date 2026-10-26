import QtQuick
import QtQuick.Controls.Basic
import "../theme"

// Pill button. `role`: "plain" (surface), "accent", "destructive", "ghost" (text only).
Button {
    id: control
    property string role: "plain"
    property bool compact: false
    property color tint: role === "accent" ? Theme.accent : role === "destructive" ? Theme.destructive : Theme.textPrimary

    implicitHeight: compact ? Theme.controlHeightSmall : Theme.controlHeight
    implicitWidth: Math.max(implicitHeight, contentItem.implicitWidth + (compact ? Theme.spacingM : Theme.spacingL))
    padding: 0
    hoverEnabled: true
    font.family: Theme.fontFamily
    font.pixelSize: compact ? Theme.captionSize + 1 : Theme.bodySize
    font.weight: Theme.weightMedium
    focusPolicy: Qt.NoFocus

    contentItem: Text {
        text: control.text
        font: control.font
        color: !control.enabled ? Theme.textTertiary
             : control.role === "accent" ? Theme.textPrimary
             : control.role === "ghost" ? Theme.accent
             : control.tint
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: height / 2
        color: control.role === "ghost" ? (control.hovered ? Theme.surface : "transparent")
             : control.role === "accent" ? Theme.accent
             : control.checked ? Theme.surface3 : Theme.surface2
        opacity: control.down ? 0.7 : control.hovered && control.role !== "ghost" ? 0.9 : 1
        Behavior on opacity { NumberAnimation { duration: Theme.durationFast } }
    }
}
