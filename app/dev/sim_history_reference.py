"""Actual history at reference size and windowed sizes, using isolated settings."""
from pathlib import Path
import json
import os
from PIL import ImageGrab
fixture=Path(__file__).with_name('sim_home.py')
context={'__file__':str(fixture)}
exec(compile(fixture.read_text(encoding='utf-8').split('\ndef capture(')[0],str(fixture),'exec'),context)
app=context['app'];errors=context['errors'];checks=[]
# Capture client area: Windows window-manager chrome requires a Windows check.
app.root.overrideredirect(True);app.root.maxsize(3840,2160)
app.status.configure(text='Демонстрация · настоящий интерфейс')
output=Path(os.environ['SIM_OUT']);output.mkdir(parents=True,exist_ok=True)
app.nb.select(1)
cases=iter([('history-reference',1536,864),('history-1366',1366,768),
            ('history-windowed',1060,740),('history-1920',1920,1080)])
def advance():
    case=next(cases,None)
    if case is None:
        canvas=app.canvases[str(app.tab_hist.outer)]
        canvas.yview_moveto(.5)
        app.root.after(200,capture_scroll);return
    name,w,h=case
    app.root.geometry(f'{w}x{h}+0+0')
    app.root.after(450,lambda:capture(name))
def capture(name,attempt=0):
    app.root.update_idletasks();view=app.history_view
    if view.last_width!=view.winfo_width() or view.job is not None or app.root._material.resize_job is not None:
        if attempt>=20:raise AssertionError('layout did not settle')
        app.root.after(150,lambda:capture(name,attempt+1));return
    x,y=app.root.winfo_rootx(),app.root.winfo_rooty();w,h=app.root.winfo_width(),app.root.winfo_height()
    ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(output/(name+'.png'))
    clipped=[]
    for row in view.row_widgets:
        for child in row.winfo_children():
            if child.winfo_x()+child.winfo_width()>row.winfo_width()+2:clipped.append(str(child))
    if clipped:errors.append({'case':name,'clipped':clipped})
    visible=sum(row.winfo_rooty()+row.winfo_height()<=y+h-28 for row in view.row_widgets)
    checks.append({'case':name,'size':[w,h],'visible_rows':visible,'wide':view.layout})
    app.root.after(20,advance)
def capture_scroll():
    app.root.update_idletasks()
    x,y=app.root.winfo_rootx(),app.root.winfo_rooty();w,h=app.root.winfo_width(),app.root.winfo_height()
    ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(output/'history-scrolled.png')
    assert app.canvases[str(app.tab_hist.outer)].yview()[0]>0,'history did not scroll'
    app.nb.select(0);app.root.after(400,finish)
def finish():
    try:
        app.root.update_idletasks()
        assert any(getattr(child,'photo',None) for frame in app.home_view.metrics.winfo_children() for child in frame.winfo_children()),'home charts did not return'
        assert not errors,errors
    except Exception as error:errors.append(repr(error))
    finally:
        (output/'checks.json').write_text(json.dumps({'errors':errors,'checks':checks},ensure_ascii=False,indent=2))
        app.root.destroy()
app.root.after(500,advance);app.run()
assert not errors,errors
print(output)
