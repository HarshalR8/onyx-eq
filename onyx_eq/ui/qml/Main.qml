import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import "theme"
import "components"

ApplicationWindow {
    id: win
    required property var bridge
    width: 1120
    height: 780
    minimumWidth: Theme.windowMinWidth
    minimumHeight: Theme.windowMinHeight
    visible: true
    title: "Onyx EQ"
    color: Theme.background
    font.family: Theme.fontFamily

    readonly property bool parametric: bridge.mode === "parametric"

    // ---- keyboard shortcuts ------------------------------------------------------------------
    Shortcut { sequences: [StandardKey.Undo]; onActivated: bridge.undo() }
    Shortcut { sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]; onActivated: bridge.redo() }
    Shortcut { sequence: "Ctrl+B"; onActivated: bridge.bypass = !bridge.bypass }
    Shortcut { sequence: "Ctrl+T"; onActivated: bridge.toggleAB() }
    Shortcut { sequences: [StandardKey.Save]; onActivated: win.quickSave() }
    Shortcut { sequence: "Ctrl+O"; onActivated: sheet.openImport() }
    Shortcut { sequence: "Ctrl+E"; onActivated: sheet.openExport() }
    Shortcut { sequence: "Ctrl+P"; onActivated: sheet.open() }
    Shortcut { sequence: "Ctrl+1"; onActivated: bridge.setMode("parametric") }
    Shortcut { sequence: "Ctrl+2"; onActivated: bridge.setMode("graphic") }
    Shortcut { sequences: [StandardKey.Delete, "Backspace"]; enabled: win.parametric && !win.textFocus(); onActivated: bridge.removeBand(bridge.selected) }
    Shortcut { sequence: "Left"; enabled: !win.textFocus(); onActivated: bridge.nudgeFreq(bridge.selected, -1 / 12) }
    Shortcut { sequence: "Right"; enabled: !win.textFocus(); onActivated: bridge.nudgeFreq(bridge.selected, 1 / 12) }
    Shortcut { sequence: "Shift+Left"; enabled: !win.textFocus(); onActivated: bridge.nudgeFreq(bridge.selected, -1 / 96) }
    Shortcut { sequence: "Shift+Right"; enabled: !win.textFocus(); onActivated: bridge.nudgeFreq(bridge.selected, 1 / 96) }
    Shortcut { sequence: "Up"; enabled: !win.textFocus(); onActivated: bridge.nudgeGain(bridge.selected, 0.5) }
    Shortcut { sequence: "Down"; enabled: !win.textFocus(); onActivated: bridge.nudgeGain(bridge.selected, -0.5) }
    Shortcut { sequence: "Shift+Up"; enabled: !win.textFocus(); onActivated: bridge.nudgeGain(bridge.selected, 0.1) }
    Shortcut { sequence: "Shift+Down"; enabled: !win.textFocus(); onActivated: bridge.nudgeGain(bridge.selected, -0.1) }
    Shortcut { sequence: "Ctrl+Up"; enabled: !win.textFocus(); onActivated: bridge.scaleQ(bridge.selected, 1.1) }
    Shortcut { sequence: "Ctrl+Down"; enabled: !win.textFocus(); onActivated: bridge.scaleQ(bridge.selected, 1 / 1.1) }
    Shortcut { sequence: "Tab"; enabled: !win.textFocus() && bridge.bandCount > 0; onActivated: bridge.selected = (bridge.selected + 1) % bridge.bandCount }
    Shortcut { sequence: "Shift+Tab"; enabled: !win.textFocus() && bridge.bandCount > 0; onActivated: bridge.selected = (bridge.selected - 1 + bridge.bandCount) % bridge.bandCount }

    function textFocus() { return activeFocusItem && activeFocusItem.hasOwnProperty("cursorPosition") }
    function quickSave() {
        if (bridge.presetName && bridge.presetName !== "Flat") bridge.savePreset(bridge.presetName)
        else sheet.openSave()
    }

    // ---- layout ------------------------------------------------------------------------------
    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingL
        anchors.rightMargin: Theme.spacingL
        anchors.bottomMargin: Theme.spacingM
        anchors.topMargin: Theme.spacingS
        spacing: Theme.spacingM

        Toolbar {
            Layout.fillWidth: true
            bridge: win.bridge
        }

        CurveView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 220
            bridge: win.bridge
        }

        // preamp + range
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingM
            Text {
                text: "Preamp"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
            }
            OSlider {
                id: preampSlider
                Layout.preferredWidth: 260
                from: -24; to: 12; stepSize: 0.1
                value: win.bridge.preamp
                onMoved: win.bridge.setPreamp(Math.round(value * 10) / 10)
                onPressedChanged: pressed ? win.bridge.beginEdit() : win.bridge.endEdit()
                onDoubleClicked: win.bridge.setPreamp(0)
            }
            NumberField {
                Layout.preferredWidth: 92
                value: win.bridge.preamp
                signed: true
                suffix: "dB"
                from: -30; to: 30; step: 0.5
                onCommitted: (v) => win.bridge.setPreamp(v)
            }
            OButton {
                text: "Auto"
                compact: true
                onClicked: win.bridge.autoPreamp()
                OToolTip { visible: parent.hovered; text: "Set preamp to the negative of the highest boost" }
            }
            Rectangle {
                visible: win.bridge.clipping
                implicitWidth: clipText.implicitWidth + Theme.spacingM
                implicitHeight: Theme.controlHeightSmall - 4
                radius: height / 2
                color: Theme.alpha(Theme.warning, 0.16)
                Text {
                    id: clipText
                    anchors.centerIn: parent
                    text: "Peaks at +" + win.bridge.maxLevel.toFixed(1) + " dB · may clip"
                    color: Theme.warning
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.features: Theme.tabular
                }
            }
            Item { Layout.fillWidth: true }
            SegmentedControl {
                segmentWidth: 52
                model: [{ value: 6, label: "±6" }, { value: 12, label: "±12" }, { value: 24, label: "±24" }]
                current: win.bridge.rangeDb
                onActivated: (v) => win.bridge.rangeDb = v
            }
        }

        // parametric: inspector + band cards
        ColumnLayout {
            visible: win.parametric
            Layout.fillWidth: true
            spacing: Theme.spacingS
            BandInspector {
                Layout.fillWidth: true
                bridge: win.bridge
            }
            BandList {
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.bandCardHeight
                bridge: win.bridge
            }
        }

        // graphic: sliders
        GraphicSliders {
            visible: !win.parametric
            Layout.fillWidth: true
            Layout.preferredHeight: 230
            bridge: win.bridge
        }

        // output + preset bar
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingS
            OComboBox {
                Layout.preferredWidth: 300
                prefix: "Output"
                enabled: win.bridge.engineEnabled && count > 0
                model: win.bridge.outputs
                textRole: "description"
                valueRole: "name"
                displayText: count ? currentText : "No devices"
                currentIndex: {
                    var o = win.bridge.outputs
                    for (var i = 0; i < o.length; ++i) if (o[i].name === win.bridge.output) return i
                    return -1
                }
                onActivated: (i) => win.bridge.setOutput(win.bridge.outputs[i].name)
            }
            Item { Layout.fillWidth: true }
            OComboBox {
                Layout.preferredWidth: 260
                prefix: "Preset"
                model: win.bridge.presets
                displayText: (win.bridge.presetName || "Untitled") + (win.bridge.presetDirty ? "  •" : "")
                currentIndex: win.bridge.presets.indexOf(win.bridge.presetName)
                onActivated: (i) => win.bridge.loadPreset(win.bridge.presets[i])
            }
            OButton {
                text: "Save"
                compact: true
                enabled: win.bridge.presetDirty || !win.bridge.hasPreset(win.bridge.presetName)
                onClicked: win.quickSave()
            }
            IconButton {
                glyph: "more"
                onClicked: sheet.open()
                OToolTip { visible: parent.hovered; text: "Presets, import/export, options (Ctrl+P)" }
            }
        }
    }

    PresetSheet {
        id: sheet
        bridge: win.bridge
    }

    // ---- drag & drop import ------------------------------------------------------------------
    DropArea {
        anchors.fill: parent
        keys: ["text/uri-list"]
        onDropped: (drop) => { if (drop.hasUrls) win.bridge.importFile(drop.urls[0]) }
        Rectangle {
            anchors.fill: parent
            anchors.margins: Theme.spacingS
            visible: parent.containsDrag
            radius: Theme.radiusSheet
            color: Theme.alpha(Theme.accent, 0.08)
            border.width: 2
            border.color: Theme.accent
            Text {
                anchors.centerIn: parent
                text: "Drop to import EQ"
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.headlineSize
                font.weight: Theme.weightSemibold
            }
        }
    }

    // ---- toast -------------------------------------------------------------------------------
    Rectangle {
        id: toast
        property string level: "ok"
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height - height - Theme.spacingL * 3
        width: Math.min(toastText.implicitWidth + Theme.spacingL * 2, parent.width - Theme.spacingL * 2)
        height: toastText.implicitHeight + Theme.spacingM
        radius: height / 2
        color: Theme.surface2
        border.width: 1
        border.color: level === "error" ? Theme.destructive : level === "warn" ? Theme.warning : Theme.hairline
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.duration; easing.type: Theme.easing } }
        Text {
            id: toastText
            anchors.centerIn: parent
            width: Math.min(implicitWidth, toast.parent.width - Theme.spacingL * 4)
            elide: Text.ElideRight
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize - 1
        }
        Timer { id: toastTimer; interval: 3500; onTriggered: toast.opacity = 0 }
        Connections {
            target: win.bridge
            function onToast(level, message) {
                toast.level = level
                toastText.text = message
                toast.opacity = 1
                toastTimer.interval = level === "ok" ? 2500 : 6000
                toastTimer.restart()
            }
        }
    }
}
