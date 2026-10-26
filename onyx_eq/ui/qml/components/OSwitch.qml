import QtQuick
import QtQuick.Controls.Basic
import "../theme"

Switch {
    id: control
    focusPolicy: Qt.NoFocus
    font.family: Theme.fontFamily
    font.pixelSize: Theme.bodySize
    spacing: Theme.spacingS
    indicator: Rectangle {
        implicitWidth: 44
        implicitHeight: 26
        x: control.leftPadding
        anchors.verticalCenter: parent.verticalCenter
        radius: height / 2
        color: control.checked ? Theme.positive : Theme.surface3
        Behavior on color { ColorAnimation { duration: Theme.duration } }
        Rectangle {
            width: parent.height - 4
            height: width
            radius: width / 2
            y: 2
            x: control.checked ? parent.width - width - 2 : 2
            color: Theme.textPrimary
            Behavior on x { NumberAnimation { duration: Theme.duration; easing.type: Theme.easing } }
        }
    }
    contentItem: Text {
        leftPadding: control.indicator.width + control.spacing
        text: control.text
        font: control.font
        color: Theme.textPrimary
        verticalAlignment: Text.AlignVCenter
    }
}
