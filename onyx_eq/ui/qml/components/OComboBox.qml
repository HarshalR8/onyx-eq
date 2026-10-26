import QtQuick
import QtQuick.Controls.Basic
import "../theme"

ComboBox {
    id: control
    property string prefix: ""
    implicitHeight: Theme.controlHeight
    implicitWidth: 200
    font.family: Theme.fontFamily
    font.pixelSize: Theme.bodySize - 1
    focusPolicy: Qt.NoFocus
    leftPadding: Theme.spacingM
    rightPadding: Theme.spacingL + Theme.spacingS

    background: Rectangle {
        radius: Theme.radiusControl
        color: control.pressed ? Theme.surface3 : Theme.surface2
    }
    contentItem: Text {
        text: (control.prefix ? control.prefix + "  " : "") + control.displayText
        font: control.font
        color: Theme.textPrimary
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Text {
        x: control.width - width - Theme.spacingM + 2
        anchors.verticalCenter: parent.verticalCenter
        text: "⌄"
        color: Theme.textSecondary
        font.family: Theme.fontFamily
        font.pixelSize: Theme.bodySize
    }
    delegate: ItemDelegate {
        id: d
        required property int index
        required property var modelData
        width: ListView.view ? ListView.view.width : control.width
        height: Theme.controlHeight + 4
        hoverEnabled: true
        contentItem: Text {
            text: control.textRole ? d.modelData[control.textRole] : d.modelData
            font: control.font
            color: Theme.textPrimary
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
            leftPadding: Theme.spacingS
        }
        background: Rectangle {
            radius: Theme.radiusSmall
            color: d.hovered ? Theme.surface3 : "transparent"
        }
        Text {
            visible: control.currentIndex === d.index
            anchors.right: parent.right
            anchors.rightMargin: Theme.spacingM
            anchors.verticalCenter: parent.verticalCenter
            text: "✓"
            color: Theme.accent
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
        }
    }
    popup: Popup {
        y: control.height + Theme.spacingXs
        width: Math.max(control.width, 240)
        implicitHeight: Math.min(contentItem.implicitHeight + 2 * padding, 360)
        padding: Theme.spacingXs + 2
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            boundsBehavior: Flickable.StopAtBounds
        }
        background: Rectangle {
            radius: Theme.radiusControl
            color: Theme.surface
            border.width: 1
            border.color: Theme.hairline
        }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.durationFast } }
    }
}
