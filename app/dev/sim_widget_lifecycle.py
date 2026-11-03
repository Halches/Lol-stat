"""Actual gallery and overlay lifecycle, offline and with isolated settings."""
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lcu
import lolhelper
import ui


def main():
    with tempfile.TemporaryDirectory(prefix='lol-widget-check-') as folder:
        ui.app_home=lambda:folder
        Path(folder,'settings.json').write_text(json.dumps({'design3':True,'dashboard':False,'sound':'off',
            'widgets':dict.fromkeys(ui.WIDGETS,False),'scoreboard':True}),encoding='utf-8')
        for name in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon','sync_phone'):
            setattr(ui.App,name,lambda *a,**k:None)
        ui.Voice.warm=lambda *a:None
        lcu.LCU.image=lambda *a:None
        app=ui.App(lolhelper.load_data(),'WIDGET CHECK')
        app.root.geometry('1060x840+0+0');app.nb.select(4)
        view=app.windows_view;tab=app.tab['tab'];errors=[];checks=[];timings=[];polls=[]
        app.root.report_callback_exception=lambda et,ev,tb:fail(repr(ev))
        def fail(message):
            errors.append(message)
            app.root.destroy()
        def step(func):
            def run():
                try:func()
                except Exception as error:fail(repr(error))
            return run
        def start():
            cards=dict(view.cards);photos=dict(view.photos)
            for _ in range(10):
                before=time.perf_counter();view.toggles['timers'].invoke();timings.append((time.perf_counter()-before)*1000)
                assert all(view.cards[key] is value for key,value in cards.items())
                assert all(view.photos[key] is value for key,value in photos.items())
            checks.append('toggle preserves cards and thumbnails')
            app.toggle_demo();app.root.after(200,step(stop))
        def stop():
            assert tab.winfo_viewable(),'placement did not show Tab'
            app.stop_demo()
            assert not tab.winfo_viewable(),'Tab survived placement stop'
            app.root.after(100,step(restart))
        def restart():
            assert not tab.winfo_viewable(),'queued preview reopened Tab after stop'
            checks.append('stop hides Tab and cancels queued previews')
            app.toggle_demo();app.root.after(200,step(inject_failure))
        def inject_failure():
            assert tab.winfo_viewable()
            original=tab.auto_tick
            def sometimes_fails(active,game):
                polls.append(time.perf_counter())
                if len(polls)==1:raise RuntimeError('intentional widget lifecycle test')
                return original(active,game)
            tab.auto_tick=sometimes_fails
            app.root.after(250,step(recovered))
        def recovered():
            assert len(polls)>=2,'hotkey polling stopped after an exception'
            assert not app.demo_on and not tab.winfo_viewable(),'error left Tab visible'
            checks.append('hotkey polling survives an error and hides Tab')
            app.root.destroy()
        app.root.after(600,step(start))
        app.root.after(15000,lambda:fail('widget check timeout'))
        app.run()
        report={'platform':sys.platform,'errors':errors,'checks':checks,
            'toggle_median_ms':round(statistics.median(timings),2) if timings else None,
            'toggle_max_ms':round(max(timings),2) if timings else None}
        out=Path(os.environ.get('WIDGET_CHECKS_OUT','/tmp/widget-checks.json'))
        out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
        if errors or len(checks)!=3:raise SystemExit(1)


if __name__=='__main__':main()
