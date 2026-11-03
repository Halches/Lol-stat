"""Real home screen, offline assets and isolated demonstration settings."""
import base64
import copy
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
import profile_ranks

OUT=Path(os.environ.get('SIM_OUT','/tmp/home-preview'));OUT.mkdir(parents=True,exist_ok=True)
settings=tempfile.TemporaryDirectory(prefix='lol-home-preview-');ui.app_home=lambda:settings.name
Path(settings.name,'settings.json').write_text(json.dumps({'design3':True,'theme':os.environ.get('SIM_THEME','lol'),'scale':int(os.environ.get('SIM_SCALE',100)),'home_period':'season'}))
for method in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon'):setattr(ui.App,method,lambda *a,**k:None)
lcu.live_data=lambda:None;lcu.LCU.image=lambda *a:None;lcu.LCU.me=lambda *a:None
app=ui.App(lolhelper.load_data(),'Демо');errors=[];checks=[]
app.root.report_callback_exception=lambda et,ev,tb:errors.append(str(ev))
if app.dash:app.dash.withdraw()
app.icons.a=json.loads(Path(os.environ['SIM_ASSETS_JSON']).read_text())
for group,var in [('champ','SIM_POOL_PORTRAITS'),('item','SIM_HOME_ITEMS')]:
    folder=Path(os.environ[var]) if os.environ.get(var) else None
    for p in folder.glob('*.png') if folder else []:app.icons.a.setdefault(group,{})[p.stem]=base64.b64encode(p.read_bytes()).decode()
if os.environ.get('SIM_PROFILE_ICON'):
    app.icons.a.setdefault('profile',{})['29']=base64.b64encode(Path(os.environ['SIM_PROFILE_ICON']).read_bytes()).decode()
app.icons.cache.clear();app.icons.raw.clear()
app.account={'riot':'Halch#9200','icon':29,'level':278,'puuid':'demo'}
app.my_rank={'tier':'EMERALD','div':'IV','lp':17,'w':221,'l':211}
app.account['ranks']=profile_ranks.parse({'queueMap':{
    'RANKED_SOLO_5x5':{'tier':'EMERALD','division':'IV','leaguePoints':17,'wins':221,'losses':211},
    'RANKED_FLEX_SR':{'tier':'PLATINUM','division':'I','leaguePoints':48,'wins':13,'losses':9},
    'RANKED_TFT':{'tier':'DIAMOND','division':'III','leaguePoints':63,'wins':4,'losses':20}}})
app.status.configure(text='Демонстрация · клиент не опрашивается')
app.root.title('LoL Helper · Главная · демонстрация');app.root.geometry(os.environ.get('SIM_GEOMETRY','1440x1100+0+0'))
app.nb.select(0);app.panel_sync()

def capture(name):
    app.root.update_idletasks();view=app.home_view
    assert list(view.rank_cards)==(['solo','flex','arena','tft'] if view.layout[4] else ['solo','flex','arena'])
    for parent in (view.hero,view.metrics,*view.rank_cards.values(),*view.matches.winfo_children()):
        for child in parent.winfo_children():
            assert child.winfo_x()+child.winfo_width()<=parent.winfo_width()+2,(name,'clipped',child.winfo_class())
    subprocess.run(['import','-window',str(app.root.winfo_id()),str(OUT/name)],check=True)
    checks.append({'stage':name,'window':[app.root.winfo_width(),app.root.winfo_height()],
                   'layout':view.layout,'content_height':view.winfo_height(),'stats_n':view.data['stats']['n']})

def go():
    try:
        capture('home-main.png')
        def card_text(widget):
            return [str(widget.cget('text'))] if isinstance(widget,ui.tk.Label) else [text for child in widget.winfo_children() for text in card_text(child)]
        assert 'Платина I' in ' '.join(card_text(app.home_view.rank_cards['flex']))
        if 'tft' in app.home_view.rank_cards:assert 'Алмаз III' in ' '.join(card_text(app.home_view.rank_cards['tft']))
        app.home_view.period_pick('recent');assert ui.Settings(settings.name)['home_period']=='recent'
        assert app.home_view.data['stats']['n']==20
        capture('home-recent.png')
        app.set_who('drv');app.panel_sync()
        def labels(widget):
            return [str(widget.cget('text'))] if isinstance(widget,ui.tk.Label) else [text for child in widget.winfo_children() for text in labels(child)]
        hero_text=' '.join(labels(app.home_view.hero))
        assert 'Золото II' in hero_text and 'Изумруд IV' not in hero_text and 'Платина I' not in hero_text and 'Алмаз III' not in hero_text,hero_text
        assert app.home_view.data['stats']['n']==20
        capture('home-other-profile.png')
        app.set_who('halch');app.account=None;app.panel_sync();capture('home-offline.png')
        original=app.player.games;app.player.games=[];app.panel_sync()
        assert app.home_view.data['stats']['wr'] is None
        capture('home-empty.png');app.player.games=original
        app.account={'riot':'ОченьДлинноеИмяИгрока#LONGTAG','icon':29,'level':278,'puuid':'demo'}
        app.data.d['players']['halch']['riot']=app.account['riot'];app.panel_sync()
        app.root.geometry('1060x740+0+0');app.root.update();app.home_view.reflow();app.root.update_idletasks();capture('home-compact.png')
        assert not app.home_view.layout[0]
        assert not errors,errors
    except Exception as e:errors.append(repr(e));raise
    finally:
        (OUT/'native-checks.json').write_text(json.dumps({'errors':errors,'checks':checks},ensure_ascii=False))
        app.root.destroy()
app.root.after(600,go);app.run()
assert not errors,errors
print(OUT)
