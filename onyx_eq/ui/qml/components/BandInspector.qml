import QtQuick
import QtQuick.Layouts
import "../theme"

// Exact numeric entry for the selected band.
Rectangle {
    id: root
    required property var bridge
    readonly property int sel: bridge.selected
    // values pulled from the model so they update live while dragging
    property var band: ({})
    function refresh() { band = bridge.bandAt(sel) }
    onSelChanged: refresh()
    Component.onCompleted: refresh()
    Connections {
        target: root.bridge.bandModel
        function onDataChanged() { root.refresh() }
        function onModelReset() { root.refresh() }
        function onRowsInserted() { root.refresh() }
        function onRowsRemoved() { root.refresh() }
    }
    readonly property bool has: band.freq !== undefined

    radius: Theme.radiusCard
    color: Theme.surface
    implicitHeight: row.implicitHeight + Theme.spacingM * 2

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: Theme.spacingM
        spacing: Theme.spacingM
        visible: root.has

        Rectangle {
            Layout.alignment: Qt.AlignBottom
            Layout.bottomMargin: (Theme.controlHeight - height) / 2
            width: 12; height: 12; radius: 6
            color: Theme.bandColor(root.sel)
        }
        Item {
            Layout.preferredWidth: 150
            Layout.preferredHeight: typeBox.height + Theme.captionSize + Theme.spacingXs
            Text {
                id: typeLabel
                text: "Type"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
            }
            OComboBox {
                id: typeBox
                anchors.top: typeLabel.bottom
                anchors.topMargin: Theme.spacingXs
                width: parent.width
                model: root.bridge.bandTypes
                textRole: "name"
                valueRole: "value"
                currentIndex: {
                    var t = root.bridge.bandTypes
                    for (var i = 0; i < t.length; ++i) if (t[i].value === root.band.type) return i
                    return 0
                }
                onActivated: (i) => root.bridge.setBandType(root.sel, root.bridge.bandTypes[i].value)
            }
        }
        NumberField {
            label: "Frequency"
            value: root.band.freq || 1000
            decimals: (root.band.freq || 0) < 100 ? 1 : 0
            suffix: "Hz"
            from: 10; to: 22000
            step: 1 / 24; logStep: true
            onCommitted: (v) => root.bridge.setBandFreq(root.sel, v)
        }
        NumberField {
            label: "Gain"
            value: root.band.gain || 0
            signed: true
            suffix: "dB"
            from: -30; to: 30; step: 0.5
            fieldEnabled: !!root.band.hasGain
            onCommitted: (v) => root.bridge.setBandGain(root.sel, v)
        }
        NumberField {
            label: "Q"
            value: root.band.q || 0.707
            decimals: 2
            from: 0.05; to: 30
            step: 0.1; logStep: true
            onCommitted: (v) => root.bridge.setBandQ(root.sel, v)
        }
        Item { Layout.fillWidth: true }
        OSwitch {
            Layout.alignment: Qt.AlignBottom
            text: "On"
            checked: !!root.band.enabled
            onToggled: root.bridge.setBandEnabled(root.sel, checked)
        }
        OButton {
            Layout.alignment: Qt.AlignBottom
            text: root.bridge.solo === root.sel ? "Unsolo" : "Solo"
            checked: root.bridge.solo === root.sel
            compact: true
            onClicked: root.bridge.toggleSolo(root.sel)
        }
        OButton {
            Layout.alignment: Qt.AlignBottom
            text: "Delete"
            role: "destructive"
            compact: true
            onClicked: root.bridge.removeBand(root.sel)
        }
    }
    Text {
        anchors.centerIn: parent
        visible: !root.has
        text: root.bridge.bandCount ? "Select a band to edit it" : "Double-click the curve to add a band"
        color: Theme.textTertiary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.bodySize
    }
}
