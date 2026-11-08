"""Общие Qt-компоненты: нарисованные поверхности и живые элементы управления."""
from __future__ import annotations
import base64,io,json,os
from functools import lru_cache
from pathlib import Path
from PIL import Image,ImageOps
from PySide6.QtCore import Qt,QObject,Signal,Slot,QTimer,QRectF,QSize
from PySide6.QtGui import QColor,QFont,QImage,QPixmap,QPainter,QPen,QPainterPath,QIcon
from PySide6.QtWidgets import (QWidget,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,QScrollArea,
    QSizePolicy,QComboBox,QCheckBox,QLineEdit,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QLayout,QApplication)
from app_config import C,bundle_dir,log_error
import material_assets

HERE=Path(bundle_dir())/'qt_ui'
def pixmap(image):
    b=io.BytesIO();image.save(b,format='PNG');return QPixmap.fromImage(QImage.fromData(b.getvalue()))

@lru_cache(maxsize=128)
def surface(kind,w,h,theme):
    if kind=='shell':
        im=material_assets.shell(w,h)
        if im is not None and not C.get('dark',True):
            alpha=im.getchannel('A');im=ImageOps.colorize(ImageOps.grayscale(im),'#c5b3cd','#fff9ff').convert('RGBA');im.putalpha(alpha)
        return pixmap(im) if im else QPixmap()
    regions={'panel':((26,279,2148,448),44,20),'button':((100,226,1915,566),120,12),'selected':((92,202,2084,554),128,12)}
    rect,cut,border=regions[kind]
    with Image.open(HERE/'painted'/f'blossom-{kind}-v1.png') as im:
        im=material_assets.nine_slice(im.convert('RGBA').crop(rect),max(1,w),max(1,h),cut,min(border,max(1,min(w,h)//3)))
    if not C.get('dark',True):
        alpha=im.getchannel('A');im=ImageOps.colorize(ImageOps.grayscale(im),'#baa4c3','#fff9ff').convert('RGBA');im.putalpha(alpha)
    return pixmap(im)

class Label(QLabel):
    def __init__(self,text='',size=11,tone='fg',bold=False,serif=False,parent=None):
        super().__init__(str(text),parent);self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setFont(QFont('PT Serif' if serif else QApplication.font().family(),max(7,round(size*(QApplication.instance().property('uiScale') or 1))),QFont.Weight.Bold if bold else QFont.Weight.Normal))
        self.setStyleSheet('color:'+C.get(tone,tone)+';background:transparent;')
    def configure(self,**kw):
        if 'text' in kw:self.setText(str(kw['text']))
        if 'fg' in kw:self.setStyleSheet('color:'+kw['fg']+';background:transparent;')
    def cget(self,key):return self.text() if key=='text' else None
    def winfo_exists(self):return True

class Button(QPushButton):
    def __init__(self,text,action=None,active=False,parent=None):
        super().__init__(text,parent);self.active=active;self.text_color=None;self.setMinimumHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor);self.setFont(QFont(QApplication.font().family(),max(7,round(10*(QApplication.instance().property('uiScale') or 1)))))
        if action:self.clicked.connect(lambda checked=False:action())
    def sizeHint(self):return QSize(max(80,self.fontMetrics().horizontalAdvance(self.text())+30),36)
    def configure(self,**kw):
        if 'text' in kw:self.setText(kw['text'])
    def paintEvent(self,e):
        p=QPainter(self);p.drawPixmap(self.rect(),surface('selected' if self.active or self.isChecked() else 'button',self.width(),self.height(),C['bg']))
        if self.underMouse() or self.hasFocus():p.fillRect(self.rect().adjusted(4,4,-4,-4),QColor(230,170,246,24))
        if self.isDown():p.fillRect(self.rect(),QColor(0,0,0,45))
        p.setPen(QColor((self.text_color or C['fg']) if self.isEnabled() else C['mute']));p.setFont(self.font());p.drawText(self.rect().adjusted(10,3,-10,-3),Qt.AlignmentFlag.AlignCenter,self.text())

class Panel(QWidget):
    def __init__(self,parent=None,padding=14,kind='panel',horizontal=False):
        super().__init__(parent);self.kind=kind
        self.box=QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        self.box.setContentsMargins(padding,padding,padding,padding);self.box.setSpacing(8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
    def paintEvent(self,event):
        if not self.kind:return
        p=QPainter(self);p.drawPixmap(self.rect(),surface(self.kind,self.width(),self.height(),C['bg']))

class Shell(Panel):
    def __init__(self):
        super().__init__(padding=24,kind='shell',horizontal=True);self.box.setContentsMargins(24,22,24,32)

class Page(QWidget):
    def __init__(self,app):
        super().__init__();self.app=app;self.box=QVBoxLayout(self);self.box.setContentsMargins(8,6,18,14);self.box.setSpacing(12);self.box.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
    def clear(self):
        while self.box.count():
            item=self.box.takeAt(0)
            if item.widget():item.widget().deleteLater()
            elif item.layout():clear_layout(item.layout())
    def title(self,text):self.box.addWidget(Label(text,20,'gold',serif=True))
    def note(self,text):self.box.addWidget(Label(text,10,'mute'))
    def winfo_exists(self):return True

def clear_layout(layout):
    while layout.count():
        item=layout.takeAt(0)
        if item.widget():item.widget().deleteLater()
        elif item.layout():clear_layout(item.layout())

def row(*widgets):
    w=QWidget();b=QHBoxLayout(w);b.setContentsMargins(0,0,0,0);b.setSpacing(8)
    for child in widgets:b.addWidget(child)
    return w

def combo(options,value=None,changed=None):
    c=QComboBox();c.setMinimumHeight(34)
    pairs=list(options.items()) if isinstance(options,dict) else [(x,x) for x in options]
    for key,label in pairs:c.addItem(str(label),key)
    if value is not None:
        idx=c.findData(value)
        if idx>=0:c.setCurrentIndex(idx)
    if changed:c.currentIndexChanged.connect(lambda index:changed(c.itemData(index)))
    return c

def check(text,checked,changed):
    w=QCheckBox(text);w.setChecked(bool(checked));w.toggled.connect(changed);return w

def table(headers,rows):
    t=QTableWidget(len(rows),len(headers));t.setHorizontalHeaderLabels(headers);t.verticalHeader().hide()
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True);t.setWordWrap(False)
    for i,r in enumerate(rows):
        for j,value in enumerate(r):t.setItem(i,j,QTableWidgetItem(str(value) if value is not None else '—'))
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    t.horizontalHeader().setStretchLastSection(True)
    t.setMinimumHeight(min(520,70+len(rows)*34));return t

class Icons:
    def __init__(self,path=None):
        p=Path(path or Path(bundle_dir())/'assets.json')
        if not p.exists():p=Path(bundle_dir())/'dev/qt_history/icons.json'
        self.a=json.loads(p.read_text()) if p.exists() else {}
    @lru_cache(maxsize=512)
    def pil(self,group,key,size=36,gray=False):
        data=self.a.get(group,{}).get(str(key))
        if not data:return None
        im=Image.open(io.BytesIO(base64.b64decode(data))).convert('RGBA').resize((size,size),Image.Resampling.LANCZOS)
        if gray:
            alpha=im.getchannel('A');im=ImageOps.grayscale(im).convert('RGBA');im.putalpha(alpha)
        return im
    def label(self,group,key,size=36):
        l=QLabel();l.setFixedSize(size,size)
        shown=getattr(self,'settings',{}).get('show',{})
        flag={'champ':'portraits','item':'items','spell':'spells','rune':'runes','emb':'ranks','tft_emb':'ranks'}.get(group)
        if flag and not shown.get(flag,True):
            l.setText(str(key) if group=='item' else '');l.setToolTip(str(key));return l
        im=self.pil(group,key,size)
        if im:l.setPixmap(pixmap(im))
        l.setToolTip(str(key));return l
    def icon(self,group,key,size=36):
        im=self.pil(group,key,size);return QIcon(pixmap(im)) if im else QIcon()

class Scheduler(QObject):
    requested=Signal(int,object,object)
    failed=Signal(object)
    def __init__(self):
        super().__init__();self.active=True;self.timers={};self.serial=0
        self.requested.connect(self.schedule,Qt.ConnectionType.QueuedConnection)
    def after(self,ms,fn,*args):
        self.serial+=1;key=self.serial
        if self.active:self.requested.emit(int(ms),key,lambda:fn(*args))
        return key
    @Slot(int,object,object)
    def schedule(self,ms,key,fn):
        if not self.active:return
        timer=QTimer(self);timer.setSingleShot(True);self.timers[key]=timer
        def run():
            self.timers.pop(key,None);timer.deleteLater()
            if self.active:
                try:fn()
                except Exception as error:log_error('Qt callback',error);self.failed.emit(error)
        timer.timeout.connect(run);timer.start(ms)
    def after_cancel(self,key):
        t=self.timers.pop(key,None)
        if t:t.stop();t.deleteLater()
    def stop(self):
        self.active=False
        for key in list(self.timers):self.after_cancel(key)

class Chart(QWidget):
    def __init__(self,values,color='good',height=72):
        super().__init__();self.values=values;self.color=color;self.setMinimumHeight(height)
    def paintEvent(self,e):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        values=[x for x in self.values if isinstance(x,(float,int))]
        if not values:p.setPen(QColor(C['mute']));p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'Нет данных');return
        lo,hi=min(values),max(values);span=max(1,hi-lo)
        rect=self.rect().adjusted(8,8,-8,-16);n=max(1,len(self.values)-1);path=QPainterPath();started=False
        for i,value in enumerate(self.values):
            if not isinstance(value,(float,int)):started=False;continue
            x,y=rect.left()+rect.width()*i/n,rect.bottom()-rect.height()*(value-lo)/span
            if not started:path.moveTo(x,y);started=True
            else:path.lineTo(x,y)
        p.setPen(QPen(QColor(C.get(self.color,self.color)),2));p.drawPath(path)
        p.setFont(QFont('Golos Text',8));p.setPen(QColor(C['mute']));p.drawText(8,self.height()-1,f'{lo:.1f} — {hi:.1f}')

class NavButton(Button):
    def __init__(self,text,icon,action):
        super().__init__(text,action);self.nav_icon=icon;self.setMinimumHeight(30);self.setMaximumHeight(36)
    def paintEvent(self,e):
        import render
        p=QPainter(self)
        if self.active:p.drawPixmap(self.rect(),surface('selected',self.width(),self.height(),C['bg']))
        elif self.underMouse():p.fillRect(self.rect().adjusted(3,3,-3,-3),QColor(220,170,235,20))
        icon=pixmap(render.nav_icon(self.nav_icon,C['fg'] if self.active else C['mute'],19))
        p.drawPixmap(11,(self.height()-19)//2,icon);p.setPen(QColor(C['fg']));p.setFont(self.font())
        p.drawText(self.rect().adjusted(39,0,-5,0),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,self.text())

class AdaptiveGrid(QWidget):
    def __init__(self,widgets,breakpoint=850):
        super().__init__();self.widgets=widgets;self.breakpoint=breakpoint;self.columns=0;self.grid=QGridLayout(self);self.grid.setContentsMargins(0,0,0,0);self.arrange(4)
    def arrange(self,columns):
        if columns==self.columns:return
        self.columns=columns
        for i,w in enumerate(self.widgets):self.grid.addWidget(w,i//columns,i%columns)
        for i in range(4):self.grid.setColumnStretch(i,1 if i<columns else 0)
    def resizeEvent(self,e):super().resizeEvent(e);self.arrange(4 if self.width()>=self.breakpoint else 2)
    def minimumSizeHint(self):return QSize(380,self.grid.minimumSize().height())
