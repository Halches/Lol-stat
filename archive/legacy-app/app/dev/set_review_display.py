"""Set only the disposable Windows review desktop to 1920x1080."""
import ctypes
from ctypes import wintypes as w

# https://learn.microsoft.com/windows/win32/api/wingdi/ns-wingdi-devmodew
class Mode(ctypes.Structure):
    _fields_=[('device',w.WCHAR*32),('spec',w.WORD),('driver',w.WORD),
              ('size',w.WORD),('extra',w.WORD),('fields',w.DWORD),
              ('position_and_orientation',ctypes.c_byte*16),
              ('color',ctypes.c_short),('duplex',ctypes.c_short),('yres',ctypes.c_short),
              ('tt',ctypes.c_short),('collate',ctypes.c_short),('form',w.WCHAR*32),
              ('log_pixels',w.WORD),('bits',w.DWORD),('width',w.DWORD),('height',w.DWORD),
              ('flags',w.DWORD),('frequency',w.DWORD),('icm_method',w.DWORD),
              ('icm_intent',w.DWORD),('media',w.DWORD),('dither',w.DWORD),
              ('reserved1',w.DWORD),('reserved2',w.DWORD),('pan_width',w.DWORD),('pan_height',w.DWORD)]


def main():
    mode=Mode();mode.size=ctypes.sizeof(mode)
    user=ctypes.windll.user32
    if not user.EnumDisplaySettingsW(None,-1,ctypes.byref(mode)):raise RuntimeError('Cannot read review display mode')
    mode.width,mode.height=1920,1080;mode.fields|=0x80000|0x100000
    result=user.ChangeDisplaySettingsW(ctypes.byref(mode),0)
    if result!=0:raise RuntimeError('Review display rejected 1920x1080: '+str(result))
    print('Review display:',user.GetSystemMetrics(0),user.GetSystemMetrics(1))
    if (user.GetSystemMetrics(0),user.GetSystemMetrics(1))!=(1920,1080):raise RuntimeError('Unexpected review display dimensions')


if __name__=='__main__':main()
