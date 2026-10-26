import QtQuick
import "../theme"

// One draggable band handle on the curve.
// Drag: freq/gain. Shift: fine. Wheel: Q. Double-click: gain to 0. Right-click: menu.
// The selected band shows a Q ring; drag its knob in/out to change Q.
Item {
    id: dot
    required property var curve
    required property var bridge
    required property int index
    required property real freq
    required property real gain
    required property real q
    required property bool bandEnabled
    required property bool hasGain
    signal contextMenu(int index)

    readonly property bool selected: bridge.selected === index
    readonly property color tint: Theme.bandColor(index)
    readonly property real cx: curve.xOf(freq)
    readonly property real cy: curve.clampY(curve.yOf(hasGain ? gain : 0))
    readonly property real ringRadius: Math.max(Theme.dotSelectedSize, Math.min(72, 10 + 30 / q))

    x: cx - width / 2
    y: cy - height / 2
    width: Theme.dotHitSize
    height: Theme.dotHitSize
    z: selected ? 2 : 1

    // Q ring
    Rectangle {
        visible: dot.selected
        anchors.centerIn: parent
        width: dot.ringRadius * 2
        height: width
        radius: width / 2
        color: "transparent"
        border.width: 1
        border.color: Theme.alpha(dot.tint, 0.5)
        Behavior on width { enabled: !qDrag.pressed; NumberAnimation { duration: Theme.durationFast } }
    }
    Rectangle {
        id: qKnob
        visible: dot.selected
        x: dot.width / 2 + dot.ringRadius - width / 2
        y: dot.height / 2 - height / 2
        width: 10
        height: 10
        radius: 5
        color: Theme.background
        border.width: 2
        border.color: dot.tint
        MouseArea {
            id: qDrag
            anchors.fill: parent
            anchors.margins: -8
            cursorShape: Qt.SizeHorCursor
            preventStealing: true
            onPressed: dot.bridge.beginEdit()
            onReleased: dot.bridge.endEdit()
            onPositionChanged: (m) => {
                var p = mapToItem(dot, m.x, m.y)
                var r = Math.max(Theme.dotSelectedSize, Math.hypot(p.x - dot.width / 2, p.y - dot.height / 2))
                dot.bridge.setBandQ(dot.index, Math.round(30 / Math.max(1, r - 10) * 1000) / 1000)
            }
        }
    }

    // the dot
    Rectangle {
        anchors.centerIn: parent
        width: dot.selected ? Theme.dotSelectedSize : Theme.dotSize
        height: width
        radius: width / 2
        color: dot.bandEnabled ? dot.tint : Theme.surface3
        border.width: dot.selected ? 2 : 0
        border.color: Theme.textPrimary
        opacity: dot.bandEnabled ? 1 : Theme.disabledOpacity + 0.3
        Behavior on width { NumberAnimation { duration: Theme.durationFast } }
        Text {
            anchors.centerIn: parent
            text: dot.index + 1
            visible: parent.width >= Theme.dotSize
            color: dot.bandEnabled ? Theme.background : Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.smallSize - 2
            font.weight: Theme.weightSemibold
        }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        hoverEnabled: true
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
        preventStealing: true
        property point start
        property real startX
        property real startY

        onPressed: (m) => {
            dot.bridge.selected = dot.index
            if (m.button === Qt.RightButton) {
                dot.contextMenu(dot.index)
                return
            }
            start = mapToItem(dot.curve, m.x, m.y)
            startX = dot.cx
            startY = dot.curve.yOf(dot.hasGain ? dot.gain : 0)
            dot.bridge.beginEdit()
        }
        onPositionChanged: (m) => {
            if (!pressed || !(m.buttons & Qt.LeftButton)) return
            var p = mapToItem(dot.curve, m.x, m.y)
            var k = (m.modifiers & Qt.ShiftModifier) ? 0.15 : 1
            var nx = Math.max(0, Math.min(dot.curve.xOf(dot.curve.fmax), startX + (p.x - start.x) * k))
            var ny = startY + (p.y - start.y) * k
            var g = Math.round(dot.curve.dbOf(ny) * 10) / 10
            g = Math.max(-dot.curve.range, Math.min(dot.curve.range, g))
            dot.bridge.moveBand(dot.index, Math.round(dot.curve.fOf(nx) * 10) / 10, g)
        }
        onReleased: (m) => { if (m.button === Qt.LeftButton) dot.bridge.endEdit() }
        onDoubleClicked: (m) => { if (m.button === Qt.LeftButton) dot.bridge.resetGain(dot.index) }
        onWheel: (w) => {
            var steps = w.angleDelta.y / 120
            var base = (w.modifiers & Qt.ShiftModifier) ? 1.02 : 1.1
            dot.bridge.beginEdit()
            dot.bridge.scaleQ(dot.index, Math.pow(base, steps))
            wheelCommit.restart()
        }
    }
    Timer { id: wheelCommit; interval: 400; onTriggered: dot.bridge.endEdit() }

    // tooltip while dragging / hovering
    Rectangle {
        visible: area.pressed || area.containsMouse || qDrag.pressed
        x: dot.width / 2 - width / 2
        y: dot.cy < 50 ? dot.height + 4 : -height - 4
        width: tip.implicitWidth + Theme.spacingM
        height: tip.implicitHeight + Theme.spacingS
        radius: Theme.radiusSmall
        color: Theme.surface2
        Text {
            id: tip
            anchors.centerIn: parent
            text: dot.bridge.formatHz(dot.freq) + " Hz" + (dot.hasGain ? "  " + (dot.gain > 0 ? "+" : "") + dot.gain.toFixed(1) + " dB" : "") + "  Q " + dot.q.toFixed(2)
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            font.features: Theme.tabular
        }
    }
}
