import QtQuick
import QtQuick.Controls.Basic
import "../theme"

ToolTip {
    id: tip
    delay: 600
    timeout: 5000
    font.family: Theme.fontFamily
    font.pixelSize: Theme.captionSize
    padding: Theme.spacingS
    contentItem: Text {
        text: tip.text
        font: tip.font
        color: Theme.textPrimary
    }
    background: Rectangle {
        radius: Theme.radiusSmall
        color: Theme.surface2
        border.width: 1
        border.color: Theme.hairline
    }
}
