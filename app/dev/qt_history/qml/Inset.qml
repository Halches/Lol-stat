import QtQuick
Rectangle {
    id: field
    property bool focused: false
    radius: 8; border.color: focused ? "#bc92ce" : "#6a5276"
    gradient: Gradient {
        GradientStop { position: 0; color: "#65516f" }
        GradientStop { position: 0.10; color: "#4a3656" }
        GradientStop { position: 0.65; color: "#2b1f36" }
        GradientStop { position: 1; color: "#39293f" }
    }
    Rectangle { x: 8; y: parent.height-2; width: parent.width-16; height: 1; color: "#8a6794"; opacity: 0.35 }
    Rectangle { anchors.fill: parent; anchors.margins: 2; radius: 6; color: "transparent"; border.color: "#180b0611" }
}
