"""Граница физических координат Win32 и логических координат Qt."""
import os
from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor
IS_WIN=os.name=='nt'
if IS_WIN:
    import ctypes
    from ctypes import wintypes
    user=ctypes.windll.user32
    user.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int];user.GetWindowLongW.restype=wintypes.LONG
    user.SetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.LONG];user.SetWindowLongW.restype=wintypes.LONG
    user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]

def styles(window,through):
    if not IS_WIN:return
    h=int(window.winId());style=user.GetWindowLongW(h,-20)|0x80000|0x80|0x08000000
    user.SetWindowLongW(h,-20,style|0x20 if through else style & ~0x20)

def geometry(window):
    if IS_WIN:
        rect=wintypes.RECT()
        if user.GetWindowRect(int(window.winId()),ctypes.byref(rect)):return rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top
    return window.x(),window.y(),window.width(),window.height()

def move(window,x,y,width=None,height=None):
    if IS_WIN:
        flags=0x10|0x4|(0x1 if width is None else 0)
        if not user.SetWindowPos(int(window.winId()),None,round(x),round(y),round(width or 0),round(height or 0),flags):raise ctypes.WinError()
    else:
        window.move(round(x),round(y))
        if width is not None:window.resize(round(width),round(height))

def cursor():
    if IS_WIN:
        point=wintypes.POINT();user.GetCursorPos(ctypes.byref(point));return QPoint(point.x,point.y)
    return QCursor.pos()
