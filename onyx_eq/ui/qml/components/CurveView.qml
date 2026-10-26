import QtQuick
import QtQuick.Shapes
import QtQuick.Controls.Basic
import "../theme"

// The frequency-response editor. All maths comes from the bridge; this only maps values to pixels.
Item {
    id: root
    objectName: "curveView"
    required property var bridge
    property bool editable: bridge.mode === "parametric"

    readonly property real fmin: bridge.curveMinHz
    readonly property real fmax: bridge.curveMaxHz
    readonly property real range: bridge.rangeDb
    readonly property real gridStep: range <= 6 ? Theme.gridDbStep / 2 : range >= 24 ? Theme.gridDbStep * 2 : Theme.gridDbStep

    // ---- coordinate mapping (pixels <-> Hz / dB) -------------------------------------------
    function xOf(f) { return plot.width * Math.log(f / fmin) / Math.log(fmax / fmin) }
    function fOf(x) { return fmin * Math.pow(fmax / fmin, x / plot.width) }
    function yOf(db) { return plot.height / 2 - db / range * (plot.height / 2) }
    function dbOf(y) { return (plot.height / 2 - y) / (plot.height / 2) * range }
    function clampY(y) { return Math.max(0, Math.min(plot.height, y)) }

    // ---- curve morph between presets ------------------------------------------------------
    property var fromCurve: []
    property var toCurve: bridge.curve
    property real morph: 1
    property bool pendingMorph: false
    readonly property var shownCurve: {
        if (morph >= 1 || fromCurve.length !== toCurve.length) return toCurve
        var out = new Array(toCurve.length)
        for (var i = 0; i < toCurve.length; ++i) out[i] = fromCurve[i] + (toCurve[i] - fromCurve[i]) * morph
        return out
    }
    NumberAnimation { id: morphAnim; target: root; property: "morph"; from: 0; to: 1; duration: Theme.durationMorph; easing.type: Theme.easing }
    Connections {
        target: root.bridge
        function onCurveMorph() { root.pendingMorph = true }
        function onCurveChanged() {
            if (root.pendingMorph) {
                root.pendingMorph = false
                root.fromCurve = root.shownCurve
                root.toCurve = root.bridge.curve
                morphAnim.restart()
            } else {
                root.toCurve = root.bridge.curve
            }
        }
    }

    function points(arr) {
        var n = arr.length, w = plot.width, pts = new Array(n)
        for (var i = 0; i < n; ++i) pts[i] = Qt.point(i / (n - 1) * w, yOf(arr[i]))
        return pts
    }
    readonly property var curvePts: plot.width > 0 && shownCurve.length > 1 ? points(shownCurve) : []
    readonly property var fillPts: curvePts.length ? curvePts.concat([Qt.point(plot.width, yOf(0)), Qt.point(0, yOf(0))]) : []
    readonly property var bandPts: plot.width > 0 && bridge.bandCurve.length > 1 && editable ? points(bridge.bandCurve) : []
    readonly property color selectedColor: Theme.bandColor(bridge.selected)

    // ---- plot area -------------------------------------------------------------------------
    Item {
        id: plot
        objectName: "plot"
        anchors.fill: parent
        anchors.topMargin: Theme.spacingM
        anchors.bottomMargin: Theme.spacingL
        anchors.leftMargin: Theme.spacingS
        anchors.rightMargin: Theme.spacingL + Theme.spacingS
        clip: false

        // grid: frequency lines
        Repeater {
            model: Theme.gridFreqs
            delegate: Item {
                required property var modelData
                x: root.xOf(modelData)
                height: plot.height
                Rectangle { width: 1; height: parent.height; color: Theme.gridLine }
                Text {
                    y: plot.height + Theme.spacingXs
                    x: -width / 2
                    text: root.bridge.formatHz(parent.modelData)
                    color: Theme.gridLabel
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.smallSize
                    font.features: Theme.tabular
                }
            }
        }
        // grid: dB lines
        Repeater {
            model: Math.floor(root.range / root.gridStep) * 2 + 1
            delegate: Item {
                required property int index
                readonly property real db: root.range - index * root.gridStep
                y: root.yOf(db)
                width: plot.width
                Rectangle { width: parent.width; height: 1; color: parent.db === 0 ? Theme.gridZero : Theme.gridLine }
                Text {
                    x: plot.width + Theme.spacingS
                    y: -height / 2
                    text: (parent.db > 0 ? "+" : "") + parent.db
                    color: Theme.gridLabel
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.smallSize
                    font.features: Theme.tabular
                }
            }
        }

        // curves
        Item {
            anchors.fill: parent
            clip: true
            opacity: root.bridge.bypass ? 0.35 : 1
            Behavior on opacity { NumberAnimation { duration: Theme.duration } }

            Shape {
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                // composite fill, fading to transparent at 0 dB
                ShapePath {
                    strokeWidth: -1
                    fillGradient: LinearGradient {
                        x1: 0; y1: 0; x2: 0; y2: plot.height
                        GradientStop { position: 0; color: Theme.alpha(Theme.accent, Theme.curveFillOpacity) }
                        GradientStop { position: 0.5; color: Theme.alpha(Theme.accent, 0) }
                        GradientStop { position: 1; color: Theme.alpha(Theme.accent, Theme.curveFillOpacity) }
                    }
                    PathPolyline { path: root.fillPts }
                }
                // selected band's own curve
                ShapePath {
                    strokeWidth: 1.5
                    strokeColor: Theme.alpha(root.selectedColor, Theme.bandCurveOpacity)
                    fillColor: "transparent"
                    PathPolyline { path: root.bandPts }
                }
                // glow + line
                ShapePath {
                    strokeWidth: Theme.curveGlowWidth
                    strokeColor: Theme.alpha(Theme.accent, Theme.curveGlowOpacity / 2)
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    PathPolyline { path: root.curvePts }
                }
                ShapePath {
                    strokeWidth: Theme.curveGlowWidth / 2
                    strokeColor: Theme.alpha(Theme.accent, Theme.curveGlowOpacity)
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    PathPolyline { path: root.curvePts }
                }
                ShapePath {
                    strokeWidth: Theme.curveWidth
                    strokeColor: root.bridge.clipping ? Theme.warning : Theme.accent
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    PathPolyline { path: root.curvePts }
                }
            }
        }

        // background interactions: double-click adds a band, click deselects, hover readout
        MouseArea {
            id: bgArea
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            onClicked: root.bridge.selected = -1
            onDoubleClicked: (m) => {
                if (root.editable)
                    root.bridge.addBand(root.fOf(m.x), Math.round(root.dbOf(m.y) * 10) / 10)
            }
        }

        // hover readout
        Text {
            id: readout
            visible: bgArea.containsMouse && root.shownCurve.length > 1
            readonly property int idx: Math.round(Math.max(0, Math.min(1, bgArea.mouseX / plot.width)) * (root.shownCurve.length - 1))
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.rightMargin: Theme.spacingS
            text: root.bridge.formatHz(root.fOf(bgArea.mouseX)) + " Hz   " +
                  (root.shownCurve[idx] >= 0 ? "+" : "") + (root.shownCurve[idx] || 0).toFixed(1) + " dB"
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            font.features: Theme.tabular
        }
        Rectangle {
            visible: readout.visible
            x: bgArea.mouseX
            width: 1
            height: plot.height
            color: Theme.hairline
        }

        // band dots
        Repeater {
            model: root.editable ? root.bridge.bandModel : null
            delegate: BandDot {
                curve: root
                bridge: root.bridge
                onContextMenu: (i) => { bandMenu.bandIndex = i; bandMenu.popup() }
            }
        }
    }

    // ---- per-band context menu -------------------------------------------------------------
    OMenu {
        id: bandMenu
        property int bandIndex: -1
        OMenu {
            id: typeMenu
            title: "Type"
            Instantiator {
                model: root.bridge.bandTypes
                delegate: MenuItem {
                    required property var modelData
                    text: modelData.name
                    checkable: true
                    checked: bandMenu.bandIndex >= 0 && root.bridge.bandTypeAt(bandMenu.bandIndex) === modelData.value
                    onTriggered: root.bridge.setBandType(bandMenu.bandIndex, modelData.value)
                }
                onObjectAdded: (i, o) => typeMenu.insertItem(i, o)
                onObjectRemoved: (i, o) => typeMenu.removeItem(o)
            }
        }
        MenuItem {
            text: bandMenu.bandIndex >= 0 && root.bridge.bandEnabledAt(bandMenu.bandIndex) ? "Disable" : "Enable"
            onTriggered: root.bridge.setBandEnabled(bandMenu.bandIndex, !root.bridge.bandEnabledAt(bandMenu.bandIndex))
        }
        MenuItem {
            text: root.bridge.solo === bandMenu.bandIndex ? "Unsolo" : "Solo"
            onTriggered: root.bridge.toggleSolo(bandMenu.bandIndex)
        }
        MenuItem {
            text: "Reset Gain"
            onTriggered: root.bridge.resetGain(bandMenu.bandIndex)
        }
        MenuSep {}
        MenuItem {
            action: OAction { text: "Delete"; destructive: true; onTriggered: root.bridge.removeBand(bandMenu.bandIndex) }
        }
    }
}
