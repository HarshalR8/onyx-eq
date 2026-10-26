import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "../theme"

// Title, mode switch, A/B, undo/redo, bypass.
Item {
    id: root
    required property var bridge
    implicitHeight: Theme.toolbarHeight

    RowLayout {
        anchors.fill: parent
        spacing: Theme.spacingS

        Text {
            text: "Onyx EQ"
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.titleSize
            font.weight: Theme.weightSemibold
        }
        Rectangle {
            Layout.leftMargin: Theme.spacingS
            visible: root.bridge.statusLevel !== "ok" || root.bridge.status !== ""
            implicitWidth: statusText.implicitWidth + Theme.spacingM
            implicitHeight: Theme.controlHeightSmall - 4
            radius: height / 2
            color: root.bridge.statusLevel === "error" ? Theme.alpha(Theme.destructive, 0.18) : Theme.surface2
            Text {
                id: statusText
                anchors.centerIn: parent
                text: root.bridge.status || (root.bridge.statusLevel === "busy" ? "Working…" : "")
                width: Math.min(implicitWidth, 320)
                elide: Text.ElideRight
                color: root.bridge.statusLevel === "error" ? Theme.destructive : Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
            }
            OToolTip { visible: statusHover.containsMouse && statusText.truncated; text: root.bridge.status }
            MouseArea { id: statusHover; anchors.fill: parent; hoverEnabled: true }
        }
        Item { Layout.fillWidth: true }

        SegmentedControl {
            model: [{ value: "parametric", label: "Parametric" }, { value: "graphic", label: "Graphic" }]
            current: root.bridge.mode
            onActivated: (v) => root.bridge.setMode(v)
        }
        Item { Layout.fillWidth: true }

        IconButton {
            glyph: "undo"
            enabled: root.bridge.canUndo
            onClicked: root.bridge.undo()
            OToolTip { visible: parent.hovered; text: "Undo (Ctrl+Z)" }
        }
        IconButton {
            glyph: "redo"
            enabled: root.bridge.canRedo
            onClicked: root.bridge.redo()
            OToolTip { visible: parent.hovered; text: "Redo (Ctrl+Shift+Z)" }
        }
        SegmentedControl {
            Layout.leftMargin: Theme.spacingS
            segmentWidth: 34
            model: [{ value: "A", label: "A" }, { value: "B", label: "B" }]
            current: root.bridge.abSlot
            onActivated: (v) => { if (v !== root.bridge.abSlot) root.bridge.toggleAB() }
            OToolTip { visible: abHover.hovered; text: "A/B compare (Ctrl+T)" }
            HoverHandler { id: abHover }
        }
        IconButton {
            Layout.leftMargin: Theme.spacingS
            glyph: "power"
            fill: root.bridge.bypass ? Theme.surface2 : Theme.alpha(Theme.accent, 0.22)
            tint: root.bridge.bypass ? Theme.textTertiary : Theme.accent
            onClicked: root.bridge.bypass = !root.bridge.bypass
            OToolTip { visible: parent.hovered; text: root.bridge.bypass ? "EQ off (Ctrl+B)" : "EQ on (Ctrl+B)" }
        }
    }
}
