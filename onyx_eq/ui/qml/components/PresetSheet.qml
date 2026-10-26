import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtCore
import "../theme"

// Modal sheet: manage presets, import/export, and options.
Popup {
    id: sheet
    objectName: "presetSheet"
    required property var bridge
    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: Math.min(Theme.sheetWidth + 120, parent ? parent.width - 2 * Theme.spacingL : Theme.sheetWidth)
    height: Math.min(contentCol.implicitHeight + 2 * padding, parent ? parent.height - 2 * Theme.spacingL : 640)
    padding: Theme.spacingL
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    function openSave() { open(); nameField.text = bridge.presetName === "Flat" ? "" : bridge.presetName; nameField.forceActiveFocus(); nameField.selectAll() }
    function openImport() { importDialog.open() }
    function openExport() { exportDialog.open() }

    Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { radius: Theme.radiusSheet; color: Theme.surface }
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.duration; easing.type: Theme.easing }
        NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.duration; easing.type: Theme.easing }
    }
    exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: Theme.durationFast } }

    component Heading: Text {
        color: Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.captionSize
        font.weight: Theme.weightMedium
        font.capitalization: Font.AllUppercase
        Layout.topMargin: Theme.spacingS
    }

    Flickable {
        anchors.fill: parent
        contentHeight: contentCol.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ColumnLayout {
            id: contentCol
            width: parent.width
            spacing: Theme.spacingS

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "Presets"
                    Layout.fillWidth: true
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.titleSize - 6
                    font.weight: Theme.weightSemibold
                }
                IconButton { glyph: "close"; onClicked: sheet.close() }
            }

            Heading { text: "Save current" }
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spacingS
                TextField {
                    id: nameField
                    Layout.fillWidth: true
                    implicitHeight: Theme.controlHeight
                    placeholderText: "Preset name"
                    placeholderTextColor: Theme.textTertiary
                    color: Theme.textPrimary
                    selectionColor: Theme.accent
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    leftPadding: Theme.spacingM - 4
                    background: Rectangle {
                        radius: Theme.radiusSmall
                        color: Theme.surface2
                        border.width: nameField.activeFocus ? 1 : 0
                        border.color: Theme.accent
                    }
                    onAccepted: saveBtn.clicked()
                }
                OButton {
                    id: saveBtn
                    text: "Save"
                    role: "accent"
                    enabled: nameField.text.trim().length > 0 && nameField.text.trim() !== "Flat"
                    onClicked: if (sheet.bridge.savePreset(nameField.text)) nameField.text = ""
                }
            }

            Heading { text: "Library" }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.min(presetList.contentHeight, 6 * (Theme.controlHeight + 6)) + Theme.spacingS
                radius: Theme.radiusControl
                color: Theme.surface2
                ListView {
                    id: presetList
                    anchors.fill: parent
                    anchors.margins: Theme.spacingXs
                    clip: true
                    model: sheet.bridge.presets
                    boundsBehavior: Flickable.StopAtBounds
                    delegate: Item {
                        id: row
                        required property string modelData
                        required property int index
                        property bool renaming: false
                        width: presetList.width
                        height: Theme.controlHeight + 6
                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.radiusSmall
                            color: rowArea.containsMouse ? Theme.surface3 : "transparent"
                        }
                        MouseArea {
                            id: rowArea
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: sheet.bridge.loadPreset(row.modelData)
                            onDoubleClicked: if (row.modelData !== "Flat") { row.renaming = true; renameField.forceActiveFocus(); renameField.selectAll() }
                        }
                        Text {
                            visible: !row.renaming
                            anchors.left: parent.left
                            anchors.leftMargin: Theme.spacingS + 2
                            anchors.verticalCenter: parent.verticalCenter
                            text: row.modelData
                            color: Theme.textPrimary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: row.modelData === sheet.bridge.presetName ? Theme.weightSemibold : Theme.weightRegular
                        }
                        TextField {
                            id: renameField
                            visible: row.renaming
                            anchors.left: parent.left
                            anchors.right: actions.left
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: Theme.spacingXs
                            text: row.modelData
                            color: Theme.textPrimary
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            background: Rectangle { radius: Theme.radiusSmall; color: Theme.surface; border.width: 1; border.color: Theme.accent }
                            onAccepted: { sheet.bridge.renamePreset(row.modelData, text); row.renaming = false }
                            onActiveFocusChanged: if (!activeFocus) row.renaming = false
                            Keys.onEscapePressed: row.renaming = false
                        }
                        Row {
                            id: actions
                            anchors.right: parent.right
                            anchors.rightMargin: Theme.spacingXs
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: Theme.spacingXs
                            visible: row.modelData !== "Flat" && (rowArea.containsMouse || renameBtn.hovered || delBtn.hovered)
                            OButton { id: renameBtn; text: "Rename"; role: "ghost"; compact: true; onClicked: { row.renaming = true; renameField.forceActiveFocus(); renameField.selectAll() } }
                            OButton { id: delBtn; text: "Delete"; role: "destructive"; compact: true; onClicked: sheet.bridge.deletePreset(row.modelData) }
                        }
                    }
                }
            }

            Heading { text: "Equalizer APO / AutoEQ files" }
            RowLayout {
                spacing: Theme.spacingS
                OButton { text: "Import…"; onClicked: importDialog.open() }
                OButton { text: "Export…"; onClicked: exportDialog.open() }
                OComboBox {
                    id: exportKind
                    Layout.preferredWidth: 190
                    model: [{ v: "parametric", t: "ParametricEQ.txt" }, { v: "graphic", t: "GraphicEQ.txt" }, { v: "json", t: "Onyx preset (.json)" }]
                    textRole: "t"
                    valueRole: "v"
                }
            }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "Tip: drop a file onto the window to import it."
                color: Theme.textTertiary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
            }

            Heading { text: "Options" }
            OSwitch {
                text: "Use “" + (sheet.bridge.presetName || "this preset") + "” for this output"
                enabled: sheet.bridge.engineEnabled && sheet.bridge.presetName !== ""
                checked: sheet.bridge.outputPreset !== "" && sheet.bridge.outputPreset === sheet.bridge.presetName
                onToggled: sheet.bridge.bindPresetToOutput(checked)
            }
            OSwitch {
                text: "Switch presets automatically when the output changes"
                checked: sheet.bridge.autoSwitch
                onToggled: sheet.bridge.autoSwitch = checked
            }
            OSwitch {
                text: "Keep EQ running after closing the window"
                enabled: sheet.bridge.keepRunningAvailable
                checked: sheet.bridge.keepRunning
                onToggled: sheet.bridge.keepRunning = checked
            }
        }
    }

    FileDialog {
        id: importDialog
        title: "Import EQ"
        fileMode: FileDialog.OpenFile
        nameFilters: ["EQ files (*.txt *.json)", "All files (*)"]
        currentFolder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)
        onAccepted: sheet.bridge.importFile(selectedFile)
    }
    FileDialog {
        id: exportDialog
        title: "Export EQ"
        fileMode: FileDialog.SaveFile
        defaultSuffix: exportKind.currentValue === "json" ? "json" : "txt"
        currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
        selectedFile: currentFolder + "/" + (sheet.bridge.presetName || "Onyx EQ") +
                      (exportKind.currentValue === "graphic" ? " GraphicEQ.txt" : exportKind.currentValue === "json" ? ".json" : " ParametricEQ.txt")
        onAccepted: sheet.bridge.exportFile(selectedFile, exportKind.currentValue)
    }
}
