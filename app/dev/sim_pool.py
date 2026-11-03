"""Offline screenshots and interaction checks for the real Tk champion-pool screen."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lcu
import lolhelper
import ui

OUT=Path(os.environ.get('SIM_OUT','/tmp/pool-preview'));OUT.mkdir(parents=True,exist_ok=True)
settings=tempfile.TemporaryDirectory(prefix='lol-pool-preview-')
ui.app_home=lambda:settings.name
Path(settings.name,'settings.json').write_text(json.dumps({'design3':True,'theme':os.environ.get('SIM_THEME','lol'),'scale':int(os.environ.get('SIM_SCALE',100)),'sound':'off'}))
for method in ('poll','load_lanes','load_changelog','hist_refresh','check_updates'):setattr(ui.App,method,lambda *a,**k:None)
lcu.live_data=lambda:None
lcu.LCU.image=lambda *a:None
lcu.LCU.me=lambda *a:None
app=ui.App(lolhelper.load_data(),'Демо')
errors=[];app.root.report_callback_exception=lambda et,ev,tb:errors.append(str(ev))
if app.dash:app.dash.withdraw()
assets=Path(os.environ['SIM_ASSETS_JSON'])
app.icons.a=json.loads(assets.read_text())
portrait_dir=Path(os.environ['SIM_POOL_PORTRAITS']) if os.environ.get('SIM_POOL_PORTRAITS') else None
for file in portrait_dir.glob('*.png') if portrait_dir else []:app.icons.a.setdefault('champ',{})[file.stem]=base64.b64encode(file.read_bytes()).decode()
app.icons.cache.clear();app.icons.raw.clear()
app.pool_view.destroy()
from pool_ui import PoolScreen
app.pool_view=PoolScreen(app.tab_pool,app)
app.root.title('LoL Helper · Мой пул · предпросмотр')
app.root.geometry(os.environ.get('SIM_GEOMETRY','1366x900+0+0'))
app.nb.select(10)
view=app.pool_view;view.role='MIDDLE';view.sort.set('Сначала выбранные');view.refresh()
checks=[]

def capture(name):
    app.root.update_idletasks()
    width,height=app.root.winfo_width(),app.root.winfo_height()
    assert view.winfo_width()>0
    assert view.cv.winfo_height()>100,('viewport too short',view.cv.winfo_height())
    assert view.footer.winfo_y()+view.footer.winfo_height()<=view.winfo_height(), 'footer clipped'
    if view.cards:assert next(iter(view.cards.values())).winfo_width()>=app.fs(115)
    for champion,card in view.cards.items():
        assert card.winfo_width()>50
        assert card.winfo_x()+card.winfo_width()<=view.grid_box.winfo_width()+2
    subprocess.run(['import','-window',str(app.root.winfo_id()),str(OUT/name)],check=True)
    checks.append({'stage':name,'window':[width,height],'columns':view.columns,'found':len(view.visible),'card_size':[next(iter(view.cards.values())).winfo_width(),next(iter(view.cards.values())).winfo_height()] if view.cards else []})

def go():
    try:
        initial=app.current_pool();had='Ahri' in initial['MIDDLE']
        view.cards['Ahri'].event_generate('<Button-1>');app.root.update_idletasks()
        assert ('Ahri' in app.current_pool()['MIDDLE']) != had
        assert ui.Settings(settings.name)['champion_pools'][app.who]['MIDDLE']==app.current_pool()['MIDDLE']
        view.cards['Ahri'].event_generate('<Button-1>');assert app.current_pool()==initial
        view.choose_role('TOP');assert app.current_pool()==initial
        view.choose_role('MIDDLE');app.root.update_idletasks()
        # Add demo selections through the real interaction; settings are temporary.
        for champion in ('Ahri','Orianna','Syndra'):
            if champion not in app.current_pool()['MIDDLE']:
                view.cards[champion].event_generate('<Button-1>');app.root.update_idletasks()
            assert champion in app.current_pool()['MIDDLE'],champion
        capture('pool-main.png')
        view.toggle_advanced();app.root.update_idletasks();capture('pool-filters.png')
        view.filters['gender'].set('Женский');view.filters['regions'].set('Иония');view.refresh()
        assert all(r['gender']=='FEMALE' and 'Ionia' in r['regions'] for r in view.visible)
        capture('pool-filtered.png')
        view.query.set('нет такого чемпиона');view.search_now();assert not view.visible
        capture('pool-empty.png')
        view.reset();view.choose_mode('pool')
        assert {r['id'] for r in view.visible}==set(app.current_pool()['MIDDLE'])
        capture('pool-selected.png')
        view.choose_mode('all');view.toggle_advanced();app.root.geometry('1060x740+0+0');app.root.update();capture('pool-compact.png')
        assert not errors,errors
    except Exception as error:
        errors.append(repr(error));raise
    finally:
        (OUT/'native-checks.json').write_text(json.dumps({'errors':errors,'checks':checks},ensure_ascii=False))
        app.root.destroy()
app.root.after(600,go)
app.run()
assert not errors,errors
print(OUT)
