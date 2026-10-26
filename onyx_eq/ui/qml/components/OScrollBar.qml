import QtQuick
import QtQuick.Controls.Basic
import "../theme"

ScrollBar {
    id: bar
    policy: size < 1 ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
    minimumSize: 0.05
    padding: 0
    contentItem: Rectangle {
        implicitHeight: Theme.spacingXs + 1
        implicitWidth: Theme.spacingXs + 1
        radius: height / 2
        color: bar.pressed ? Theme.textSecondary : Theme.surface3
    }
    background: Rectangle {
        implicitHeight: Theme.spacingXs + 1
        radius: height / 2
        color: Theme.surface
    }
}
