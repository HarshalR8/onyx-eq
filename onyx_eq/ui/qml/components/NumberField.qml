import QtQuick
import QtQuick.Controls.Basic
import "../theme"

// Compact numeric entry: type a value + Enter, or scroll to step. Emits `committed(value)`.
Item {
    id: root
    property string label: ""
    property real value: 0
    property int decimals: 1
    property string suffix: ""
    property real from: -1e9
    property real to: 1e9
    property real step: 0.1
    property bool logStep: false       // step as a ratio (frequencies)
    property bool signed: false
    property bool fieldEnabled: true
    property alias field: input
    signal committed(real value)

    implicitWidth: 112
    implicitHeight: Theme.controlHeight + (label ? Theme.captionSize + Theme.spacingXs : 0)

    function fmt(v) {
        var s = v.toFixed(decimals)
        return (signed && v > 0 ? "+" : "") + s
    }
    function commit(v) {
        root.committed(Math.max(from, Math.min(to, v)))
    }

    Text {
        id: caption
        text: root.label
        height: root.label ? implicitHeight : 0
        color: Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.captionSize
    }
    TextField {
        id: input
        anchors.top: caption.bottom
        anchors.topMargin: root.label ? Theme.spacingXs : 0
        width: parent.width
        height: Theme.controlHeight
        enabled: root.fieldEnabled
        text: root.fmt(root.value)
        font.family: Theme.fontFamily
        font.pixelSize: Theme.bodySize
        font.features: Theme.tabular
        color: enabled ? Theme.textPrimary : Theme.textTertiary
        selectionColor: Theme.accent
        selectedTextColor: Theme.textPrimary
        leftPadding: Theme.spacingS + 2
        rightPadding: unit.implicitWidth + Theme.spacingS + 2
        verticalAlignment: TextInput.AlignVCenter
        selectByMouse: true
        inputMethodHints: Qt.ImhFormattedNumbersOnly
        background: Rectangle {
            radius: Theme.radiusSmall
            color: Theme.surface2
            border.width: input.activeFocus ? 1 : 0
            border.color: Theme.accent
        }
        Text {
            id: unit
            anchors.right: parent.right
            anchors.rightMargin: Theme.spacingS + 2
            anchors.verticalCenter: parent.verticalCenter
            text: root.suffix
            color: Theme.textTertiary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
        }
        onEditingFinished: {
            var t = text.replace(",", ".").trim().toLowerCase()
            var mult = 1
            if (t.endsWith("k")) { mult = 1000; t = t.slice(0, -1) }
            var v = parseFloat(t) * mult
            if (!isNaN(v)) root.commit(v)
            focus = false
        }
        Keys.onEscapePressed: focus = false
        // typing breaks the text binding; put it back whenever editing ends
        onActiveFocusChanged: if (!activeFocus) text = Qt.binding(function () { return root.fmt(root.value) })
        WheelHandler {
            enabled: root.fieldEnabled
            onWheel: (w) => {
                var n = w.angleDelta.y / 120
                var fine = (w.modifiers & Qt.ShiftModifier) ? 0.2 : 1
                root.commit(root.logStep ? root.value * Math.pow(1 + root.step * fine, n)
                                         : Math.round((root.value + n * root.step * fine) * 1000) / 1000)
            }
        }
    }
}
