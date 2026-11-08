"""Прозрачные Qt-окна без фокуса, с отдельной интерактивной кнопкой закрепления."""
import time
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget,QPushButton,QApplication
import render
from app_config import C,WIDGETS,IS_WIN
from .widgets import pixmap
from . import native

class Overlay(QWidget):
    CAPS={k:v for k,v in WIDGETS.items()}
    def __init__(self,app,key,xy):
        super().__init__(None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.app,self.key=app,key;self.unlocked=False;self._drag=None;self._rgba=None;self._pixmap=None;self._card_signature=None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground);self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.pin=QPushButton('◇');self.pin.setWindowFlags(Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.pin.setFixedSize(22,22);self.pin.setToolTip('Закрепить / открепить виджет');self.pin.clicked.connect(self.toggle_pin)
        self.pin.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(250,65);self.move_physical(*app.layout().get(key,xy));self.unlock(False)
        self.winId();self.windowHandle().screenChanged.connect(lambda screen:self.refresh_screen())
    def card(self,accent=None,width=None,title=False):
        return render.Card(C,'Forum',self.app.s['scale']/100,plate=self.app.s['widget_bg']!='none',accent=accent,width=width,title=self.CAPS.get(self.key) if title else None)
    def put(self,card):
        sig=card.signature()
        if sig==self._card_signature:return
        self._card_signature=sig;self.put_image(card.render())
    def put_image(self,image):
        self._rgba=image;self._pixmap=pixmap(image);self.refresh_screen();self.setWindowOpacity(self.app.s['alpha']/100);self.update();self.sync_pin()
    def paintEvent(self,event):
        if self._pixmap:
            p=QPainter(self);p.drawPixmap(0,0,self._pixmap)
    def toggle_pin(self):
        pins=self.app.s['widget_pins'];pins[self.key]=not pins.get(self.key,False);self.app.s.save();self.unlock(self.unlocked)
    def unlock(self,on):
        self.unlocked=bool(on);through=self.key=='tab' or not on or self.app.s['widget_pins'].get(self.key,False)
        # Native HWND style changes avoid Qt hiding/recreating the overlay at each Alt press.
        if IS_WIN:native.styles(self,through);native.styles(self.pin,False)
        else:self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,through)
        self.sync_pin()
    def sync_pin(self):
        if not hasattr(self,'pin'):return
        x,y,w,h=native.geometry(self);native.move(self.pin,x+w-round(22*self.devicePixelRatioF()),y);self.pin.setText('◆' if self.app.s['widget_pins'].get(self.key) else '◇')
        self.pin.setVisible(self.isVisible() and self.unlocked and self.key!='tab')
    def deiconify(self):QWidget.show(self);self.sync_pin()
    def withdraw(self):self.hide();self.pin.hide()
    def lift(self):self.raise_();self.sync_pin()
    def winfo_viewable(self):return self.isVisible()
    def mousePressEvent(self,e):
        if self.unlocked and not self.app.s['widget_pins'].get(self.key):self._drag=native.cursor()-QPoint(*native.geometry(self)[:2])
    def mouseMoveEvent(self,e):
        if self._drag is not None:point=native.cursor()-self._drag;self.move_physical(point.x(),point.y());self.sync_pin()
    def mouseReleaseEvent(self,e):
        if self._drag is not None:self._drag=None;self.app.layout()[self.key]=list(native.geometry(self)[:2]);self.app.s.save()
    def closeEvent(self,event):self.pin.close();self.pin.deleteLater();super().closeEvent(event);self.deleteLater()
    def demo(self):self.put(self.card().row(('text',WIDGETS.get(self.key,self.key),'fg',12,True)).row(('text','Пример для расстановки','mute',10,False)))

    def move_physical(self,x,y):native.move(self,x,y)
    def refresh_screen(self):
        if self._rgba is None:return
        self._pixmap.setDevicePixelRatio(self.devicePixelRatioF())
        x,y,_,_=native.geometry(self);native.move(self,x,y,self._rgba.width,self._rgba.height);self.update()
