import QtQuick
Item {
    id: glass
    property bool raised: false
    property real corner: 11
    BorderImage {
        anchors.fill: parent
        source: "image://assets/painted/panel"
        border { left: 20; top: 20; right: 20; bottom: 20 }
        opacity: glass.raised ? 1 : 0.94
    }
}
