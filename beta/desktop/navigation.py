"""Small native line icons for navigation, readable in the compact rail."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def navigation_icon(page):
    image = QPixmap(24, 24)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#c5b6db"), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                        Qt.PenJoinStyle.RoundJoin))
    lines = {
        "overview": [(3, 11), (12, 3), (21, 11), (19, 11), (19, 21), (14, 21), (14, 14), (10, 14), (10, 21), (5, 21), (5, 11)],
        "history": [(12, 7), (12, 12), (16, 14)],
        "builds": [(5, 5), (19, 5), (19, 20), (5, 20), (5, 5)],
        "updates": [(12, 3), (12, 15), (7, 10), (12, 15), (17, 10)],
        "toggle": [(14, 6), (8, 12), (14, 18)],
    }
    points = lines.get(page, [])
    if points:
        path = QPainterPath(QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(*point)
        painter.drawPath(path)
    if page == "history":
        painter.drawEllipse(3, 3, 18, 18)
    elif page == "builds":
        painter.drawLine(8, 10, 16, 10)
        painter.drawLine(8, 15, 14, 15)
    elif page == "assistant":
        for x, top in ((4, 10), (8, 6), (12, 3), (16, 6), (20, 10)):
            painter.drawLine(x, top, x, 24 - top)
    elif page == "settings":
        painter.drawEllipse(6, 6, 12, 12)
        painter.drawEllipse(10, 10, 4, 4)
        for a, b in (((12, 2), (12, 5)), ((12, 19), (12, 22)), ((2, 12), (5, 12)),
                     ((19, 12), (22, 12)), ((5, 5), (7, 7)), ((17, 17), (19, 19)),
                     ((5, 19), (7, 17)), ((17, 7), (19, 5))):
            painter.drawLine(*a, *b)
    elif page == "updates":
        painter.drawLine(4, 18, 4, 21)
        painter.drawLine(4, 21, 20, 21)
        painter.drawLine(20, 21, 20, 18)
    painter.end()
    return QIcon(image)
