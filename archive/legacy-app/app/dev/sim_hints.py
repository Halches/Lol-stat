"""Native hint controls and editor with temporary settings and silent audio stubs."""
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
import core,lcu,lolhelper,ui
OUT=Path(os.environ.get('SIM_OUT','/tmp/hints-preview'));OUT.mkdir(parents=True,exist_ok=True)
tmp=tempfile.TemporaryDirectory(prefix='lol-hints-preview-');ui.app_home=lambda:tmp.name
Path(tmp.name,'settings.json').write_text(json.dumps({'design3':True,'theme':os.environ.get('SIM_THEME','lol'),'scale':int(os.environ.get('SIM_SCALE',100)),'sound':'off'}))
for method in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon'):setattr(ui.App,method,lambda *a,**k:None)
lcu.live_data=lambda:None;lcu.LCU.image=lambda *a:None;lcu.LCU.me=lambda *a:None
app=ui.App(lolhelper.load_data(),'Предпросмотр');errors=[];checks=[]
app.root.report_callback_exception=lambda et,ev,tb:(errors.append(str(ev)),traceback.print_exception(et,ev,tb))
if app.dash:app.dash.withdraw()
app.icons.a=json.loads(Path(os.environ['SIM_ASSETS_JSON']).read_text());app.icons.cache.clear();app.icons.raw.clear()
app.voice.say=lambda *a,**k:None;app.voice.beep=lambda *a,**k:None
app.status.configure(text='Предпросмотр подсказок · без игры и озвучки');app.root.geometry(os.environ.get('SIM_GEOMETRY','1500x1250+0+0'));app.nb.select(3)
view=app.hints_view

def settle():app.root.update();app.root.update_idletasks()
def capture(name,win=None):
    settle();w=win or app.root
    subprocess.run(['import','-window',str(w.winfo_id()),str(OUT/name)],check=True)
    checks.append({'stage':name,'size':[w.winfo_width(),w.winfo_height()],'shown':len(view.shown)})
def go():
    try:
        view.refresh();capture('hints-main.png')
        assert not view.controls.winfo_ismapped()
        view.toggle_bulk();settle();assert view.controls.winfo_ismapped();view.toggle_bulk()
        view.toggle_details('gank1');settle();assert view.details['gank1'][0].winfo_ismapped();capture('hints-details.png')
        view.refresh();assert 'gank1' in view.expanded;view.toggle_details('gank1')
        assert len(view.shown)==len([h for h in core.HINTS if core.hint_for(h[0],'TOP')])
        view.choose_role('UTILITY');view.choose_scope('role');assert all('UTILITY' in core.HINT_ROLES[h[0]] for h in view.shown)
        before=copy.deepcopy(app.s['hints_role']['TOP']);view.query.set('линзу');view.refresh();assert [h[0] for h in view.shown]==['lens']
        view.set_all('beep');assert app.hint_mode('lens','UTILITY')=='beep';assert app.s['hints_role']['TOP']==before
        view.choose_scope('all');view.query.set('');view.mode.set('Все режимы');view.refresh();capture('hints-support.png')
        view.query.set('ганк');view.refresh();capture('hints-search.png')
        view.query.set('нет такой подсказки');view.refresh();assert not view.shown;capture('hints-empty.png')
        view.query.set('');view.choose_role('MIDDLE');view.choose_scope('role');view.refresh()
        app.edit_hint('gank1',next(h[2] for h in core.HINTS if h[0]=='gank1'));editor=app.hint_editor
        editor.text.insert('1.0','Проверь обзор: {текст}');editor.say.insert('1.0','Поставь вард. {текст}');capture('hints-editor.png',editor);editor.save()
        assert ui.Settings(tmp.name)['hint_text']['gank1']['text']=='Проверь обзор: {текст}'
        app.hint_vars['gank1'].set(ui.MODES['text']);view.change_mode('gank1');view.test('gank1','Пример предупреждения о ганке')
        assert view.inline_previews['gank1'].cget('text')=='Проверь обзор: Пример предупреждения о ганке'
        capture('hints-custom.png')
        view.mode.set(ui.MODES['text']);view.refresh();assert all(app.hint_mode(h[0])=='text' for h in view.shown)
        ids={h[0] for h in view.shown};view.set_all('off');assert all(app.hint_mode(h)=='off' for h in ids)
        assert not view.shown # the active mode filter updates after the batch, not during it
        view.mode.set('Все режимы');view.reset_modes();assert app.s['hint_text'].get('gank1')
        app.root.geometry('1060x820+0+0');settle();view.refresh();assert not view.wide;capture('hints-compact.png')
        assert not errors,errors
    except Exception as error:errors.append(repr(error));raise
    finally:
        (OUT/'native-checks.json').write_text(json.dumps({'errors':errors,'checks':checks},ensure_ascii=False));app.root.destroy()
app.root.after(600,go);app.run();assert not errors,errors
print(OUT)
