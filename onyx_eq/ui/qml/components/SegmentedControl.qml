import QtQuick
import "../theme"

// Apple-style segmented control. model: [{value, label}], current: value
Rectangle {
    id: root
    property var model: []
    property var current
    property int segmentWidth: 96
    signal activated(var value)

    implicitWidth: segmentWidth * model.length + 4
    implicitHeight: Theme.controlHeight
    radius: Theme.radiusSmall + 1
    color: Theme.surface2

    readonly property int currentIndex: {
        for (var i = 0; i < model.length; ++i) if (model[i].value === current) return i
        return -1
    }

    Rectangle {
        visible: root.currentIndex >= 0
        x: 2 + root.currentIndex * (root.width - 4) / Math.max(1, root.model.length)
        y: 2
        width: (root.width - 4) / Math.max(1, root.model.length)
        height: root.height - 4
        radius: Theme.radiusSmall - 1
        color: Theme.surface3
        Behavior on x { NumberAnimation { duration: Theme.duration; easing.type: Theme.easing } }
    }
    Row {
        anchors.fill: parent
        anchors.margins: 2
        Repeater {
            model: root.model
            delegate: Item {
                required property var modelData
                required property int index
                width: (root.width - 4) / Math.max(1, root.model.length)
                height: parent.height
                Text {
                    anchors.centerIn: parent
                    text: modelData.label
                    color: index === root.currentIndex ? Theme.textPrimary : Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize + 1
                    font.weight: Theme.weightMedium
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: root.activated(modelData.value)
                }
            }
        }
    }
}
