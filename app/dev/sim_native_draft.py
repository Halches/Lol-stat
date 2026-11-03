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
import matchup_data
import offmeta_data
import player_builds
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
full = dict(fixture, pick=copy.deepcopy(fixture), win=dict(fixture, perks=[8214,8226,8210,8237,8345,8347], wr_runes=54.1, n_runes=1800, core=[6655,3020,4645]),
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
def fetch_matchup(self, champion, role, opponent):
    if not champion or not opponent: return None
    key = ('matchup', champion, role, opponent)
    value = matchup_data.parse((Path(__file__).parent/'fixtures/lolalytics-matchup.html').read_text(), champion, role, opponent, self.data)
    if value: self.lola[key] = value
    self.lola_state[key] = 'ok' if value else 'fail'
    return value
ui.App.lola_matchup = fetch_matchup
ui.App.lola_fetch = fetch
OFFMETA=json.loads((Path(__file__).parent/'fixtures/mobalytics-offmeta.json').read_text())['payload']
ui.App.offmeta_build=lambda self,ch,role:offmeta_data.parse_state(OFFMETA,ch,role)
PLAYERS=json.loads((Path(__file__).parent/'fixtures/mobalytics-players.json').read_text())
def player_options(self,ch,role):
    value=player_builds.listing(PLAYERS['index'],ch,role)
    if value:
        for group in value['groups'].values():
            for i,row in enumerate(group):
                details=player_builds.detail(PLAYERS['pages'].get(row['id']),row)
                if details:group[i]=details
    return value
ui.App.player_builds=player_options
errors=[]
geometry_checks=[]
app = ui.App(lolhelper.load_data(), 'Разработка · демонстрация')
app.root.report_callback_exception = lambda et, ev, tb: errors.append(str(ev))
assets_file = os.environ.get('SIM_ASSETS_JSON')
if assets_file:
    app.icons.a = json.loads(Path(assets_file).read_text())
    app.icons.a.setdefault('skill',{}).update({
        'Ahri'+letter:app.icons.a['champ']['Ahri'+letter] for letter in 'QWER' if 'Ahri'+letter in app.icons.a['champ']})
    app.icons.cache.clear(); app.icons.raw.clear()
app.player.pool = {'MIDDLE':['Ahri','Orianna','Syndra']}
app.s['draft_scope'] = 'pool'
app.s['draft_build_context'] = os.environ.get('SIM_BUILD_CONTEXT','general')
app.s['rune_pick'] = os.environ.get('SIM_BUILD_VARIANT','pick')
app.s['auto_import'] = False
app.s['auto_parts'] = {'runes':True,'items':True,'spells':False}
for key, value in app.s['auto_parts'].items(): app.auto_vars[key].set(value)
app.lola.clear(); app.lola_state.clear()
hist = {'n':10,'w':7,'streak':3,'on':24,'on_w':15,'kda':3.8,'tags':['почти только'],
        'good':['редко умирает (3.4 за игру)'], 'bad':['мало обзора (0.4/мин)'], 'tilt':[]}
allies = [{'c':ch,'pos':role,'me':i==2,'rank':{'tier':'EMERALD','div':'II','lp':64,'w':68,'l':52},
           'hist':dict(hist, extra_comments=([('G10','Топ-1000 · №42 в мире · Lolalytics','good'),('G7','Мейнер · 16/20 игр','good')] if i==2 else [('G8','Участие в убийствах 68% · 5 игр','good'),('N4','Непривычная роль · 1/15 игр','neutral')] if i==0 else [('G9','До 14 мин: 0.6 смерти · 5 игр','good')] if i==1 else [])), 'pu':'demo'+str(i)}
          for i,(ch,role) in enumerate(zip(['Malphite','Sejuani','Ahri','Jinx','Thresh'],core.ROLES))]
cs={'role':'MIDDLE','me':'Ahri','allies':allies,'enemies':['Renekton','LeeSin','Viktor','Caitlyn','Lux'],
    'locked':False,'unavailable':set(['Malphite','Sejuani','Jinx','Thresh','Renekton','LeeSin','Viktor','Caitlyn','Lux']), 'left':28}
app.draft=cs
r={'role':'MIDDLE','roles':dict(zip(cs['enemies'],core.ROLES)),'opp':'Viktor',
   'picks':[{'c':c,'name':app.data.cn(c),'why':'Из пула · личная статистика и данные роли'} for c in ['Ahri','Orianna','Syndra']]}
app.hraw={'demo'+str(i):[{'champ':103, 'win':j%2==0, 'dur':1800, 'lane':'MIDDLE', 'role':'SOLO',
           'k':8, 'd':3, 'a':11, 'cs':220, 't':0, 'gid':100+j} for j in range(5)] for i in range(5)}
app.root.withdraw(); app.dash.geometry(os.environ.get('SIM_GEOMETRY','1920x1080+0+0')); app.dash.update_idletasks()
app.dash.title('LoL Helper · драфт · демонстрационные данные')

def capture(name):
    app.root.update();app.dash.update_idletasks()
    check_geometry(name)
    subprocess.run(['import','-window',str(app.dash.winfo_id()),str(OUT/name)],check=True)
    if name == 'native-draft-builds.png':
        mid = app.dash.mid
        x = mid.winfo_rootx()-app.dash.winfo_rootx()
        y = mid.winfo_rooty()-app.dash.winfo_rooty()
        height = min(mid.winfo_reqheight(), app.dash.winfo_height()-y)
        region = f'{mid.winfo_width()}x{height}+{x}+{y}'
        subprocess.run(['import','-window',str(app.dash.winfo_id()),'-crop',region,str(OUT/'native-draft-builds-detail.png')],check=True)

def check_geometry(stage):
    cards = app.dash._draft_cards
    rects = [(card.winfo_x(), card.winfo_y(), card.winfo_width(), card.winfo_height()) for card in cards]
    assert len(rects) == 10, (stage, rects)
    assert len({r[2:] for r in rects}) == 1, (stage, rects)
    assert [r[1] for r in rects[:5]] == [r[1] for r in rects[5:]], (stage, rects)
    assert all(card.body.winfo_reqheight() <= card.winfo_height()-2*card.vpad for card in cards), stage
    comment_backgrounds = {bg for bg,fg in ui.player_comments.palette(ui.C['dark']).values()}
    for card in cards:
        rows = {}
        for widget in descendants(card):
            if isinstance(widget, ui.tk.Label) and widget.cget('bg') in comment_backgrounds:
                rows.setdefault(widget.winfo_rooty(), set()).add(widget.cget('bg'))
        assert all(len(colours) == 1 for colours in rows.values()), (stage, 'mixed comment colours in a row')
    view = app.dash._draft_view
    top = view.center_clip.winfo_rooty()
    bottom = top+view.center_clip.winfo_height()
    assert top == cards[0].winfo_rooty(), (stage,'centre top',top,cards[0].winfo_rooty())
    assert bottom == cards[4].winfo_rooty()+cards[4].winfo_height(), (stage,'centre bottom',bottom)
    skills = view.center_bottom
    assert skills.winfo_rooty()+skills.winfo_height() <= bottom, (stage, 'skills overflow')
    geometry_checks.append({'centre_top':top,'centre_bottom':bottom,'stage':stage, 'size':rects[0][2:], 'rows':[r[1] for r in rects[:5]]})

def show(locked=False):
    cs['locked']=locked
    app.dash.draft_sig=None
    app.dash.show_draft(cs,r,[('Fizz',2,'Сложный матчап по истории')])
    ui.tk.Label.configure(app.dash.head, text=app.dash.head.cget('text')+' · демонстрация')
    app.dash.deiconify(); app.dash.update_idletasks()

def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)

