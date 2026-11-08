import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 1536; height: 864
    minimumWidth: 940; minimumHeight: 640
    visible: true
    title: "LoL Helper — история матчей · Qt Quick"
    color: "#160e20"
    property string resultFilter: "all"
    property bool narrow: width < 1200
    function applyFilters() {
        history.setFilters(search.text, role.currentIndex, queue.currentIndex, resultFilter)
        matches.positionViewAtBeginning()
    }
    function resetFilters() {
        debounce.stop()
        search.text = ""; role.currentIndex = 0; queue.currentIndex = 0
        resultFilter = "all"; applyFilters()
    }
    function showMatch(index) { history.openMatch(index); details.open() }
    function closeDetails() { details.close() }
    Timer { id: debounce; interval: 150; onTriggered: window.applyFilters() }
    BorderImage {
        anchors.fill: parent; source: "image://assets/art/shell"
        border { left: 54; top: 54; right: 54; bottom: 54 }
        opacity: 0.81
    }
    Rectangle { x: 25; y: 25; width: parent.width-50; height: parent.height-50; radius: 13; color: "#29150e21" }
    Rectangle { x: 26; y: 26; width: 190; height: parent.height-52; color: "#28140d20" }
    Rectangle { x: 216; y: 25; width: 1; height: parent.height-52; color: "#69506f"; opacity: 0.65 }
    Item {
        x: 40; y: 32; width: 169; height: parent.height-64
        T { x: 13; text: "⬡"; color: "#e4c2ae"; font.pixelSize: 28 }
        T { x: 21; y: 7; text: "H"; color: "#e4c2ae"; font.family: serifFamily; font.pixelSize: 15; font.bold: true }
        T { x: 49; y: 5; text: "LOL HELPER"; color: "#e4c2ae"; font.family: serifFamily; font.pixelSize: 16; font.bold: true }
        T { x: 12; y: 51; text: "ИГРА"; color: "#bba2ce"; font.pixelSize: 12; font.letterSpacing: 1.2 }
        Column {
            y: 77; width: parent.width; spacing: 0
            Repeater {
                model: [{label:"Главная",icon:"home"}, {label:"История матчей",icon:"history"}, {label:"Мой пул",icon:"pool"}, {label:"Чемпион",icon:"list"}]
                BlossomButton {
                    required property var modelData
                    required property int index
                    width: 169; text: modelData.label; glyph: modelData.icon; navigation: true
                    selected: index === 1; enabled: index === 1
                    background.opacity: selected ? 1 : 0
                    onClicked: window.resetFilters()
                }
            }
            Item { width: 1; height: 20 }
            T { x: 12; height: 25; text: "НАСТРОЙКИ"; color: "#bba2ce"; font.pixelSize: 12; font.letterSpacing: 1.1 }
            Repeater {
                model: [{label:"Подсказки",icon:"bulb"}, {label:"Виджеты и окна",icon:"window"}, {label:"Вид",icon:"look"}, {label:"Звук",icon:"sound"}, {label:"Клавиши",icon:"keys"}, {label:"Таймеры",icon:"clock"}]
                BlossomButton { required property var modelData; width: 169; text: modelData.label; glyph: modelData.icon; navigation: true; enabled: false; background.opacity: 0 }
            }
        }
        T { x: 20; anchors.bottom: parent.bottom; anchors.bottomMargin: 14; text: "Локальный прототип"; font.pixelSize: 11; color: "#ac91ba" }
    }
    T { x: 250; y: 27; height: 38; text: "ИСТОРИЯ МАТЧЕЙ"; font.family: serifFamily; font.pixelSize: 25; font.bold: true; font.letterSpacing: 1.1 }
    Row {
        anchors.right: parent.right; anchors.rightMargin: 48; y: 39; spacing: 8
        Rectangle { width: 8; height: 8; radius: 4; color: "#64cfc6"; anchors.verticalCenter: parent.verticalCenter }
        T { text: "Qt Quick · локальные данные"; font.pixelSize: 12; color: "#c5b3d0" }
    }
    Rectangle { x: 235; y: 66; width: parent.width-278; height: 1; color: "#796083"; opacity: 0.65 }
    Item {
        id: body
        x: 248; y: 75; width: parent.width-x-46; height: parent.height-y-49
        T { text: "Матчи и разбор"; font.family: serifFamily; font.pixelSize: 25; color: "#e4c2ae"; height: 32 }
        Row {
            y: 36; spacing: 8
            BlossomButton { width: 189; text: "Сохранённые матчи"; selected: true; onClicked: window.resetFilters() }
            BlossomButton { width: 154; text: "Из клиента LoL"; enabled: false }
        }
        Column {
            visible: !window.narrow
            anchors.right: parent.right; y: 12; spacing: 7
            BlossomButton { text: "Сайт со статистикой"; glyph: "site"; width: 219; enabled: false; implicitHeight: 32 }
            BlossomButton { text: "Обновить из клиента"; glyph: "refresh"; width: 219; enabled: false; implicitHeight: 32 }
        }
        T { y: 79; width: parent.width; text: history.profileLabel; font.pixelSize: 14; color: "#cbb8d4" }
        Item {
            y: 104; width: parent.width; height: 62
            Glass { anchors.fill: parent; raised: true }
            TextField {
                id: search; objectName: "search"
                x: 15; y: 14; width: parent.width-role.width-queue.width-65; height: 35
                leftPadding: 42; rightPadding: 10
                color: "#eee0f0"; placeholderTextColor: "#cbb9d2"; placeholderText: "ПОИСК ЧЕМПИОНА ИЛИ ОППОНЕНТА"
                font.family: "Golos Text"; font.pixelSize: 14; selectByMouse: true
                background: Inset {
                    focused: search.activeFocus
                    Image { x: 12; y: 8; width: 20; height: 20; source: "image://assets/nav/search" }
                }
                onTextEdited: debounce.restart()
            }
            Column {
                x: parent.width-role.width-queue.width-35; y: 4; spacing: 1
                T { text: "РОЛЬ"; font.pixelSize: 11; color: "#cbb9d2"; font.letterSpacing: 1 }
                Choice { id: role; objectName: "roleChoice"; width: window.narrow ? 135 : 193; model: history.roles; onActivated: window.applyFilters() }
            }
            Column {
                anchors.right: parent.right; anchors.rightMargin: 15; y: 4; spacing: 1
                T { text: "РЕЖИМ"; font.pixelSize: 11; color: "#cbb9d2"; font.letterSpacing: 1 }
                Choice { id: queue; objectName: "queueChoice"; width: window.narrow ? 146 : 202; model: history.queueLabels; onActivated: window.applyFilters() }
            }
        }
        Row {
            y: 176; spacing: 8
            BlossomButton { objectName: "allButton"; width: 160; text: "Все результаты"; selected: window.resultFilter === "all"; onClicked: { window.resultFilter="all"; window.applyFilters() } }
            BlossomButton { objectName: "winButton"; width: 105; text: "Победы"; selected: window.resultFilter === "win"; onClicked: { window.resultFilter="win"; window.applyFilters() } }
            BlossomButton { objectName: "lossButton"; width: 132; text: "Поражения"; selected: window.resultFilter === "loss"; onClicked: { window.resultFilter="loss"; window.applyFilters() } }
        }
        BlossomButton { objectName: "resetButton"; anchors.right: parent.right; y: 176; text: "Сбросить"; onClicked: window.resetFilters() }
        Item {
            y: 221; width: parent.width; height: 101
            Glass { anchors.fill: parent; raised: true }
            Row {
                anchors.fill: parent; anchors.margins: 12
                Repeater {
                    model: [
                        {label:"МАТЧИ",value:history.summary.n,note:"В текущем фильтре"},
                        {label:"ПОБЕДЫ",value:history.summary.wins,note:"Результат известен: " + history.summary.known},
                        {label:"KDA",value:history.summary.kda,note:"По " + history.summary.kdaCount + " матчам"},
                        {label:"ФАРМ / МИН",value:history.summary.farm,note:"По " + history.summary.farmCount + " матчам"}]
                    Item {
                        required property var modelData; required property int index
                        width: parent.width/4; height: parent.height
                        Rectangle { visible: index > 0; width: 1; y: 7; height: 62; color: "#715a7b"; opacity: 0.55 }
                        Column { x: 14; width: parent.width-22; spacing: 0
                            T { width: parent.width; height: 16; text: modelData.label; font.pixelSize: 12; font.letterSpacing: 1.5; color: "#cdb8d8" }
                            T { height: 44; text: modelData.value; font.family: serifFamily; font.pixelSize: window.narrow ? 34 : 38; font.bold: true; style: Text.Raised; styleColor: "#3e244b" }
                            T { width: parent.width; height: 18; text: modelData.note; color: "#cbb9d2"; font.pixelSize: window.narrow ? 11 : 13 }
                        }
                    }
                }
            }
        }
        T { y: 333; width: parent.width; text: "Нажми на матч для подробностей. LP показывается при наличии снимков ранга до и после игры."; font.pixelSize: 12; color: "#cbb9d2" }
        T { y: 357; text: "Найдено " + history.summary.n + " из " + history.summary.total; font.pixelSize: 13; color: "#ddcde3" }
        ListView {
            id: matches; objectName: "matchList"
            y: 377; width: parent.width; height: parent.height-y
            clip: true; spacing: 6; model: history.matchModel; reuseItems: true
            boundsBehavior: Flickable.StopAtBounds; cacheBuffer: 90
            property int liveDelegates: contentItem.children.length
            delegate: MatchRow { width: matches.width-5; onActivated: row => window.showMatch(row) }
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 5 }
            T { anchors.centerIn: parent; visible: matches.count === 0; text: "Ничего не найдено. Измени фильтры."; color: "#cab4d5" }
        }
    }
    Dialog {
        id: details; objectName: "matchDialog"
        anchors.centerIn: parent; width: Math.min(640, window.width-70); modal: true
        padding: 24
        background: Item { Rectangle { anchors.fill: parent; radius: 12; color: "#261a32" } Glass { anchors.fill: parent; raised: true } }
        header: T { text: "Сохранённый матч"; padding: 24; font.family: serifFamily; font.pixelSize: 24 }
        contentItem: Column {
            spacing: 16
            Row { spacing: 16
                Image { width: 64; height: 64; source: history.detail.portrait || "" }
                Column { spacing: 5
                    T { text: history.detail.champion || ""; font.family: serifFamily; font.pixelSize: 25 }
                    T { text: history.detail.subtitle || ""; color: "#cab4d5" }
                }
            }
            T { text: (history.detail.result || "") + "   ·   " + (history.detail.score || ""); color: history.detail.tone || "#eee0f0"; font.pixelSize: 23 }
            Row { spacing: 5; Repeater { model: history.detail.equipment || []; Image { required property string modelData; width: 32; height: 32; source: modelData } } }
            T { text: "Золото: " + (history.detail.gold ?? "—") + "    Урон: " + (history.detail.damage ?? "—") + "    CS: " + (history.detail.cs ?? "—") }
            T { text: "Оппонент: " + (history.detail.opponent || "—") + "    ·    " + (history.detail.duration || "") }
            T { width: parent.width; wrapMode: Text.WordWrap; text: "Показаны данные локального архива. Полный разбор матча остаётся в основной программе."; color: "#bba4c6"; font.pixelSize: 12 }
            BlossomButton { text: "Закрыть"; onClicked: details.close() }
        }
    }
}
