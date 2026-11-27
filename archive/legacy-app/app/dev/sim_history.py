"""Offline history and actual Tk match window, including async errors and stale callbacks."""
import base64
import copy
import json
import os
from pathlib import Path
from PIL import Image, ImageGrab
import sys
import tempfile
import threading
import traceback
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core
import lcu
import lolhelper
import ui
from test_draft_history import game_fixture

OUT=Path(os.environ.get('SIM_OUT','/tmp/history-preview'));OUT.mkdir(parents=True,exist_ok=True)
settings=tempfile.TemporaryDirectory(prefix='lol-history-preview-');ui.app_home=lambda:settings.name
Path(settings.name,'settings.json').write_text(json.dumps({'design3':True,'theme':os.environ.get('SIM_THEME','lol'),'scale':int(os.environ.get('SIM_SCALE',100))}))
for method in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon'):setattr(ui.App,method,lambda *a,**k:None)
lcu.live_data=lambda:None;lcu.LCU.image=lambda *a:None
ME={'riot':'Halch#9200','puuid':'p3'}
lcu.LCU.me=lambda *a:dict(ME)
lcu.LCU.rank=lambda *a:{'tier':'EMERALD','div':'IV','lp':17,'w':221,'l':211}
GAMES=[{'gid':1000+i,'champ':103 if i%3==0 else 112 if i%3==1 else 134,'win':i%3!=1,'k':8+i%4,'d':3+i%3,'a':10+i%5,
        'dur':1800+i*15,'cs':200+i,'vis':25,'dmg':26000,'gold':14000,'q':420 if i%4 else 440,'lane':'MIDDLE','role':'SOLO',
        't':1793700000000-i*5400000,'items':[1056,3020,3118,3089,3135,3157,3340],'perk':8112,'spells':[4,12]} for i in range(30)]
# First match is solo, permitting a known demo LP change.
GAMES[0]['q']=420;GAMES[0]['d']=8
GAME=game_fixture()
for i,p in enumerate(GAME['participants']):
    p['stats']['deaths']=[4,3,8,4,6,5,6,6,5,6][i]
    p['stats']['totalDamageDealtToChampions']=18000+i*1000
GAME['participants'][2]['stats'].update(kills=8,deaths=8,assists=10,totalMinionsKilled=170,totalDamageDealtToChampions=26000,goldEarned=14000)
GAME['participantIdentities'][2]['player'].update(gameName='Halch',tagLine='9200')
GAME['participantIdentities'][5]['player']['gameName']='ОченьДлинныйНикПротивника'
lcu.LCU.history=lambda *a,**k:copy.deepcopy(GAMES)
lcu.LCU.game=lambda self,gid:dict(copy.deepcopy(GAME),gameId=gid)
app=ui.App(lolhelper.load_data(),'Демо');errors=[];checks=[]
app.root.report_callback_exception=lambda et,ev,tb:(errors.append(str(ev)),traceback.print_exception(et,ev,tb))
if app.dash:app.dash.withdraw()
app.icons.a=json.loads(Path(os.environ['SIM_ASSETS_JSON']).read_text())
for group,var in [('champ','SIM_POOL_PORTRAITS'),('item','SIM_HOME_ITEMS')]:
    folder=Path(os.environ[var]) if os.environ.get(var) else None
    for p in folder.glob('*.png') if folder else []:app.icons.a.setdefault(group,{})[p.stem]=base64.b64encode(p.read_bytes()).decode()
app._simulation_image_refs=list(app.icons.cache.values());app.icons.cache.clear();app.icons.raw.clear();app.account=dict(ME)
app.status.configure(text='Демонстрационные матчи · клиент не опрашивается')
app.root.title('LoL Helper · История · демонстрация');app.root.geometry(os.environ.get('SIM_GEOMETRY','1440x1100+0+0'))
app.nb.select(1);view=app.history_view

def settle(until=lambda:True):
    for _ in range(200):
        app.root.update()
        if until():break
        time.sleep(.005)
    assert until(),'async timeout'
    app.root.update_idletasks()