def exercise_external():
    previous=(app.s['draft_build_context'],app.s['rune_pick'])
    app.draft=cs
    app.set_draft_build('offmeta','pick')
    assert app.selected_draft_build(cs)['pick']['core']==[2503,3158,3100]
    show(True);app.dash._draft_view.center_canvas.yview_moveto(.4);app.dash.update_idletasks();capture('native-draft-offmeta.png')
    row=app.player_builds('Ahri','MIDDLE')['groups']['OTP'][0]
    app.set_draft_build('player:'+row['id'],'pick')
    assert app.selected_draft_build(cs)['pick']==row['variant']
    show(True);app.dash._draft_view.center_canvas.yview_moveto(.65);app.dash.update_idletasks();capture('native-draft-player.png')
    app.s['draft_build_context'],app.s['rune_pick']=previous
    show(True)
    window=app.dash;window.close();app.root.update();assert not window.winfo_viewable()
    app.on_draft(cs);app.root.update();assert app.dash is window and not window.winfo_viewable()
    app.open_dash();app.root.update();assert window.winfo_viewable()

def exercise_folds():
    exercise_external()
    view = app.dash._draft_view
    view.center_canvas.yview_moveto(1); app.dash.update_idletasks()
    assert view.center_canvas.yview()[1] >= .999, 'centre cannot scroll to the end'
    view.center_canvas.yview_moveto(0); app.dash.update_idletasks()
    history = next(w for w in descendants(app.dash.cols[0])
                   if isinstance(w, ui.ttk.Button) and 'Последние матчи' in w.cget('text'))
    history.invoke(); app.dash.update_idletasks()
    assert ('history', 'demo0') in app.dash._draft_open, 'history did not open'
    check_geometry('history-open')
    history.invoke(); app.dash.update_idletasks()
    assert ('history', 'demo0') not in app.dash._draft_open, 'history did not close'
    check_geometry('history-closed')
    for title in ('Полный разбор сборки', 'Композиции', 'Кого банить'):
        button = next(w for w in descendants(app.dash.mid)
                      if isinstance(w, ui.ttk.Button) and title in w.cget('text'))
        button.invoke(); app.dash.update_idletasks()
        button.invoke(); app.dash.update_idletasks()
    # Missing network/build data must still open a working preview drawer.
    app.lola_build = lambda champion, role: None
    show(False)
    button = next(w for w in descendants(app.dash.mid)
                  if isinstance(w, ui.ttk.Button) and 'Предварительная сборка' in w.cget('text'))
    button.invoke(); app.dash.update_idletasks()

