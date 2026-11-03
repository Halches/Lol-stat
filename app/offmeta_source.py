"""Bounded, asynchronous public-page loading with verified, dated factual cache."""
import json
import os
import threading
import time
import urllib.request
import offmeta_data

class OffmetaSource:
    def __init__(self,home,post,changed):
        self.home,self.post,self.changed=home,post,changed
        self.values={};self.states={};self.pending=set();self.attempts={};self.errors={}

    def get(self,champion,role):
        key=(champion,role);now=time.time()
        if key in self.values and now-self.attempts.get(key,0)<12*3600:return self.values[key]
        if key in self.pending or len(self.pending)>=4:return self.values.get(key)
        if self.states.get(key)=='fail' and now-self.attempts.get(key,0)<300:return self.values.get(key)
        self.pending.add(key);self.states[key]='loading';self.attempts[key]=now
        path=os.path.join(self.home,'offmeta',offmeta_data.slug(champion)+'_'+role+'.json')
        previous=self.values.get(key)
        def worker():
            saved=None;value=None;error=''
            try:
                try:
                    with open(path,encoding='utf-8') as f:stored=json.load(f)
                    saved=offmeta_data.parse_state(stored.get('payload'),champion,role)
                    stamp=stored.get('fetched_at')
                    if saved and type(stamp) in (int,float) and 0<stamp<=now:saved.update(fetched_at=stamp)
                    else:saved=None
                except (OSError,ValueError,TypeError,AttributeError):pass
                if saved and now-saved['fetched_at']<12*3600:value=saved
                else:
                    req=urllib.request.Request(offmeta_data.url(champion),headers={'User-Agent':'LoLHelper/1.0 (public build page)'})
                    with urllib.request.urlopen(req,timeout=20) as response:
                        raw=response.read(5*1024*1024+1)
                    if len(raw)>5*1024*1024:raise ValueError('Ответ слишком большой')
                    payload=offmeta_data.compact(offmeta_data.state(raw.decode('utf-8')))
                    value=offmeta_data.parse_state(payload,champion,role)
                    if not value:raise ValueError('Источник не подтвердил чемпиона, роль или состав сборки')
                    value['fetched_at']=time.time()
                    try:
                        os.makedirs(os.path.dirname(path),exist_ok=True)
                        with open(path+'.tmp','w',encoding='utf-8') as f:json.dump({'payload':payload,'fetched_at':value['fetched_at']},f)
                        os.replace(path+'.tmp',path)
                    except OSError:error='Не удалось сохранить сборку на диск'
            except Exception as exc:
                error=str(exc)
                if saved or previous:value=dict(saved or previous,stale=True)
            def done():
                self.pending.discard(key);self.states[key]='ok' if value else 'fail';self.errors[key]=error
                if value:self.values[key]=value
                self.changed(champion,role)
            try:self.post(0,done)
            except Exception:pass
        threading.Thread(target=worker,daemon=True,name='offmeta-build').start()
        return self.values.get(key)
