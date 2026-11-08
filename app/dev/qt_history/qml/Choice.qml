import QtQuick
import QtQuick.Controls
ComboBox {
    id: control
    implicitHeight: 32
    leftPadding: 10; rightPadding: 30
    background: Inset { focused: control.activeFocus }
    contentItem: T { text: control.displayText }
    indicator: T { text: "⌄"; x: control.width-25; y: 0; height: control.height; font.pixelSize: 21; color: "#c7b5d1" }
    delegate: ItemDelegate {
        required property var modelData
        required property int index
        width: control.width
        contentItem: T { text: modelData }
        background: Rectangle { color: parent.highlighted ? "#674c76" : "#2c2037" }
        highlighted: control.highlightedIndex === index
    }
    popup: Popup {
        y: control.height+3; width: control.width; padding: 1
        implicitHeight: contentItem.implicitHeight + 2
        background: Rectangle { color: "#2c2037"; radius: 6; border.color: "#81658e" }
        contentItem: ListView { clip: true; implicitHeight: Math.min(contentHeight, 260); model: control.popup.visible ? control.delegateModel : null; currentIndex: control.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator {} }
    }
}
