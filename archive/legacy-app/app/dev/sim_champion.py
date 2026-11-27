"""Actual champion-page Tk previews with isolated settings and no network or exports."""
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
import core
import lcu
import lolhelper
import matchup_data
import offmeta_data
import player_builds
import ui
OUT=Path(os.environ.get('SIM_OUT','/tmp/champion-preview'));OUT.mkdir(parents=True,exist_ok=True)
tmp=tempfile.TemporaryDirectory(prefix='lol-champion-preview-');ui.app_home=lambda:tmp.name
Path(tmp.name,'settings.json').write_text(json.dumps({'design3':True,'theme':os.environ.get('SIM_THEME','lol'),'scale':int(os.environ.get('SIM_SCALE',100)),'sound':'off'}))
for method in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon'):setattr(ui.App,method,lambda *a,**k:None)
lcu.live_data=lambda:None;lcu.LCU.image=lambda *a:None;lcu.LCU.me=lambda *a:None
fixture={'prim':8100,'sec':8200,'perks':[8112,8126,8140,8135,8226,8210], 'shards':[5008,5008,5001],
         'spells':['SummonerFlash','SummonerTeleport'],'start':[1056,2003],'core':[6655,3020,3118],'i4':[3089],'i5':[3135],'i6':[3157],
         'skills':'QWEQQRQWQWRWWEEREE','skill_prio':'QWE','wr_runes':52.4,'n_runes':4200,'wr_core':58.1,'n_core':1600}
full=dict(fixture,pick=copy.deepcopy(fixture),win=dict(fixture,perks=[8214,8226,8210,8237,8345,8347],wr_runes=54.1,n_runes=1800,core=[6655,3020,4645]),wr=51.8,games=25000,
          situ=[(3157,'Защита','против взрывного урона'),(3135,'Пробивание','против сопротивления магии')])
def fetch(self,kind,champion,role):
    if not champion:return None
    key=(champion,role) if kind=='build' else (kind,champion,role)
    if kind=='build':value=copy.deepcopy(full)
    elif kind=='counter':value={'counters':[{'cid':int(self.cid(c)),'vsWr':wr,'d2':wr-50,'n':n} for c,wr,n in [('Viktor',47.2,3250),('Syndra',48.1,2840),('Yasuo',49.0,2520),('Orianna',52.1,2310),('Lux',53.4,1980),('Akali',54.2,2100)]]}
    else:return None
    self.lola[key]=value;self.lola_state[key]='ok';return value
def matchup(self,champion,role,opponent):
    key=('matchup',champion,role,opponent)
    value=matchup_data.parse((Path(__file__).parent/'fixtures/lolalytics-matchup.html').read_text(),champion,role,opponent,self.data)
    self.lola_state[key]='ok' if value else 'fail'
    if value:self.lola[key]=value
    return value
OFFMETA=json.loads((Path(__file__).parent/'fixtures/mobalytics-offmeta.json').read_text())['payload']
ui.App.offmeta_build=lambda self,champion,role:offmeta_data.parse_state(OFFMETA,champion,role)
PLAYERS=json.loads((Path(__file__).parent/'fixtures/mobalytics-players.json').read_text())
def player_options(self,champion,role):
    value=player_builds.listing(PLAYERS['index'],champion,role)
    if value:
        for group in value['groups'].values():
            for i,row in enumerate(group):
                full=player_builds.detail(PLAYERS['pages'].get(row['id']),row)
                if full:group[i]=full
    return value
ui.App.player_builds=player_options
ui.App.lola_fetch=fetch;ui.App.lola_matchup=matchup
app=ui.App(lolhelper.load_data(),'Демонстрация');errors=[];checks=[]
app.root.report_callback_exception=lambda et,ev,tb:(errors.append(str(ev)),traceback.print_exception(et,ev,tb))
if app.dash:app.dash.withdraw()
app.icons.a=json.loads(Path(os.environ['SIM_ASSETS_JSON']).read_text())
for group,var in [('champ','SIM_POOL_PORTRAITS'),('item','SIM_HOME_ITEMS')]:
    folder=Path(os.environ[var]) if os.environ.get(var) else None
    for file in folder.glob('*.png') if folder else []:app.icons.a.setdefault(group,{})[file.stem]=base64.b64encode(file.read_bytes()).decode()
