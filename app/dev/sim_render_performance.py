"""Repeat actual overlay updates without a game, network or user settings."""
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
    with tempfile.TemporaryDirectory(prefix='lol-render-check-') as folder:
        ui.app_home=lambda:folder
        Path(folder,'settings.json').write_text(json.dumps({'design3':True,'dashboard':False,'sound':'off'}),encoding='utf-8')
        for name in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon','sync_phone'):
            setattr(ui.App,name,lambda *a,**k:None)
        ui.Voice.warm=lambda *a:None
        lcu.LCU.image=lambda *a:None
        app=ui.App(lolhelper.load_data(),'RENDER PERFORMANCE')
        errors=[];report={};resources=[]
        app.root.report_callback_exception=lambda et,ev,tb:errors.append(repr(ev))
        def run():
            try:
                for key,overlay in dict(app.ov,**app.tab).items():
                    overlay.demo();photo=overlay._ph
                    times=[]
                    for _ in range(20):
                        start=time.perf_counter()
                        if key=='hints':overlay.show()
                        else:overlay.demo()
                        times.append((time.perf_counter()-start)*1000)
                        assert overlay._ph is photo,key+' recreated an unchanged Tk image'
                    report[key]={'median_ms':round(statistics.median(times),3),'max_ms':round(max(times),3),'same_tk_image':True}
                for theme in ('lol_day','lol'):
                    app.s['theme']=theme;app.rebuild();app.root.update_idletasks()
                    resources.append({'theme':theme,'canvases':len(app.canvases),'retained_images':len(app._imgs)})
                    assert len(app.canvases)==11,'destroyed canvases accumulated'
                    assert len(app._imgs)==1,'old images accumulated'
                    assert all(canvas.winfo_exists() for canvas in app.canvases.values())
            except Exception as error:errors.append(repr(error))
            finally:app.root.destroy()
        app.root.after(600,run)
        app.run()
        result={'platform':sys.platform,'overlays':report,'rebuild_resources':resources,'errors':errors}
        path=Path(os.environ.get('RENDER_PERF_OUT','/tmp/render-performance.json'))
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False))
        if errors or len(report)!=8:raise SystemExit(1)


if __name__=='__main__':main()
