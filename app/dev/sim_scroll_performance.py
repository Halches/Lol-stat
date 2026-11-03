"""Offline scroll timing on the real home screen; no game, network or user settings."""
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tkinter as tk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lcu
import lolhelper
import ui
from history_ui import HistoryScreen


def main():
    with tempfile.TemporaryDirectory(prefix='lol-scroll-timing-') as settings:
        ui.app_home=lambda:settings
        for method in ('poll','load_lanes','load_changelog','hist_refresh','check_updates','ensure_home_icon','sync_phone'):
            setattr(ui.App,method,lambda *a,**k:None)
        ui.Voice.warm=lambda *a:None
        lcu.LCU.image=lambda *a:None
        rebuilds={'history':0}
        original_refresh=HistoryScreen.refresh
        def count_refresh(view):
            rebuilds['history']+=1
            return original_refresh(view)
        HistoryScreen.refresh=count_refresh
        app=ui.App(lolhelper.load_data(),'SCROLL TIMING')
        app.root.geometry('1060x740+0+0');app.nb.select(0)
        errors=[];results={};samples=[];mode=0;step=0;last=None;render_start=0
        app.root.report_callback_exception=lambda et,ev,tb:errors.append(str(ev))
        canvas=app.canvases[app.nb.select()]
        names=['canvas_native','window_position']
        def advance():
            nonlocal mode,step,last,render_start
            if step==0:render_start=rebuilds['history']
            now=time.perf_counter()
            if last is not None:samples.append((now-last)*1000)
            if step>=80:
                ordered=sorted(samples)
                results[names[mode]]={'frames':len(samples),'interval_median_ms':round(statistics.median(samples),2),
                    'interval_p95_ms':round(ordered[math.ceil(len(ordered)*.95)-1],2),'interval_max_ms':round(max(samples),2),
                    'history_rebuilds':rebuilds['history']-render_start}
                if rebuilds['history']!=render_start:errors.append('History rebuilt while only scrolling home')
                canvas.yview_moveto(0);tk.Canvas.yview_moveto(canvas,0)
                mode+=1;step=0;last=None;samples.clear()
                if mode==2:
                    app.root.destroy();return
                app.root.after(200,advance);return
            fraction=(step%40)/39
            if (step//40)%2:fraction=1-fraction
            if mode==0:
                tk.Canvas.configure(canvas,scrollregion=canvas.bbox('all'))
                tk.Canvas.yview_moveto(canvas,fraction)
            else:canvas.yview_moveto(fraction)
            step+=1;last=now;app.root.after(16,advance)
        app.root.after(600,advance)
        app.root.after(30000,lambda:(errors.append('timing timeout'),app.root.destroy()))
        app.run()
        HistoryScreen.refresh=original_refresh
        report={'platform':sys.platform,'window':[1060,740],'results':results,'errors':errors,
            'note':'Synthetic scrolling of real home UI. Not a live game or proof for every Windows PC.'}
        output=Path(os.environ.get('SCROLL_PERF_OUT','/tmp/scroll-performance.json'))
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
        if errors or len(results)!=2:raise SystemExit(1)


if __name__=='__main__':main()
