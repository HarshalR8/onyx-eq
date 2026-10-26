import QtQuick
import "../theme"

// Horizontal band cards. Click selects; the dot toggles the band.
ListView {
    id: list
    required property var bridge
    orientation: ListView.Horizontal
    spacing: Theme.spacingS
    clip: true
    implicitHeight: Theme.bandCardHeight
    model: bridge.bandModel
    boundsBehavior: Flickable.StopAtBounds
    currentIndex: bridge.selected
    highlightFollowsCurrentItem: false
    onCurrentIndexChanged: if (currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Contain)
    WheelHandler {
        orientation: Qt.Vertical
        onWheel: (w) => { list.flick(w.angleDelta.y * 8, 0) }
    }

    footer: Item {
        width: Theme.bandCardHeight + Theme.spacingS
        height: list.height
        Rectangle {
            x: Theme.spacingS
            width: Theme.bandCardHeight * 0.7
            height: list.height
            radius: Theme.radiusCard
            color: addArea.containsMouse ? Theme.surface2 : Theme.surface
            Text {
                anchors.centerIn: parent
                text: "+"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.titleSize
                font.weight: Font.Light
            }
            MouseArea {
                id: addArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: list.bridge.addBand(1000, 0)
            }
        }
    }

    delegate: Rectangle {
        id: card
        required property int index
        required property real freq
        required property real gain
        required property real q
        required property bool bandEnabled
        required property bool hasGain
        required property string typeName
        readonly property bool selected: list.bridge.selected === index
        width: Theme.bandCardWidth
        height: list.height
        radius: Theme.radiusCard
        color: selected ? Theme.surface2 : Theme.surface
        Behavior on color { ColorAnimation { duration: Theme.durationFast } }

        MouseArea {
            anchors.fill: parent
            onClicked: list.bridge.selected = card.index
        }
        Column {
            anchors.fill: parent
            anchors.margins: Theme.spacingM - 2
            spacing: 2
            Row {
                spacing: Theme.spacingS
                Rectangle {
                    width: 10; height: 10; radius: 5
                    anchors.verticalCenter: parent.verticalCenter
                    color: card.bandEnabled ? Theme.bandColor(card.index) : "transparent"
                    border.width: card.bandEnabled ? 0 : 1.5
                    border.color: Theme.bandColor(card.index)
                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -8
                        onClicked: list.bridge.setBandEnabled(card.index, !card.bandEnabled)
                    }
                }
                Text {
                    text: list.bridge.formatHz(card.freq) + " Hz"
                    color: card.bandEnabled ? Theme.textPrimary : Theme.textTertiary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.headlineSize
                    font.weight: Theme.weightSemibold
                    font.features: Theme.tabular
                }
            }
            Text {
                text: (card.hasGain ? (card.gain > 0 ? "+" : "") + card.gain.toFixed(1) + " dB   " : "") + "Q " + card.q.toFixed(2)
                color: card.bandEnabled ? Theme.textSecondary : Theme.textTertiary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize - 1
                font.features: Theme.tabular
            }
            Text {
                text: card.typeName + (list.bridge.solo === card.index ? "  ·  Solo" : "")
                color: Theme.textTertiary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
            }
        }
    }
}
