"""Actual settings gallery and renderer previews; isolated settings, no client/network."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lcu
import lolhelper
import ui
OUT=Path(os.environ.get('SIM_OUT','/tmp/windows-preview'));OUT.mkdir(parents=True,exist_ok=True)
tmp=tempfile.TemporaryDirectory(prefix='lol-windows-preview-');ui.app_home=lambda:tmp.name
Path(tmp.name,'settings.json').write_text(json.dumps({'design3':True,'theme':os.environ.get('SIM_THEME','lol'),'scale':int(os.environ.get('SIM_SCALE',100)),'sound':'off'}))
for method in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon'):setattr(ui.App,method,lambda *a,**kw:None)
lcu.live_data=lambda:None;lcu.LCU.image=lambda *a:None;lcu.LCU.me=lambda *a:None
app=ui.App(lolhelper.load_data(),'Предпросмотр');errors=[];checks=[]
app.root.report_callback_exception=lambda et,ev,tb:(errors.append(str(ev)),traceback.print_exception(et,ev,tb))
if app.dash:app.dash.withdraw()
app.icons.a=json.loads(Path(os.environ['SIM_ASSETS_JSON']).read_text())
for group,var in [('champ','SIM_POOL_PORTRAITS'),('item','SIM_HOME_ITEMS')]:
    folder=Path(os.environ[var]) if os.environ.get(var) else None
    for path in folder.glob('*.png') if folder else []:app.icons.a.setdefault(group,{})[path.stem]=base64.b64encode(path.read_bytes()).decode()
app.icons.cache.clear();app.icons.raw.clear();view=app.windows_view;view.previews.clear();view.photos.clear()
app.root.title('LoL Helper · Виджеты и окна · предпросмотр');app.status.configure(text='Предпросмотр виджетов · демонстрационные данные')
app.root.geometry(os.environ.get('SIM_GEOMETRY','1500x1700+0+0'));app.nb.select(4)
def settle():app.root.update();app.root.update_idletasks()
def capture(name,window=None):
    settle();win=window or app.root
    if not window:
        for card in view.cards.values():assert card.winfo_x()+card.winfo_width()<=view.grid_box.winfo_width()+2
    subprocess.run(['import','-window',str(win.winfo_id()),str(OUT/name)],check=True)
    checks.append({'stage':name,'size':[win.winfo_width(),win.winfo_height()],'columns':view.columns})
def go():
    try:
        settle();view.refresh();settle()
        assert not any(app.s['widgets'].values()) and app.s['scoreboard']
        assert len(view.cards)==8 and all(im is not None for im in view.previews.values())
        capture('windows-gallery.png')
        view.toggles['timers'].invoke();assert app.s['widgets']['timers'];assert ui.Settings(tmp.name)['widgets']['timers']
        view.pin('timers');assert app.ov['timers'].pinned and ui.Settings(tmp.name)['widget_pins']['timers']
        assert not app.tab['tab'].pin_window
        capture('windows-enabled.png')
        view.enlarge('timers');capture('windows-preview.png',view.preview_window);view.preview_window.destroy()
        view.only_tab();assert not any(app.s['widgets'].values()) and app.s['scoreboard'];assert app.s['widget_pins']['timers']
        view.toggle_advanced();settle();assert view.advanced.winfo_ismapped()
        canvas=app.canvases[str(app.tab_win.outer)];canvas.yview_moveto(1);settle();capture('windows-options.png');canvas.yview_moveto(0)
        view.toggle_advanced();app.root.geometry('1060x840+0+0');settle();view.refresh();capture('windows-compact.png');assert view.columns==1
        # Explicit saved choices survive loading after the changed new-install defaults.
        app.s['widgets']['lane']=True;app.s.save();assert ui.Settings(tmp.name)['widgets']['lane']
        app.s['widgets']['lane']=False;app.s.save()
        app.demo_on=True
        view.toggles['timers'].invoke();settle();assert app.ov['timers'].winfo_viewable()
        view.toggles['timers'].invoke();settle();assert not app.ov['timers'].winfo_viewable()
        app.demo_on=False;app.set_unlocked(False)
        assert not errors,errors
    except Exception as error:errors.append(repr(error));raise
    finally:
        (OUT/'native-checks.json').write_text(json.dumps({'errors':errors,'checks':checks},ensure_ascii=False));app.root.destroy()
app.root.after(600,go);app.run();assert not errors,errors
print(OUT)
