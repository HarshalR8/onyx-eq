import QtQuick
import QtQuick.Controls.Basic
import "../theme"

// Horizontal slider. Bipolar sliders fill from the centre value.
Slider {
    id: control
    property real origin: 0
    property color tint: Theme.accent
    implicitHeight: Theme.controlHeight
    implicitWidth: 200
    focusPolicy: Qt.NoFocus
    signal doubleClicked()

    background: Item {
        x: control.leftPadding
        width: control.availableWidth
        height: control.height
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width
            height: Theme.sliderTrack
            radius: height / 2
            color: Theme.surface3
        }
        Rectangle {
            readonly property real o: (Math.min(Math.max(control.origin, control.from), control.to) - control.from) / (control.to - control.from)
            anchors.verticalCenter: parent.verticalCenter
            x: Math.min(o, control.visualPosition) * parent.width
            width: Math.abs(control.visualPosition - o) * parent.width
            height: Theme.sliderTrack
            radius: height / 2
            color: control.tint
        }
    }
    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        anchors.verticalCenter: parent.verticalCenter
        width: Theme.sliderKnob
        height: Theme.sliderKnob
        radius: width / 2
        color: Theme.textPrimary
        scale: control.pressed ? 1.1 : 1
        Behavior on scale { NumberAnimation { duration: Theme.durationFast } }
    }
    TapHandler {
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: control.doubleClicked()
    }
}