app.icons.cache.clear();app.icons.raw.clear()
app.player.games=[{'c':'Ahri','pos':'MIDDLE','w':int(i%3!=0),'k':7+i%4,'d':3+i%3,'a':9+i%5,'csm':6.5+i%4*.2,'opp':'Viktor' if i%2==0 else 'Lux','t':1793700000-i*3600} for i in range(24)]
app.root.title('LoL Helper · Чемпион · демонстрация');app.root.geometry(os.environ.get('SIM_GEOMETRY','1500x1300+0+0'))
app.status.configure(text='Демонстрационные сборки и матчапы · без подключения к клиенту')
app.nb.select(2);view=app.champion_view

def settle():app.root.update();app.root.update_idletasks()
def capture(name):
    settle();subprocess.run(['import','-window',str(app.root.winfo_id()),str(OUT/name)],check=True)
    checks.append({'stage':name,'size':[app.root.winfo_width(),app.root.winfo_height()],'two_columns':view.layout})
def go():
    try:
        capture('champion-search.png')
        view.query.set('ahri');view.search_pick();assert view.champion=='Ahri'
        old_pick=app.s['rune_pick'];old_context=app.s['draft_build_context']
        view.choose('Ahri','MIDDLE');capture('champion-main.png')
        assert view.selected_variant['perks'][0]==8112
        assert len(app.player.on('Ahri','MIDDLE'))==24
        assert len(view.option_buttons)==3
        view.select_build('general','offmeta');assert view.selected_variant['perks'][0]==8992
        assert view.selected_variant['core']==[2503,3158,3100]
        capture('champion-offmeta.png')
        view.toggle_details();assert view.expanded
        cv=app.canvases[str(app.tab_champ.outer)];cv.yview_moveto(.35);settle();capture('champion-offmeta-details.png');cv.yview_moveto(0)
        view.toggle_details();view.select_build('general','pick')
        capture('champion-curtain-closed.png')
        view.toggle_right();settle();assert view.right_open
        capture('champion-curtain-open.png')
        if view.layout:
            left_end=view.left_column.winfo_y()+view.left_column.winfo_height()-8
            right_end=view.right_column.winfo_y()+view.right_column.winfo_height()
            assert abs(left_end-right_end)<=1,(left_end,right_end)
        assert len(view.players['groups']['OTP'])==3 and len(view.players['groups']['Pro'])==2
        view.select_player(view.players['groups']['OTP'][0]['id']);assert view.selected_player['kind']=='OTP'
        capture('champion-mainer.png')
        view.select_player(view.players['groups']['Pro'][0]['id']);assert view.selected_player['name']=='Kenas'
        if view.right_canvas:view.right_canvas.yview_moveto(.45);settle()
        capture('champion-pro.png')
        cv.yview_moveto(.45);settle();capture('champion-players.png');cv.yview_moveto(0)
        assert app.s['rune_pick']==old_pick and app.s['draft_build_context']==old_context
        view.select_build('general','pick')
        view.select_build('general','win');assert view.selected_variant['perks'][0]==8214
        assert app.s['rune_pick']==old_pick and app.s['draft_build_context']==old_context
        view.select_opponent('Viktor');assert view.context=='matchup' and view.selected_variant
        view.select_build('matchup','win');capture('champion-matchup.png')
        view.toggle_details();assert view.expanded
        cv=app.canvases[str(app.tab_champ.outer)];cv.yview_moveto(.55);settle();capture('champion-details.png');cv.yview_moveto(0)
        pool=copy.deepcopy(app.current_pool());view.toggle_pool();assert ('Ahri' in app.current_pool()['MIDDLE'])!=('Ahri' in pool['MIDDLE']);view.toggle_pool();assert app.current_pool()==pool
        view.choose('Ahri','TOP');assert view.role=='TOP' and not view.selected_variant # fixture validates middle only
        view.choose('Ahri','MIDDLE');view.select_build('general','pick')
        original=app.lola_fetch;app.lola_fetch=lambda *a:None;app.lola_state[('Ahri','MIDDLE')]='fail';app.lola_state[('counter','Ahri','MIDDLE')]='fail';view.refresh();capture('champion-unavailable.png');app.lola_fetch=original
        view.choose('Ahri','MIDDLE');app.set_who(None);capture('champion-no-profile.png')
        app.root.geometry('1060x820+0+0');settle();view.refresh();capture('champion-compact.png')
        assert not view.layout
        assert not errors,errors
    except Exception as error:errors.append(repr(error));raise
    finally:
        (OUT/'native-checks.json').write_text(json.dumps({'errors':errors,'checks':checks},ensure_ascii=False));app.root.destroy()
app.root.after(600,go);app.run();assert not errors,errors
print(OUT)
