"""Public player builds, loaded in background; progress and cache retain per-build dates."""
import copy
import json
import os
import threading
import time
import urllib.request
import offmeta_data
import player_builds

class PlayerBuildSource:
    def __init__(self,home,post,changed):
        self.home,self.post,self.changed=home,post,changed
        self.values={};self.states={};self.pending=set();self.attempts={};self.errors={}

    @staticmethod
    def read(url):
        req=urllib.request.Request(url,headers={'User-Agent':'LoLHelper/1.0 (public build page)'})
        with urllib.request.urlopen(req,timeout=15) as response:raw=response.read(5*1024*1024+1)
        if len(raw)>5*1024*1024:raise ValueError('Ответ слишком большой')
        return player_builds.compact(offmeta_data.state(raw.decode('utf-8')))

    def emit(self,key,value,done=False,error=''):
        snapshot=copy.deepcopy(value)
        def apply():
            if done:self.pending.discard(key)
            self.states[key]='ok' if done and snapshot else 'fail' if done else 'loading'
            self.errors[key]=error
            if snapshot:self.values[key]=snapshot
            self.changed(*key)
        try:self.post(0,apply)
        except Exception:pass

    def get(self,champion,role):
        key=(champion,role);now=time.time();old=self.values.get(key)
        ttl=300 if old and old.get('partial') else 12*3600
        if old and now-self.attempts.get(key,0)<ttl:return old
        if key in self.pending or len(self.pending)>=2:return old
        if self.states.get(key)=='fail' and now-self.attempts.get(key,0)<300:return old
        self.pending.add(key);self.attempts[key]=now;self.states[key]='loading'
        path=os.path.join(self.home,'players',offmeta_data.slug(champion)+'_'+role+'.json')
        def worker():
            saved={};packet=None;error=''
            try:
                try:
                    with open(path,encoding='utf-8') as f:saved=json.load(f)
                    if not isinstance(saved,dict):saved={}
                except (OSError,ValueError):pass
                stamp=saved.get('fetched_at');index=saved.get('index');packet=player_builds.listing(index,champion,role)
                index_ttl=300 if saved.get('partial') else 12*3600
                fresh=packet and type(stamp) in (int,float) and 0<stamp<=now and now-stamp<index_ttl
                if not fresh:
                    index=self.read(offmeta_data.url(champion));packet=player_builds.listing(index,champion,role);stamp=time.time()
                if not packet:raise ValueError('Источник не подтвердил чемпиона и роль')
                packet.update(fetched_at=stamp,partial=True)
                pages=saved.get('pages') if isinstance(saved.get('pages'),dict) else {}
                dates=saved.get('dates') if isinstance(saved.get('dates'),dict) else {}
                # Keep verified prior loadouts visible while updating this same patch/player.
                for kind in packet['groups']:
                    for i,row in enumerate(packet['groups'][kind]):
                        cached=player_builds.detail(pages.get(row['id']),row);date=dates.get(row['id'])
                        if cached and type(date) in (int,float) and 0<date<=now:
                            cached.update(fetched_at=date,stale=now-date>=12*3600);packet['groups'][kind][i]=cached
                self.emit(key,packet)
                for kind in ('OTP','Pro'):
                    for i,row in enumerate(packet['groups'][kind]):
                        bid=row['id'];date=dates.get(bid);cached=player_builds.detail(pages.get(bid),row)
                        recent=cached and type(date) in (int,float) and 0<date<=now and now-date<12*3600
                        try:
                            if not recent:
                                page=self.read(row['source_url']);resolved=player_builds.detail(page,row)
                                if not resolved:raise ValueError('Не подтверждена полная сборка '+row['name'])
                                pages[bid]=page;dates[bid]=time.time()
                            else:resolved=cached
                            resolved['fetched_at']=dates[bid];packet['groups'][kind][i]=resolved
                        except Exception as exc:
                            error=str(exc)
                            if cached:
                                cached.update(fetched_at=date,stale=True);packet['groups'][kind][i]=cached
                            else:row['error']=True
                        self.emit(key,packet)
                packet['partial']=any(not row.get('variant') or row.get('stale') for group in packet['groups'].values() for row in group)
                # Only keep the up-to-six requested records, not other players on the page.
                wanted={row['id'] for group in packet['groups'].values() for row in group}
                try:
                    os.makedirs(os.path.dirname(path),exist_ok=True)
                    with open(path+'.tmp','w',encoding='utf-8') as f:json.dump({'index':index,'pages':{bid:page for bid,page in pages.items() if bid in wanted},'dates':{bid:date for bid,date in dates.items() if bid in wanted},'fetched_at':stamp,'partial':packet['partial']},f)
                    os.replace(path+'.tmp',path)
                except OSError:error='Не удалось сохранить сборки на диск'
            except Exception as exc:
                error=str(exc)
                if old:packet=copy.deepcopy(old);packet.update(stale=True,partial=True)
                elif saved:
                    packet=player_builds.listing(saved.get('index'),champion,role)
                    if packet:
                        packet.update(fetched_at=saved.get('fetched_at'),stale=True,partial=True)
                        for kind in packet['groups']:
                            for i,row in enumerate(packet['groups'][kind]):
                                resolved=player_builds.detail((saved.get('pages') or {}).get(row['id']),row)
                                if resolved:resolved.update(fetched_at=(saved.get('dates') or {}).get(row['id']),stale=True);packet['groups'][kind][i]=resolved
            self.emit(key,packet,done=True,error=error)
        threading.Thread(target=worker,daemon=True,name='player-builds').start()
        return old
