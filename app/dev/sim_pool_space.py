"""Measure real pool viewport at 1080p and capture the Windows Tk window."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import ImageGrab
import lcu
import lolhelper
import ui
from pool_ui import PoolScreen

OUT=Path(os.environ.get('POOL_SPACE_OUT','dist/pool-space'));OUT.mkdir(parents=True,exist_ok=True)


def main():
    with tempfile.TemporaryDirectory(prefix='lol-pool-space-') as folder:
        ui.app_home=lambda:folder
        Path(folder,'settings.json').write_text(json.dumps({'design3':True,'dashboard':False,'sound':'off'}),encoding='utf-8')
        for name in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon','sync_phone'):
            setattr(ui.App,name,lambda *a,**k:None)
        ui.Voice.warm=lambda *a:None;lcu.LCU.image=lambda *a:None
        app=ui.App(lolhelper.load_data(),'Пул · проверка пространства')
        app.root.maxsize(3840,2160);app.root.geometry('1920x1080+0+0');app.nb.select(10)
        errors=[];checks=[];cases=iter([('before','lol',100)]+[(f'{theme}-{scale}',theme,scale) for theme in ('lol','lol_day') for scale in (100,125,150)])
        app.root.report_callback_exception=lambda et,ev,tb:fail(repr(ev))
        baseline=types.ModuleType('pool_before');baseline.__file__=str(Path('app/pool_ui.py').resolve())
        exec(compile(subprocess.check_output(['git','show','357680d0237ff2f016dc9a541981c88f9c1ba077:app/pool_ui.py'],text=True),baseline.__file__,'exec'),baseline.__dict__)
        current=None
        def fail(message):
            errors.append(message);finish()
        def finish():
            (OUT/'checks.json').write_text(json.dumps({'errors':errors,'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
            app.root.destroy()
        def advance():
            nonlocal current
            current=next(cases,None)
            if current is None:finish();return
            _,theme,scale=current
            app.s['theme']=theme;app.s['scale']=scale;app.rebuild();app.root.maxsize(3840,2160);app.root.geometry('1920x1080+0+0');app.nb.select(10)
            if current[0]=='before':
                app.pool_view.destroy();app.pool_view=baseline.PoolScreen(app.tab_pool,app)
            app.root.update_idletasks()
            view=app.pool_view
            view.resize(types.SimpleNamespace(width=view.cv.winfo_width()))
            app.root.after(500,capture)
        def capture():
            try:
                view=app.pool_view
                app.root.update_idletasks()
                if view.resize_job:
                    app.root.after(150,capture);return
                app.root.update_idletasks()
                cards=list(view.cards.values())
                full_rows=len({int(card.grid_info()['row']) for card in cards if card.winfo_y()+card.winfo_height()<=view.cv.winfo_height()})
                info={'case':current[0],'window':[app.root.winfo_width(),app.root.winfo_height()],
                      'viewport_height':view.cv.winfo_height(),'columns':view.columns,'full_rows':full_rows,
                      'card_height':cards[0].winfo_height()}
                assert info['window']==[1920,1080],('window manager constrained the test window',info)
                assert info['columns']>0,info
                checks.append(info)
                print(json.dumps(info),flush=True)
                user=ctypes.windll.user32;user.GetAncestor.argtypes=[ctypes.c_void_p,ctypes.c_uint];user.GetAncestor.restype=ctypes.c_void_p
                ImageGrab.grab(window=user.GetAncestor(app.root.winfo_id(),2)).save(OUT/(current[0]+'.png'))
                if current[0]!='before':
                    assert full_rows>=3,('fewer than three full rows',info)
                    if current[2]==100:assert full_rows>=5,info
                    if current[2]==100 and current[1]=='lol':
                        before=checks[0]
                        assert info['viewport_height']>before['viewport_height']+100,(before,info)
                    original=dict(view.cards);initial=app.current_pool()
                    view.cards['Ahri'].event_generate('<Button-1>');view.cards['Ahri'].event_generate('<Button-1>')
                    assert app.current_pool()==initial
                    view.toggle_advanced();view.toggle_advanced();view.choose_mode('pool');view.choose_mode('all')
                    assert all(view.cards[key] is card for key,card in original.items())
                app.root.after(100,advance)
            except Exception as error:fail(repr(error))
        app.root.after(500,advance);app.root.after(30000,lambda:fail('pool space timeout'))
        app.run()
        if errors or len(checks)!=7:raise SystemExit(str(errors))


if __name__=='__main__':main()
