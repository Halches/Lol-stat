import QtQuick
import QtQuick.Controls
Button {
    id: control
    property bool selected: false
    property string glyph: ""
    property bool navigation: false
    implicitWidth: label.implicitWidth + 42 + (glyph ? 26 : 0)
    implicitHeight: 35
    hoverEnabled: true
    background: Item {
        BorderImage {
            anchors.fill: parent
            source: "image://assets/painted/" + (control.selected ? "selected" : "button")
            border { left: 12; top: 12; right: 12; bottom: 12 }
        }
        Rectangle { anchors.fill: parent; anchors.margins: 2; radius: 7; color: control.down ? "#35090713" : control.hovered ? "#12f0c5ff" : "transparent" }
        Rectangle { anchors.fill: parent; anchors.margins: 3; radius: 6; color: "transparent"; border.color: control.activeFocus ? "#c4a0d2" : "transparent" }
    }
    contentItem: Item {
        Row {
            anchors.verticalCenter: parent.verticalCenter
            x: control.navigation ? 10 : (parent.width-width)/2
            spacing: 10
            Image { source: control.glyph ? "image://assets/nav/"+control.glyph : ""; visible: control.glyph !== ""; width: visible ? 19 : 0; height: 19; anchors.verticalCenter: parent.verticalCenter }
            T { id: label; text: control.text; font.pixelSize: 14; color: control.enabled ? "#f2e8f4" : "#c3b4cc" }
        }
    }
}