def finish():
    Path(OUT/'native-checks.json').write_text(json.dumps({'errors':errors,'card_checks':geometry_checks,'body_width':app.dash.body.winfo_width(),
       'window_width':app.dash.winfo_width(),'window_height':app.dash.winfo_height(),
       'content_height':app.dash.body.winfo_reqheight(),
       'columns':[{'actual':col.winfo_width(),'requested':col.winfo_reqwidth()} for col in [app.dash.cols[0],app.dash.mid,app.dash.cols[1]]]},ensure_ascii=False))
    app.root.destroy()

original_geometry = app.dash.geometry()
def resize_for_check():
    app.dash.geometry('1366x768+0+0' if app.dash.winfo_width() >= 1700 else '1920x1080+0+0')
def restore_size():
    app.dash.update_idletasks()
    check_geometry('resized')
    app.dash.geometry(original_geometry)
def run_checks():
    try:
        show(False);capture('native-draft-selection.png')
        show(True);capture('native-draft-builds.png')
        resize_for_check();app.root.update();app.dash._draft_view.sync_card_sizes()
        restore_size();app.root.update();app.dash._draft_view.sync_card_sizes()
        exercise_folds()
    except Exception as error:errors.append(repr(error))
    finally:finish()
app.root.after(300,run_checks)
app.run()
if errors: raise RuntimeError(errors)
print(OUT)
