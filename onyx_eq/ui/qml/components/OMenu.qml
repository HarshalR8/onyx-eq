import QtQuick
import QtQuick.Controls.Basic
import "../theme"

Menu {
    id: menu
    padding: Theme.spacingXs + 2
    font.family: Theme.fontFamily
    font.pixelSize: Theme.bodySize - 1
    delegate: MenuItem {
        id: item
        implicitHeight: Theme.controlHeight
        implicitWidth: 220
        hoverEnabled: true
        contentItem: Text {
            leftPadding: Theme.spacingS + (item.checkable ? Theme.spacingM : 0)
            text: item.text
            font: menu.font
            color: !item.enabled ? Theme.textTertiary
                 : (item.action && item.action.destructive) ? Theme.destructive : Theme.textPrimary
            verticalAlignment: Text.AlignVCenter
        }
        indicator: Text {
            visible: item.checked
            x: Theme.spacingS
            anchors.verticalCenter: parent.verticalCenter
            text: "✓"
            color: Theme.accent
            font: menu.font
        }
        arrow: Text {
            visible: item.subMenu
            x: item.width - width - Theme.spacingS
            anchors.verticalCenter: parent.verticalCenter
            text: "›"
            color: Theme.textSecondary
            font: menu.font
        }
        background: Rectangle {
            radius: Theme.radiusSmall
            color: item.highlighted ? Theme.surface3 : "transparent"
        }
    }
    background: Rectangle {
        implicitWidth: 220
        radius: Theme.radiusControl
        color: Theme.surface
        border.width: 1
        border.color: Theme.hairline
    }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.durationFast } }
}
