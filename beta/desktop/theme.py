STYLE = """
QWidget {
    color: #f2eef8;
    font-family: "Segoe UI";
    font-size: 14px;
}
QWidget#main, QWidget#body, QScrollArea { background: #0e0e15; }
QScrollBar:vertical { background: #13111a; width: 8px; margin: 2px 0; }
QScrollBar::handle:vertical { background: #4e4164; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QLabel { background: transparent; }
QLabel[role="brand"] {
    background: #302747; border: 1px solid #69568f; border-radius: 10px;
    color: #d4c4ff; font-size: 22px; font-weight: 700;
}
QLabel[role="title"] { font-size: 25px; font-weight: 700; }
QLabel[role="headline"] { font-size: 34px; font-weight: 700; }
QLabel[role="section"] { font-size: 19px; font-weight: 700; }
QLabel[role="muted"], QLabel[role="itemName"] { color: #b7afc7; }
QLabel[role="itemName"] { font-size: 12px; }
QLabel[role="caption"] { color: #9e95b1; font-size: 12px; }
QLabel[role="captionStrong"] { color: #dbd2ec; font-size: 12px; font-weight: 600; }
QLabel[role="chip"] {
    background: #261f37; border: 1px solid #4c3c67; border-radius: 7px;
    color: #d1befb; font-size: 12px; font-weight: 600; padding: 5px 9px;
}
QLabel[role="footer"] { color: #9189a1; font-size: 11px; }
QLabel[role="notice"] { color: #d1befb; }
QFrame[role="panel"] { background: #171620; border: 1px solid #302b3d; border-radius: 14px; }
QFrame[role="homeSearch"], QFrame[role="homePanel"] {
    background: #18171f; border: 1px solid #302c3b; border-radius: 14px;
}
QFrame[role="homePlaceholder"] {
    background: #14131b; border: 1px solid #2a2635; border-radius: 14px;
}
QLabel[role="homeConnection"] {
    background: #1e1b2a; border: 1px solid #373044; border-radius: 12px;
    color: #c7bbdc; font-size: 13px; padding: 5px 11px;
}
QLabel[role="homeSection"] { font-size: 18px; font-weight: 650; }
QFrame[role="homeSearch"] QLabel[role="homeSection"] { font-size: 22px; }
QLabel[role="homeField"] { color: #d4cbe2; font-size: 12px; font-weight: 600; }
QLabel[role="homeSecondary"] { color: #a9a0b9; font-size: 13px; }
QLabel[role="previewChampion"] { font-size: 28px; font-weight: 700; }
QFrame#dashboardSidebar {
    border-right: 1px solid #2c2936;
    background: qlineargradient(x1:0, y1:0, x2:0.7, y2:1,
                                stop:0 #231e31, stop:0.4 #15141d, stop:1 #101017);
}
QLabel[role="dashboardBrand"] { color: #f2edf8; font-size: 16px; font-weight: 700; }
QLabel[role="dashboardTitle"] { color: #f4effa; font-size: 32px; font-weight: 700; }
QLabel[role="dashboardSection"] { color: #eeeaf4; font-size: 21px; font-weight: 650; }
QFrame[role="dashboardPanel"], QFrame[role="dashboardProfile"] {
    background: #18171f; border: 1px solid #322e3d; border-radius: 14px;
}
QFrame[role="dashboardProfile"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #292234, stop:0.65 #1d1a26, stop:1 #18171f);
    border-color: #3c334b;
}
QLabel[role="dashboardEyebrow"] { color: #cfc4df; font-size: 14px; font-weight: 650; }
QLabel[role="dashboardMuted"] { color: #aaa1b7; font-size: 13px; }
QLabel[role="dashboardProfileName"] { color: #f5f0fa; font-size: 27px; font-weight: 700; }
QLabel[role="dashboardRankName"] { color: #f0eaf7; font-size: 20px; font-weight: 650; }
QLabel[role="dashboardLP"] {
    background: #24202f; border: 1px solid #3b334a; border-radius: 7px;
    color: #d0bde7; font-size: 13px; font-weight: 600; padding: 4px 7px;
}
QLabel[role="dashboardPercent"] { color: #e9def5; font-size: 23px; font-weight: 700; }
QWidget[role="dashboardDivider"] { background: #342e3f; }
QLabel[role="dashboardAvatar"] {
    color: #c9b8e1; font-weight: 650; background: #242030; border: 1px solid #4a3c5e; border-radius: 9px;
}
QLabel[role="dashboardMatchName"] { color: #f5f0fa; font-size: 21px; font-weight: 700; }
QLabel[role="dashboardMatchStat"] { color: #f4edf9; font-size: 20px; font-weight: 700; }
QLabel[role="dashboardOutcome"] { font-size: 13px; font-weight: 650; }
QLabel[role="dashboardMatchMeta"] { color: #c5bbd1; font-size: 13px; }
QFrame[role="draftSide"] { background: #13121b; border: 1px solid #3b324e; border-radius: 13px; }
QLabel[role="draftChampion"] { color: #f4effb; font-size: 17px; font-weight: 700; }
QLabel[role="draftTeam"] { color: #d8cce9; font-size: 14px; font-weight: 700; }
QLabel[role="draftPlayerName"] { color: #eadffd; font-size: 12px; font-weight: 600; }
QLabel[role="draftCardDetail"] { color: #c7bcd4; font-size: 11px; }
QLabel[role="draftPlayerComment"] { color: #dac9ea; font-size: 11px; font-weight: 600; }
QLabel[role="draftPlayerComment"][tone="good"] { color: #a7dec2; }
QLabel[role="draftPlayerComment"][tone="bad"] { color: #f2abb7; }
QLabel[role="draftPlayerComment"][tone="neutral"] { color: #e7c89b; }
QDialog#draftCommentPopup { background: #191622; border: 1px solid #584469; }
QDialog#draftCommentPopup QScrollArea, QWidget#draftCommentRows { background: #191622; }
QLabel[role="draftCommentHeading"] { color: #dac9ea; font-size: 12px; font-weight: 600; }
QLabel[role="draftCommentHeading"][tone="good"] { color: #a7dec2; }
QLabel[role="draftCommentHeading"][tone="bad"] { color: #f2abb7; }
QLabel[role="draftCommentHeading"][tone="neutral"] { color: #e7c89b; }
QLabel[role="draftCommentDetail"] { color: #c7bcd4; font-size: 11px; }
QLabel[role="draftTag"] { background: #222031; border: 1px solid #544861; border-radius: 5px;
                         color: #dcc9ee; padding: 2px 5px; font-size: 10px; font-weight: 600; }
QLabel[role="draftTag"][tone="good"] { background: #142820; border-color: #375a49; color: #a7dec2; }
QLabel[role="draftTag"][tone="bad"] { background: #301c26; border-color: #754356; color: #f2abb7; }
QLabel[role="draftTag"][tone="neutral"] { background: #31271e; border-color: #745b3d; color: #e7c89b; }
QLabel[role="draftSuggestionIcon"] { background: transparent; border: 0; color: #cfbfdc; font-size: 11px; }
QLabel[role="draftOptionTitle"] { color: #dfd0f0; font-size: 12px; font-weight: 600; }
QLabel[role="draftOptionName"] { color: #cfbfdc; font-size: 10px; }
QLabel[role="draftBadge"] { color: #eadfff; background: #35284c; border: 1px solid #725c94;
                           border-radius: 5px; font-size: 11px; font-weight: 700; padding: 3px 6px; }
QFrame[role="item"] { background: #1c1a27; border: 1px solid #332d42; border-radius: 9px; }
QFrame[role="item"]:hover { border-color: #665283; }
QFrame[role="loadout"] { background: #1b1826; border: 1px solid #362d49; border-radius: 9px; }
QLabel[role="icon"] {
    background: #29243b; border: 1px solid #473c5d; border-radius: 6px;
    color: #c3b4df; font-size: 12px; font-weight: 600;
}
QLabel[role="rune"] {
    background: #251f32; border: 1px solid #534366; border-radius: 11px;
    color: #c3b4df; font-size: 10px; font-weight: 600;
}
QToolTip { color: #eee8fa; background: #241c32; border: 1px solid #65537e; padding: 4px; }
QPushButton, QLineEdit, QComboBox {
    background: #211d2e; border: 1px solid #3e344e; border-radius: 8px;
    padding: 8px 12px; min-height: 20px;
}
QPushButton { font-weight: 600; }
QPushButton:hover { background: #2d263d; border-color: #665386; }
QPushButton:pressed { background: #362c50; }
QPushButton:disabled { color: #837a94; background: #211e2b; border-color: #332c42; }
QPushButton:focus, QCheckBox:focus, QLineEdit:focus, QComboBox:focus { border-color: #a78edc; }
QPushButton[role="primary"] { color: #160f24; background: #bba3ef; border-color: #d0b8fb; }
QPushButton[role="primary"]:hover { background: #d0b8fb; }
QPushButton[role="primary"]:pressed { background: #a68edc; }
QPushButton[role="primary"]:disabled { color: #9a8fae; background: #2b2438; border-color: #433453; }
QPushButton[role="tab"] { color: #c6bbda; font-size: 13px; min-height: 17px; padding: 6px 11px; }
QPushButton[role="tab"]:checked {
    color: #eadfff; background: #35284c; border-color: #795fa3;
}
QPushButton[role="dashboardNav"] {
    text-align: left; color: #bfb5cd; font-size: 14px; font-weight: 600;
    background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 10px 8px;
}
QPushButton[role="dashboardNav"]:hover { background: #211d2b; border-color: #3e344c; }
QPushButton[role="dashboardNav"]:checked {
    color: #f1e9fc; background: #31273f; border: 1px solid #4c3d61; border-left: 3px solid #b09aca;
}
QPushButton[role="dashboardNav"]:focus, QPushButton[role="dashboardReview"]:focus,
QComboBox[role="dashboardQueue"]:focus { border-color: #c5ace7; }
QPushButton[role="dashboardReview"], QComboBox[role="dashboardQueue"] {
    min-height: 17px; padding: 5px 9px; font-size: 13px;
}
QComboBox[role="dashboardQueue"] { min-width: 80px; }
QPushButton[role="buildChoice"], QComboBox[role="buildChoice"] {
    color: #c6bbda; font-size: 13px; font-weight: 600; min-height: 17px; min-width: 0;
    padding: 6px 11px; text-align: left; background: #211d2e; border-color: #3e344e;
}
QComboBox[role="buildChoice"] { combobox-popup: 0; padding-right: 27px; }
QComboBox[role="buildChoice"]::drop-down { width: 22px; border: 0; }
QPushButton[role="buildChoice"]:hover, QComboBox[role="buildChoice"]:hover { border-color: #665386; }
QPushButton[role="buildChoice"]:focus, QComboBox[role="buildChoice"]:focus { border-color: #a78edc; }
QPushButton[role="buildChoice"]:checked, QComboBox[role="buildChoice"][chosen="true"] {
    color: #eadfff; background: #35284c; border-color: #795fa3;
}
QPushButton[role="draftMoreComments"] {
    color: #d8c5fb; background: #332548; border: 1px solid #685589;
    border-radius: 5px; padding: 0 5px; font-size: 10px; min-height: 0;
}
QPushButton[role="draftMoreComments"]:hover { background: #4b3667; }
QPushButton[role="draftMoreComments"]:focus { border-color: #c5a9ff; }
QPushButton[role="draftDetailsButton"] {
    color: #ddd1ef; background: #181421; border: 1px solid #655475;
    border-radius: 6px; padding: 0; min-height: 0;
}
QPushButton[role="draftDetailsButton"]:focus { border: 2px solid #e3d0ff; }
QLineEdit { background: #14131c; color: #d6d0e1; selection-background-color: #695489; }
QComboBox { background: #14131c; color: #d6d0e1; min-width: 115px; }
QComboBox[role="draftRoleIcon"] {
    combobox-popup: 0; padding: 0; min-height: 0; min-width: 0;
    background: #181421; border: 1px solid #655475; border-radius: 7px;
}
QComboBox[role="draftRoleIcon"][manual="true"] { background: #392c50; border-color: #b18de8; }
QComboBox[role="draftRoleIcon"]:hover, QComboBox[role="draftRoleIcon"]:focus { border-color: #c5a9ff; }
QComboBox[role="draftRoleIcon"]::drop-down { width: 0; border: 0; }
QComboBox[role="draftRoleIcon"]::down-arrow { image: none; }
QPushButton[role="tab"]:focus, QPushButton[role="buildChoice"]:focus,
QComboBox[role="buildChoice"]:focus, QComboBox[role="draftRoleIcon"]:focus {
    border: 2px solid #e3d0ff;
}
QPushButton[role="primary"]:focus { border: 2px solid #36234d; }
QFrame[role="homePanel"] QPushButton:focus, QFrame[role="homePanel"] QLineEdit:focus,
QFrame[role="homeSearch"] QLineEdit:focus, QFrame[role="homeSearch"] QComboBox:focus {
    border: 2px solid #c6afea;
}
QFrame[role="homePanel"] QCheckBox:focus::indicator { border-color: #e1cdfb; }
QComboBox QAbstractItemView, QLineEdit QAbstractItemView {
    background: #211d2e; border: 1px solid #4d4166; color: #f2eef8;
    selection-background-color: #514069;
}
QCheckBox { color: #c9bfd7; spacing: 7px; }
QCheckBox::indicator {
    width: 14px; height: 14px; background: #15131d;
    border: 1px solid #65557d; border-radius: 4px;
}
QCheckBox::indicator:checked { background: #a78bd9; border: 1px solid #ddc5fa; }
QFrame[role="overlay"] { background: #171321; border: 1px solid #625182; border-radius: 12px; }
QWidget#overlayRows { background: #171321; }
QLabel[role="overlayRune"] {
    background: #252032; border: 1px solid #4c3e63; border-radius: 8px;
    color: #ded0ef; font-size: 8px; font-weight: 600;
}
"""
