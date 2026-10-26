import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "../theme"

// Graphic-mode editor: band-count picker and one vertical slider per band.
ColumnLayout {
    id: root
    required property var bridge
    spacing: Theme.spacingS
    readonly property var labels: bridge.graphicLabels(bridge.bandCount)

    RowLayout {
        Layout.fillWidth: true
        spacing: Theme.spacingS
        Text {
            text: "Bands"
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize - 1
        }
        SegmentedControl {
            segmentWidth: 48
            model: root.bridge.graphicPresets.map(function (n) { return { value: n, label: "" + n } })
            current: root.bridge.graphicCount
            onActivated: (v) => root.bridge.setGraphicCount(v)
        }
        NumberField {
            id: custom
            Layout.preferredWidth: 72
            label: ""
            value: root.bridge.graphicCount
            decimals: 0
            from: 2; to: 511; step: 1
            onCommitted: (v) => root.bridge.setGraphicCount(Math.round(v))
        }
        Item { Layout.fillWidth: true }
        OButton {
            text: "Flatten"
            compact: true
            onClicked: root.bridge.flattenGraphic()
        }
    }

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true

    ListView {
        id: list
        anchors.fill: parent
        orientation: ListView.Horizontal
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: false
        spacing: count > 40 ? 0 : 2
        model: root.bridge.bandModel
        readonly property real slotWidth: Math.max(Theme.sliderWidth - 8, Math.min(Theme.sliderWidth * 1.6, (width - spacing * (count - 1)) / Math.max(1, count)))
        footer: Item { width: 1; height: 1 }
        ScrollBar.horizontal: OScrollBar { }

        delegate: Item {
            id: s
            required property int index
            required property real gain
            readonly property real range: root.bridge.rangeDb
            width: list.slotWidth
            height: list.height - Theme.spacingS  // room for the scrollbar
            readonly property real trackTop: Theme.captionSize + Theme.spacingS
            readonly property real trackH: height - trackTop - (Theme.captionSize + Theme.spacingS)
            function yOf(g) { return trackTop + trackH / 2 - g / range * trackH / 2 }
            function gOf(y) { return (trackTop + trackH / 2 - y) / (trackH / 2) * range }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: (s.gain > 0 ? "+" : "") + s.gain.toFixed(1)
                visible: list.slotWidth >= Theme.sliderWidth - 4 || paint.pressed
                color: s.gain === 0 ? Theme.textTertiary : Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.smallSize - 1
                font.features: Theme.tabular
            }
            Rectangle {   // track
                x: (parent.width - width) / 2
                y: s.trackTop
                width: Theme.sliderTrack
                height: s.trackH
                radius: width / 2
                color: Theme.surface2
            }
            Rectangle {   // zero tick
                x: (parent.width - width) / 2
                y: s.yOf(0)
                width: Theme.sliderTrack * 3
                height: 1
                color: Theme.gridZero
            }
            Rectangle {   // fill from 0
                x: (parent.width - width) / 2
                y: Math.min(s.yOf(0), s.yOf(Math.max(-s.range, Math.min(s.range, s.gain))))
                width: Theme.sliderTrack
                height: Math.abs(s.yOf(Math.max(-s.range, Math.min(s.range, s.gain))) - s.yOf(0))
                radius: width / 2
                color: Theme.accent
            }
            Rectangle {   // knob
                readonly property real d: Math.min(Theme.sliderKnob - 4, list.slotWidth - 4)
                x: (parent.width - d) / 2
                y: s.yOf(Math.max(-s.range, Math.min(s.range, s.gain))) - d / 2
                width: d
                height: d
                radius: d / 2
                color: Theme.textPrimary
                scale: paint.pressed ? 1.15 : 1
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                text: root.labels[s.index] || ""
                visible: list.count <= 31 || s.index % Math.ceil(list.count / 24) === 0
                color: Theme.textTertiary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.smallSize - 1
                font.features: Theme.tabular
            }
        }
    }

        // One area for all sliders: press and drag across them to paint a curve.
        // Shift = fine steps, double-click = reset, wheel = ±0.5 dB.
        MouseArea {
            id: paint
            objectName: "paint"
            anchors.fill: parent
            anchors.bottomMargin: Theme.spacingS
            preventStealing: true
            property int lastIndex: -1
            property real lastGain: 0
            function hit(x, y) {
                var i = list.indexAt(list.contentX + x, list.contentY + y)
                var item = list.itemAtIndex(i)
                return { index: i, item: item }
            }
            function gainAt(item, y, mods) {
                var g = Math.max(-item.range, Math.min(item.range, item.gOf(y)))
                var step = (mods & Qt.ShiftModifier) ? 0.1 : 0.5
                return Math.round(g / step) * step
            }
            onPressed: (m) => {
                var h = hit(m.x, m.y)
                if (h.index < 0) return
                root.bridge.beginEdit()
                lastIndex = h.index
                lastGain = gainAt(h.item, m.y, m.modifiers)
                root.bridge.setGraphicGain(h.index, lastGain)
            }
            onPositionChanged: (m) => {
                if (!pressed) return
                var h = hit(Math.max(0, Math.min(width - 1, m.x)), m.y)
                if (h.index < 0) return
                var g = gainAt(h.item, m.y, m.modifiers)
                // fill the sliders skipped by a fast drag
                var from = lastIndex < 0 ? h.index : lastIndex
                var n = Math.abs(h.index - from)
                for (var k = 1; k <= n; ++k) {
                    var i = from + (h.index > from ? k : -k)
                    root.bridge.setGraphicGain(i, Math.round((lastGain + (g - lastGain) * k / n) * 10) / 10)
                }
                if (n === 0) root.bridge.setGraphicGain(h.index, g)
                lastIndex = h.index
                lastGain = g
            }
            onReleased: { lastIndex = -1; root.bridge.endEdit() }
            onDoubleClicked: (m) => { var h = hit(m.x, m.y); if (h.index >= 0) root.bridge.setGraphicGain(h.index, 0) }
            onWheel: (w) => {
                if (w.modifiers & Qt.ControlModifier || Math.abs(w.angleDelta.x) > Math.abs(w.angleDelta.y)) {
                    list.flick(-(w.angleDelta.x || w.angleDelta.y) * 8, 0)
                    return
                }
                var h = hit(w.x, w.y)
                if (h.index >= 0) root.bridge.setGraphicGain(h.index, h.item.gain + w.angleDelta.y / 120 * 0.5)
            }
        }
    }
}
