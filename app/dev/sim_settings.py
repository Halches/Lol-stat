"""Настоящие настройки в изолированном профиле, без клиента, сети и звука."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lcu,lolhelper,ui

OUT=Path(os.environ['SIM_OUT']);OUT.mkdir(parents=True,exist_ok=True)
tmp=tempfile.TemporaryDirectory(prefix='lol-settings-');ui.app_home=lambda:tmp.name
Path(tmp.name,'settings.json').write_text(json.dumps({'design3':True,'theme':os.environ.get('SIM_THEME','lol'),'scale':int(os.environ.get('SIM_SCALE',100))}))
for method in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon'):setattr(ui.App,method,lambda *a,**k:None)
lcu.live_data=lambda:None;lcu.LCU.image=lambda *a:None;lcu.LCU.me=lambda *a:None
ui.Voice.warm=lambda *a:None;ui.Voice.say=lambda *a,**k:None;ui.Voice.beep=lambda *a,**k:None
app=ui.App(lolhelper.load_data(),'Разработка');errors=[];checks=[]
app.root.report_callback_exception=lambda et,ev,tb:errors.append(str(ev))
if app.dash:app.dash.withdraw()
app.status.configure(text='Предпросмотр настроек · без игры и озвучки')
app.root.geometry(os.environ.get('SIM_GEOMETRY','1500x1300+0+0'))


def capture(name):
    app.root.update();app.root.update_idletasks()
    subprocess.run(['import','-window',str(app.root.winfo_id()),str(OUT/name)],check=True)
    checks.append({'stage':name,'size':[app.root.winfo_width(),app.root.winfo_height()]})


def go():
    try:
        for index,name in ((5,'look'),(6,'voice'),(7,'keys'),(8,'timers')):
            app.nb.select(index);capture('settings-'+name+'.png')
        original=app.s['obj']['dragon_first'];var=ui.tk.StringVar(value='-1:00');app.set_obj('dragon_first',var)
        assert app.s['obj']['dragon_first']==original
        var.set('2:99');app.set_obj('dragon_first',var);assert app.s['obj']['dragon_first']==original
        var.set('5:45');app.set_obj('dragon_first',var);assert ui.Settings(tmp.name)['obj']['dragon_first']==345
        app.set_voice_param('master',66);assert ui.Settings(tmp.name)['master']==66
        app.root.geometry('1060x820+0+0');app.root.update()
        for index,name in ((5,'look'),(6,'voice'),(7,'keys'),(8,'timers')):
            app.nb.select(index);capture('settings-'+name+'-compact.png')
        assert not errors,errors
    except Exception as error:errors.append(repr(error));raise
    finally:
        (OUT/'native-checks.json').write_text(json.dumps({'errors':errors,'checks':checks},ensure_ascii=False));app.root.destroy()


app.root.after(700,go);app.run();assert not errors,errors
