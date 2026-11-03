"""Small, local-only UI latency log for the development review build."""
import json
from pathlib import Path
import time
import tkinter as tk


class LatencyLog:
    def __init__(self, root, path):
        self.root, self.path = root, Path(path)
        self.started = time.perf_counter()
        self.last = self.started
        self.samples = self.max_gap_ms = 0
        self.gaps = []
        self.callbacks = []
        self.closed = False
        self.original = tk.CallWrapper.__call__
        original = self.original
        def timed(wrapper, *args):
            start = time.perf_counter()
            try:
                return original(wrapper, *args)
            finally:
                duration = (time.perf_counter()-start)*1000
                if duration >= 50:
                    func = wrapper.func
                    for _ in range(5):
                        code=getattr(func,'__code__',None)
                        if not code or code.co_name!='callit':break
                        cells=dict(zip(code.co_freevars,func.__closure__ or ()))
                        if 'func' not in cells:break
                        func=cells['func'].cell_contents
                    self.callbacks.append({'callback':getattr(func,'__qualname__',type(func).__name__),
                        'duration_ms':round(duration,1),'at_s':round(start-self.started,1)})
                    self.callbacks = sorted(self.callbacks,key=lambda v:v['duration_ms'],reverse=True)[:30]
        self.timed = timed
        tk.CallWrapper.__call__ = timed
        self.job = root.after(50,self.tick)
        self.save_job = root.after(5000,self.save)

    def tick(self):
        if self.closed:return
        now = time.perf_counter();gap = (now-self.last)*1000;self.last = now
        self.samples += 1;self.max_gap_ms = max(self.max_gap_ms,gap)
        if gap >= 150:
            self.gaps.append({'gap_ms':round(gap,1),'at_s':round(now-self.started,1)})
            self.gaps = sorted(self.gaps,key=lambda v:v['gap_ms'],reverse=True)[:30]
        self.job = self.root.after(50,self.tick)

    def save(self):
        data = {'build':'widgets-v4','elapsed_s':round(time.perf_counter()-self.started,1),
            'heartbeat_interval_ms':50,'samples':self.samples,'max_gap_ms':round(self.max_gap_ms,1),
            'long_gaps':self.gaps,'slow_callbacks':self.callbacks}
        try:self.path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError:pass
        if not self.closed:self.save_job = self.root.after(5000,self.save)

    def close(self):
        self.closed = True
        if tk.CallWrapper.__call__ is self.timed:tk.CallWrapper.__call__ = self.original
        for job in (self.job,self.save_job):self.root.after_cancel(job)
        self.save()