def capture(name,window=None):
    window=window or app.root;app.root.update();app.root.update_idletasks()
    if window is not app.root and getattr(window,'job',None):
        app.root.after(120,app.root.quit);app.root.mainloop()
    app.root.update()
    if window is app.root:
        for card in view.row_widgets:
            assert card.winfo_width()<=view.winfo_width()
            for child in card.winfo_children():
                assert child.winfo_x()+child.winfo_width()<=card.winfo_width()+2,(name,'clipped row')
    else:
        cards=getattr(window,'player_cards',[])
        for card in cards:
            assert card.winfo_x()+card.winfo_width()<=card.master.winfo_width()+2
        if window.layout and len(cards)==10:
            sizes=[(c.winfo_width(),c.winfo_height()) for c in cards]
            assert max(w for w,h in sizes)-min(w for w,h in sizes)<=1,sizes
            assert len({h for w,h in sizes})==1,sizes
    x,y=window.winfo_rootx(),window.winfo_rooty()
    ImageGrab.grab(bbox=(x,y,x+window.winfo_width(),y+window.winfo_height())).save(OUT/name)
    with Image.open(OUT/name) as screenshot:screenshot.verify()
    checks.append({'stage':name,'size':[window.winfo_width(),window.winfo_height()],'matches':len(view.filtered)})

def go():
    try:
        capture('history-saved.png')
        view.use_source('client');settle(lambda:not view.busy)
        assert view.client_owner=='p3' and len(view.client_rows)==30
        view.set_client(GAMES,{1000:18,1001:-17,1002:21},'p3',ME['riot'])
        capture('history-client.png')
        view.query.set('Ари');view.refresh();assert all(r['champion']=='Ahri' for r in view.filtered)
        view.select_result('loss');assert not view.filtered;capture('history-empty.png')
        view.reset();view.more();assert len(view.row_widgets)==30
        view.limit=20;view.refresh()
        popup=view.open_record(view.filtered[0]);settle(lambda:not popup.loading)
        assert popup.review and len(popup.review['rows'])==10
        assert not popup.analysis_open
        popup.toggle_analysis();popup.geometry(os.environ.get('SIM_DETAIL_GEOMETRY','1280x1200+20+20'));settle()
        popup.render();settle();capture('history-match.png',popup)
        popup.close()
        saved=copy.deepcopy(view.client_rows)
        app.client.history=lambda *a,**k:None
        view.load_client();settle(lambda:not view.busy)
        assert view.client_rows==saved;capture('history-refresh-error.png')
        entered=threading.Event();release=threading.Event()
        def delayed(*a,**k):entered.set();release.wait(2);return copy.deepcopy(GAMES)
        app.client.history=delayed;view.load_client();assert entered.wait(1)
        app.account={'puuid':'other','riot':'Other#TEST'};view.account_changed(app.account)
        release.set();settle();assert view.client_rows is None
        app.account=dict(ME);view.set_client(GAMES,{},'p3',ME['riot'])
        entered.clear();release.clear()
        def delayed_game(gid):entered.set();release.wait(2);return dict(copy.deepcopy(GAME),gameId=gid)
        app.client.game=delayed_game;popup=view.open_record(view.filtered[0]);assert entered.wait(1)
        popup.close();release.set();settle();assert not popup.winfo_exists()
        view.source='saved';view.refresh();popup=view.open_record(view.filtered[0])
        assert not popup.loading
        if view.filtered[0].get('match_id') in app.data.d.get('match_details',{}):assert popup.review and len(popup.review['rows'])==10
        else:assert popup.review is None
        capture('history-saved-detail.png',popup);popup.close()
        popup=view.open_record(dict(view.filtered[0],match_id=None,gid=None))
        assert popup.review is None;capture('history-saved-legacy.png',popup);popup.close()
        app.root.geometry('1060x740+0+0');settle();view.refresh();settle();capture('history-compact.png')
        assert not errors,errors
    except Exception as error:errors.append(repr(error));raise
    finally:
        (OUT/'native-checks.json').write_text(json.dumps({'errors':errors,'checks':checks},ensure_ascii=False))
        app.root.destroy()
app.root.after(700,go);app.run()
assert not errors,errors
print(OUT)
