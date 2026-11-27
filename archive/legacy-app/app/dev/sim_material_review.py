"""Capture the actual desktop UI on the host OS, not a generated concept image."""
from pathlib import Path
import json
import os
import sys
import time
from PIL import ImageGrab
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
# Reuse the isolated home fixture: no polling, network, export or real settings.
fixture=Path(__file__).with_name('sim_home.py')
context={'__file__':str(fixture)}
exec(compile(fixture.read_text(encoding='utf-8').split('\ndef capture(')[0],str(fixture),'exec'),context)
app=context['app'];errors=context['errors']
app.root.overrideredirect(True);app.root.maxsize(3840,2160);app.root.geometry('1536x864+0+0')
app.status.configure(text='Демонстрационные данные · настоящий интерфейс')
output=Path(os.environ['SIM_OUT']);output.mkdir(parents=True,exist_ok=True)
pages=iter(enumerate(('home','history','champion','hints','widgets','appearance','sound','keys','timers','updates','pool')))
checks=[]
def advance():
    case=next(pages,None)
    if case is None:
        app.nb.select(0);app.root.after(200,finish);return
    index,name=case;app.nb.select(index)
    app.root.after(200,lambda:capture(name))
def capture(name):
    app.root.update_idletasks()
    x,y=app.root.winfo_rootx(),app.root.winfo_rooty();w,h=app.root.winfo_width(),app.root.winfo_height()
    ImageGrab.grab(bbox=(x,y,x+w,y+h)).save(output/(name+'.png'))
    checks.append({'page':name,'size':[w,h],'images':len(app.root.tk.call('image','names'))})
    app.root.after(50,advance)
def finish():
    app.root.update_idletasks()
    try:
        assert app.home_view.winfo_ismapped()
        assert any(getattr(child,'photo',None) for frame in app.home_view.metrics.winfo_children() for child in frame.winfo_children()),'metric images did not return after a tab round trip'
        assert not errors,errors
    except Exception as error:errors.append(repr(error))
    finally:
        (output/'checks.json').write_text(json.dumps({'errors':errors,'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
        app.root.destroy()
app.root.after(700,advance);app.run()
assert not errors,errors
assert len(checks)==11,checks
print(output)
