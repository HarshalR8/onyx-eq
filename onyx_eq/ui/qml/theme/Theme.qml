pragma Singleton
import QtQuick

// Every colour, radius, font size, spacing and duration lives here. Nothing is hard-coded elsewhere.
QtObject {
    // colours
    readonly property color background: "#000000"
    readonly property color surface: "#1C1C1E"
    readonly property color surface2: "#2C2C2E"
    readonly property color surface3: "#3A3A3C"
    readonly property color separator: "#38383A"
    readonly property color hairline: Qt.rgba(1, 1, 1, 0.08)
    readonly property color textPrimary: "#FFFFFF"
    readonly property color textSecondary: Qt.rgba(235 / 255, 235 / 255, 245 / 255, 0.6)
    readonly property color textTertiary: Qt.rgba(235 / 255, 235 / 255, 245 / 255, 0.3)
    readonly property color accent: "#0A84FF"
    readonly property color destructive: "#FF453A"
    readonly property color positive: "#30D158"
    readonly property color warning: "#FF9F0A"
    readonly property color scrim: Qt.rgba(0, 0, 0, 0.6)
    readonly property var bandColors: ["#0A84FF", "#30D158", "#FF9F0A", "#FF375F", "#BF5AF2", "#64D2FF", "#FFD60A", "#AC8E68"]
    function bandColor(i) { return bandColors[((i % bandColors.length) + bandColors.length) % bandColors.length] }
    function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

    // curve view
    readonly property color gridLine: Qt.rgba(1, 1, 1, 0.06)
    readonly property color gridZero: Qt.rgba(1, 1, 1, 0.16)
    readonly property color gridLabel: Qt.rgba(235 / 255, 235 / 255, 245 / 255, 0.3)
    readonly property real curveWidth: 2
    readonly property real curveGlowWidth: 8
    readonly property real curveGlowOpacity: 0.18
    readonly property real curveFillOpacity: 0.28
    readonly property real bandCurveOpacity: 0.35
    readonly property real dotSize: 14
    readonly property real dotSelectedSize: 18
    readonly property real dotHitSize: 32
    readonly property real disabledOpacity: 0.35
    readonly property var gridFreqs: [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    readonly property real gridDbStep: 6

    // type
    readonly property string fontFamily: Qt.application.font.family
    readonly property int titleSize: 28
    readonly property int headlineSize: 17
    readonly property int bodySize: 15
    readonly property int captionSize: 12
    readonly property int smallSize: 11
    readonly property int weightRegular: Font.Normal
    readonly property int weightMedium: Font.Medium
    readonly property int weightSemibold: Font.DemiBold
    readonly property var tabular: ({ "tnum": 1 })

    // shape & spacing (8-pt grid)
    readonly property int radiusControl: 12
    readonly property int radiusCard: 16
    readonly property int radiusSheet: 22
    readonly property int radiusSmall: 8
    readonly property int unit: 8
    readonly property int spacingXs: 4
    readonly property int spacingS: 8
    readonly property int spacingM: 16
    readonly property int spacingL: 24
    readonly property int controlHeight: 32
    readonly property int controlHeightSmall: 28
    readonly property int bandCardWidth: 148
    readonly property int bandCardHeight: 92
    readonly property int sliderWidth: 34
    readonly property int sliderTrack: 4
    readonly property int sliderKnob: 20
    readonly property int toolbarHeight: 56
    readonly property int sheetWidth: 440
    readonly property int windowMinWidth: 820
    readonly property int windowMinHeight: 620

    // motion
    readonly property int durationFast: 120
    readonly property int duration: 220
    readonly property int durationMorph: 250
    readonly property int easing: Easing.OutCubic
}
