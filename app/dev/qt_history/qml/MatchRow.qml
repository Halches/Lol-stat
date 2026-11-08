import QtQuick
import QtQuick.Controls
Item {
    id: card
    required property var record
    required property int index
    property color tone: record.tone
    property bool compact: width < 1000
    signal activated(int row)
    height: compact ? 98 : 66
    Glass { anchors.fill: parent }
    Rectangle { x: 12; y: 8; width: 5; height: parent.height-18; radius: 2; color: card.record.tone }
    Rectangle { x: 31; y: 8; width: 50; height: 50; radius: 5; color: "#211427"; border.color: "#886280" }
    Image { x: 33; y: 10; width: 46; height: 46; source: card.record.portrait; asynchronous: false }
    Column {
        x: 108; y: 9; width: card.compact ? parent.width-480 : (card.width > 1160 ? 232 : 173); spacing: 2
        T { width: parent.width; text: card.record.champion; font.family: serifFamily; font.pixelSize: 20; font.bold: true }
        T { width: parent.width; text: card.record.subtitle; color: "#c7b6d0" }
    }
    Column {
        x: card.compact ? 108 : (card.width > 1160 ? 360 : 290); y: card.compact ? 65 : 8
        spacing: 4
        T { visible: !card.compact; text: "ЗАКЛИНАНИЯ · РУНА · ПРЕДМЕТЫ"; font.pixelSize: 12; color: "#c7b6d0" }
        Row { spacing: 3; Repeater { model: card.record.equipment; Image { required property string modelData; width: 24; height: 24; source: modelData } } }
    }
    Column { visible: !card.compact || card.width > 740; x: card.compact ? parent.width-310 : parent.width-465; y: card.compact ? 59 : 14; spacing: card.compact ? 0 : 5
        T { text: card.record.participation; color: "#d1c1d8"; font.pixelSize: card.compact ? 12 : 14 }
        T { text: card.record.vision; color: "#c7b6d0"; font.pixelSize: card.compact ? 12 : 14 }
    }
    Rectangle { visible: !card.compact; x: parent.width-335; y: 10; width: 1; height: parent.height-20; color: "#51685173" }
    Column { x: parent.width-350; y: 8; width: 155; spacing: 3
        T { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: card.record.score; font.family: serifFamily; font.pixelSize: 23; font.bold: true }
        T { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: card.record.farm; color: "#c7b6d0" }
    }
    Column { x: parent.width-201; y: 8; width: 112; spacing: 5
        Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: Math.max(80, outcome.implicitWidth+20); height: 23; radius: 10; border.color: Qt.rgba(card.tone.r, card.tone.g, card.tone.b, 0.28)
            gradient: Gradient { GradientStop { position: 0; color: Qt.rgba(card.tone.r, card.tone.g, card.tone.b, 0.23) } GradientStop { position: 1; color: Qt.rgba(card.tone.r*0.4, card.tone.g*0.4, card.tone.b*0.4, 0.25) } }
            T { id: outcome; anchors.centerIn: parent; text: card.record.result; font.pixelSize: 13; color: card.record.tone }
        }
        T { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: card.record.duration; color: "#c7b6d0" }
    }
    T { x: parent.width-55; y: 40; width: 45; text: card.record.lp; font.pixelSize: 12; horizontalAlignment: Text.AlignRight; color: "#c7b6d0" }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: card.activated(card.index) }
    activeFocusOnTab: true
    Keys.onReturnPressed: activated(index)
    Rectangle { anchors.fill: parent; anchors.margins: 2; color: "transparent"; radius: 10; border.color: card.activeFocus ? "#e0b9eb" : "transparent" }
}
