"""Render the real draft UI offline; SIM_OUT, SIM_ASSETS_JSON and DISPLAY select fixtures/output."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
import lcu
import lolhelper
import ui

OUT = Path(os.environ.get('SIM_OUT', tempfile.mkdtemp(prefix='lol-draft-pictures-')))
OUT.mkdir(parents=True, exist_ok=True)
settings_home = tempfile.TemporaryDirectory(prefix='lol-native-settings-')
ui.app_home = lambda: settings_home.name
(Path(settings_home.name)/'settings.json').write_text(json.dumps({
    'design3':True, 'scale':int(os.environ.get('SIM_SCALE',100)),
    'theme':os.environ.get('SIM_THEME','lol')}))
ui.App.poll = lambda self: None
ui.App.load_lanes = lambda self: None
ui.App.load_changelog = lambda self: None
ui.App.hist_refresh = lambda self: None
ui.App.check_updates = lambda self, manual=False: None
lcu.live_data = lambda: None
lcu.LCU.image = lambda self, path: None
lcu.LCU.me = lambda self: None
lcu.LCU.history = lambda self, pu, n=20: []
fixture = {'prim': 8100, 'sec': 8200, 'perks': [8112, 8126, 8140, 8135, 8226, 8210],
           'shards': [5008,5008,5001], 'spells': ['SummonerFlash', 'SummonerTeleport'],
           'start': [1056,2003], 'core': [6655,3020,3118], 'i4': [3089], 'i5': [3135], 'i6': [3157],
           'skills': 'QWEQQRQWQWRWWEEREE', 'skill_prio': 'QWE',
           'wr_runes': 52.4, 'n_runes': 4200, 'wr_core': 58.1, 'n_core': 1600}
full = dict(fixture, pick=copy.deepcopy(fixture), win=dict(fixture, perks=[8214,8226,8210,8237,8345,8347]),
            games=25000, situ=[(3157,'Защита','против взрывного урона'),(3135,'Пробивание','против сопротивления магии')])

def fetch(self, kind, champion, role):
    if not champion or not role: return None
    key = (champion, role) if kind == 'build' else (kind, champion, role)
    if kind == 'build': value = full
    elif kind == 'counter':
        value = {'counters':[{'cid':int(self.cid(c)), 'vsWr':wr, 'd2':delta, 'n':1500}
                             for c,wr,delta in [('Ahri',46.8,-2),('Orianna',47.5,-1.5),('Syndra',47,-1.8)]]}
    elif kind == 'build-team':
        value = {'team': {'middle':[[int(self.cid(c)),54+i,1,2+i,1,1600] for i,c in enumerate(('Ahri','Orianna','Syndra'))]}}
    else: return None
    self.lola[key] = value; self.lola_state[key] = 'ok'
    return value
ui.App.lola_fetch = fetch
errors=[]
app = ui.App(lolhelper.load_data(), 'Разработка · демонстрация')
app.root.report_callback_exception = lambda et, ev, tb: errors.append(str(ev))
assets_file = os.environ.get('SIM_ASSETS_JSON')
if assets_file:
    app.icons.a = json.loads(Path(assets_file).read_text())
    app.icons.cache.clear(); app.icons.raw.clear()
app.player.pool = {'MIDDLE':['Ahri','Orianna','Syndra']}
app.s['draft_scope'] = 'pool'
app.s['auto_import'] = False
app.s['auto_parts'] = {'runes':True,'items':True,'spells':False}
for key, value in app.s['auto_parts'].items(): app.auto_vars[key].set(value)
app.lola.clear(); app.lola_state.clear()
hist = {'n':10,'w':7,'streak':3,'on':24,'on_w':15,'kda':3.8,'tags':['почти только'],
        'good':['редко умирает (3.4 за игру)'], 'bad':['мало обзора (0.4/мин)'], 'tilt':[]}
allies = [{'c':ch,'pos':role,'me':i==2,'rank':{'tier':'EMERALD','div':'II','lp':64,'w':68,'l':52},
           'hist':dict(hist), 'pu':'demo'+str(i)}
          for i,(ch,role) in enumerate(zip(['Malphite','Sejuani','Ahri','Jinx','Thresh'],core.ROLES))]
cs={'role':'MIDDLE','me':'Ahri','allies':allies,'enemies':['Renekton','LeeSin','Viktor','Caitlyn','Lux'],
    'locked':False,'unavailable':set(['Malphite','Sejuani','Jinx','Thresh','Renekton','LeeSin','Viktor','Caitlyn','Lux']), 'left':28}
app.draft=cs
r={'role':'MIDDLE','roles':dict(zip(cs['enemies'],core.ROLES)),'opp':'Viktor',
   'picks':[{'c':c,'name':app.data.cn(c),'why':'Из пула · личная статистика и данные роли'} for c in ['Ahri','Orianna','Syndra']]}
app.hraw={'demo'+str(i):[] for i in range(5)}
app.root.withdraw(); app.dash.geometry(os.environ.get('SIM_GEOMETRY','1920x1080+0+0')); app.dash.update()
app.dash.title('LoL Helper · драфт · демонстрационные данные')

def capture(name):
    app.dash.update_idletasks()
    subprocess.run(['import','-window',str(app.dash.winfo_id()),str(OUT/name)],check=True)

def show(locked=False):
    cs['locked']=locked
    app.dash.draft_sig=None
    app.dash.show_draft(cs,r,[('Fizz',2,'Сложный матчап по истории')])
    app.dash.head.configure(text=app.dash.head.cget('text')+' · ДЕМОНСТРАЦИЯ')
    app.dash.deiconify(); app.dash.update()

def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)

def exercise_folds():
    for title in ('Разбор сборки', 'Композиции', 'Кого банить'):
        button = next(w for w in descendants(app.dash.mid)
                      if isinstance(w, ui.ttk.Button) and title in w.cget('text'))
        button.invoke(); app.dash.update()
        button.invoke(); app.dash.update()
    # Missing network/build data must still open a working preview drawer.
    app.lola_build = lambda champion, role: None
    show(False)
    button = next(w for w in descendants(app.dash.mid)
                  if isinstance(w, ui.ttk.Button) and 'Предварительная сборка' in w.cget('text'))
    button.invoke(); app.dash.update()

def finish():
    Path(OUT/'native-checks.json').write_text(json.dumps({'errors':errors,'body_width':app.dash.body.winfo_width(),
       'window_width':app.dash.winfo_width(),'window_height':app.dash.winfo_height(),
       'content_height':app.dash.body.winfo_reqheight(),
       'columns':[{'actual':col.winfo_width(),'requested':col.winfo_reqwidth()} for col in [app.dash.cols[0],app.dash.mid,app.dash.cols[1]]]},ensure_ascii=False))
    app.root.destroy()
app.root.after(300, lambda:show(False))
app.root.after(900, lambda:capture('native-draft-selection.png'))
app.root.after(1100, lambda:show(True))
app.root.after(1500, lambda:capture('native-draft-builds.png'))
app.root.after(1600,exercise_folds)
app.root.after(2100,finish)
app.run()
if errors: raise RuntimeError(errors)
print(OUT)
