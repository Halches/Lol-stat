"""Present RGBA overlay pixels without fading their opaque text on Windows."""
import os
import ctypes
from ctypes import wintypes
from PIL import ImageChops


def present(window, image, opacity=100):
    if os.name != 'nt':
        return
    user = ctypes.windll.user32
    gdi = ctypes.windll.gdi32
    user.GetDC.restype = wintypes.HDC
    user.GetParent.argtypes = [wintypes.HWND]
    user.GetParent.restype = wintypes.HWND
    user.GetWindowLongW.argtypes = [wintypes.HWND,ctypes.c_int]
    user.GetWindowLongW.restype = wintypes.LONG
    user.SetWindowLongW.argtypes = [wintypes.HWND,ctypes.c_int,wintypes.LONG]
    user.SetWindowLongW.restype = wintypes.LONG
    gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateDIBSection.restype = wintypes.HBITMAP
    gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi.SelectObject.restype = wintypes.HGDIOBJ
    gdi.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]

    class Header(ctypes.Structure):
        _fields_ = [('size',wintypes.DWORD),('width',wintypes.LONG),
                    ('height',wintypes.LONG),('planes',wintypes.WORD),
                    ('bits',wintypes.WORD),('compression',wintypes.DWORD),
                    ('image_size',wintypes.DWORD),('xppm',wintypes.LONG),
                    ('yppm',wintypes.LONG),('used',wintypes.DWORD),
                    ('important',wintypes.DWORD)]

    class Blend(ctypes.Structure):
        _fields_ = [('operation',ctypes.c_ubyte),('flags',ctypes.c_ubyte),
                    ('opacity',ctypes.c_ubyte),('format',ctypes.c_ubyte)]

    window.update_idletasks()
    hwnd = user.GetParent(window.winfo_id())
    screen = user.GetDC(None)
    memory = gdi.CreateCompatibleDC(screen)
    bitmap = previous = None
    try:
        header = Header(ctypes.sizeof(Header),image.width,-image.height,1,32,0,0,0,0,0,0)
        pixels = ctypes.c_void_p()
        gdi.CreateDIBSection.argtypes = [wintypes.HDC,ctypes.c_void_p,wintypes.UINT,
                                        ctypes.POINTER(ctypes.c_void_p),wintypes.HANDLE,wintypes.DWORD]
        bitmap = gdi.CreateDIBSection(memory,ctypes.byref(header),0,ctypes.byref(pixels),None,0)
        if not bitmap or not pixels.value:
            raise OSError('Не удалось выделить RGBA-изображение оверлея')
        previous = gdi.SelectObject(memory,bitmap)
        r,g,b,a = image.convert('RGBA').split()
        # UpdateLayeredWindow expects premultiplied BGRA, including antialiased edges.
        from PIL import Image
        rgba = Image.merge('RGBA',tuple(ImageChops.multiply(c,a) for c in (r,g,b))+(a,))
        data = rgba.tobytes('raw','BGRA')
        ctypes.memmove(pixels,data,len(data))
        position = wintypes.POINT(window.winfo_x(),window.winfo_y())
        origin = wintypes.POINT(0,0)
        size = wintypes.SIZE(image.width,image.height)
        blend = Blend(0,0,round(max(0,min(100,opacity))*2.55),1)
        # Tk's global-alpha/colour-key attributes otherwise prevent per-pixel alpha.
        style = user.GetWindowLongW(hwnd,-20)
        user.SetWindowLongW(hwnd,-20,style & ~0x80000)
        user.SetWindowLongW(hwnd,-20,style | 0x80000)
        user.UpdateLayeredWindow.argtypes = [wintypes.HWND,wintypes.HDC,
            ctypes.POINTER(wintypes.POINT),ctypes.POINTER(wintypes.SIZE),wintypes.HDC,
            ctypes.POINTER(wintypes.POINT),wintypes.COLORREF,ctypes.POINTER(Blend),wintypes.DWORD]
        if not user.UpdateLayeredWindow(hwnd,screen,ctypes.byref(position),ctypes.byref(size),
                                        memory,ctypes.byref(origin),0,ctypes.byref(blend),2):
            raise ctypes.WinError()
    finally:
        if previous:
            gdi.SelectObject(memory,previous)
        if bitmap:
            gdi.DeleteObject(bitmap)
        if memory:
            gdi.DeleteDC(memory)
        user.ReleaseDC(None,screen)
