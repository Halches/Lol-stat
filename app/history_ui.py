"""Native history and match details. No network calls from rendering."""
import threading
import time
import tkinter as tk
from tkinter import ttk
from scroll_canvas import ScrollCanvas
import core
import history_model as model
from view_components import ReadableComponents as Components, readable_palette


class HistoryScreen(tk.Frame,Components):
    def __init__(self,parent,app):
        from ui import C,F
        super().__init__(parent,bg=C['bg']);self.app,self.c,self.f=app,readable_palette(C),F;self.pack(fill='both',expand=True)
        self.source='saved';self.client_rows=None;self.client_owner=None;self.client_name='';self.updated=None
        self.busy=False;self.generation=0;self.limit=20;self.message='';self.job=None;self.layout=None
        self.query=tk.StringVar();self.role=tk.StringVar(value='Все роли');self.queue=tk.StringVar(value='Все режимы');self.result='all'
        self.query_trace=self.query.trace_add('write',lambda *_:self.search_changed())
        self.bind('<Configure>',self.resized);self.bind('<Destroy>',self.cleanup,add='+');self.refresh()

    def cleanup(self,event):
        if event.widget is self:
            self.generation+=1
            self.query.trace_remove('write',self.query_trace)
            if self.job:self.after_cancel(self.job);self.job=None

    def resized(self,event):
        if event.widget is self and getattr(self,'last_width',None)!=event.width:
            if self.job:self.after_cancel(self.job)
            self.job=self.after(100,self.refresh_if_resized)

    def refresh_if_resized(self):
        self.job=None
        # Configure events can describe a temporary width while children are
        # being rebuilt. Recheck the settled geometry before rebuilding again.
        if self.winfo_exists() and self.winfo_width()>1 and self.winfo_width()!=self.last_width:
            self.refresh()

    def search_changed(self):
        self.limit=20
        if self.job:self.after_cancel(self.job)
        self.job=self.after(150,self.refresh)

    def profile_changed(self):
        self.source='saved';self.limit=20;self.refresh()

    def account_changed(self,account):
        pu=(account or {}).get('puuid')
        if self.client_owner and self.client_owner!=pu:
            self.generation+=1;self.busy=False;self.client_rows=None;self.client_owner=None;self.client_name='';self.updated=None
            self.message='Клиент этого профиля недоступен';self.refresh()

    def rows(self):
        if self.source=='client':return self.client_rows or []
        games=self.app.player.games if self.app.player else []
        return model.saved(games,self.app.data,self.app.who or 'local')

    def use_source(self,value):
        self.source=value;self.limit=20;self.queue.set('Все режимы');self.refresh()
        if value=='client' and self.client_rows is None:self.load_client()

    def load_client(self,background=False):
        if self.busy:return
        if not background:self.source='client'
        self.busy=True;self.generation+=1;token=self.generation;self.message='Загрузка истории из клиента…';self.refresh()
        def worker():
            me={};games=None;lp={};error=''
            try:
                me=self.app.client.me() or {};pu=me.get('puuid')
                if not pu:error='Клиент LoL недоступен. Показаны ранее загруженные матчи, если они есть.'
                else:
                    games=self.app.client.history(pu,30)
                    if games is None:error='Клиент не отдал историю. Предыдущая выборка сохранена.'
                    else:
                        try:
                            snapshots=self.app.lp_snaps(self.app.client.rank(pu),puuid=pu)
                            lp=core.lp_changes(games,snapshots)
                        except Exception:lp={}
            except Exception:error='Не удалось обновить историю. Предыдущая выборка сохранена.'
            def done():
                if not self.winfo_exists() or token!=self.generation:return
                self.busy=False
                current=(self.app.account or {}).get('puuid')
                if current and me.get('puuid') and current!=me['puuid']:
                    self.message='Аккаунт клиента изменился. Обнови историю ещё раз.';self.refresh();return
                if error:self.message=error;self.refresh();return
                self.set_client(games,lp,me.get('puuid'),me.get('riot','Игрок клиента'))
            try:self.app.root.after(0,done)
            except (RuntimeError,tk.TclError):pass
        threading.Thread(target=worker,daemon=True).start()

    def set_client(self,games,lp,puuid,name=''):
        self.client_rows=model.client(games,self.app.data,puuid,lp);self.client_owner=puuid;self.client_name=name or 'Игрок клиента'
        self.updated=time.time();self.message='История клиента обновлена';self.app.hist_data=games;self.refresh()

    def reset(self):
        self.query.set('');self.role.set('Все роли');self.queue.set('Все режимы');self.result='all';self.limit=20;self.refresh()

    def select_result(self,value):self.result=value;self.limit=20;self.refresh()
    def more(self):self.limit+=20;self.refresh()

    def refresh(self):
        if not self.winfo_exists():return
        if self.job:self.after_cancel(self.job);self.job=None
        focus=getattr(self,'search',None)
        editing=bool(focus and focus.winfo_exists() and focus.focus_get() is focus)
        cursor=focus.index(tk.INSERT) if editing else 0
        for child in self.winfo_children():child.destroy()
        app,d,c,fs=self.app,self.app.data,self.c,self.app.fs
        width=self.winfo_width() if self.winfo_width()>1 else max(fs(550),app.root.winfo_width()-fs(250))
        self.last_width=width;self.layout=width>=fs(1200)
        top=tk.Frame(self,bg=c['bg']);top.pack(fill='x')
        self.label(top,'Матчи и разбор',21,'gold',head=True).pack(side='left')
        self.button(top,'Сайт со статистикой',app.open_site).pack(side='right')
        sources=tk.Frame(self,bg=c['bg']);sources.pack(fill='x',pady=(8,8))
        for title,key in [('Сохранённые матчи','saved'),('Из клиента LoL','client')]:
            self.button(sources,title,lambda key=key:self.use_source(key),self.source==key).pack(side='left',padx=(0,6))
        update=self.button(sources,'Загрузка…' if self.busy else 'Обновить из клиента',self.load_client)
        update.pack(side='right');update.configure(state='disabled' if self.busy else 'normal')
        profile=(d.d['players'].get(app.who or '') or {}).get('riot','Профиль не выбран')
        source_name=profile if self.source=='saved' else self.client_name or 'Текущий аккаунт клиента'
        stamp=d.d.get('t','—') if self.source=='saved' else time.strftime('%d.%m %H:%M',time.localtime(self.updated)) if self.updated else 'ещё не загружено'
        self.label(self,f'{source_name} · '+('выгрузка от ' if self.source=='saved' else 'получено ')+stamp,10,'mute',wraplength=max(250,width-20),justify='left').pack(anchor='w',pady=(0,8))
        controls=self.panel(self,10);controls.pack(fill='x')
        self.label(controls,'ПОИСК ЧЕМПИОНА ИЛИ ОППОНЕНТА',8,'mute').grid(row=0,column=0,sticky='w')
        self.search=ttk.Entry(controls,textvariable=self.query,width=22,font=(self.f['font'],fs(12)))
        self.search.grid(row=1,column=0,sticky='ew',padx=(0,10),ipady=4);controls.columnconfigure(0,weight=1)
        role_map={'Все роли':'' ,**{core.ROLE_RU[r].capitalize():r for r in core.ROLES}}
        rows=self.rows();queues=sorted({r['queue'] for r in rows if type(r.get('queue')) is int})
        queue_map={'Все режимы':'',**{core.QUEUE_RU.get(q,f'Очередь {q}')+(f' ({q})' if sum(core.QUEUE_RU.get(x)==core.QUEUE_RU.get(q) for x in queues)>1 else ''):q for q in queues}}
        if self.queue.get() not in queue_map:self.queue.set('Все режимы')
        for i,(title,var,values) in enumerate([('РОЛЬ',self.role,role_map),('РЕЖИМ',self.queue,queue_map)],1):
            self.label(controls,title,8,'mute').grid(row=0,column=i,sticky='w')
            cb=ttk.Combobox(controls,textvariable=var,values=list(values),state='readonly',width=17,font=(self.f['font'],fs(11)))
            cb.grid(row=1,column=i,sticky='ew',padx=(0,6),ipady=4)
            cb.bind('<<ComboboxSelected>>',lambda e:(setattr(self,'limit',20),self.refresh()))
        filters=tk.Frame(self,bg=c['bg']);filters.pack(fill='x',pady=(8,8))
        for title,key in [('Все результаты','all'),('Победы','win'),('Поражения','loss')]:
            self.button(filters,title,lambda key=key:self.select_result(key),self.result==key).pack(side='left',padx=(0,5))
        self.button(filters,'Сбросить',self.reset).pack(side='right')
        selected=model.filtered(rows,d,self.query.get(),role_map.get(self.role.get(),''),queue_map[self.queue.get()],self.result)
        self.filtered=selected;s=model.stats(selected)
        totals=self.panel(self,10);totals.pack(fill='x',pady=(0,8))
        texts=[('МАТЧИ',str(s['n']),''),('ПОБЕДЫ',f"{s['wr']:.1f}%" if s['wr'] is not None else '—',f"Результат известен: {s['results']}"),('KDA',f"{s['kda']:.2f}" if s['kda'] is not None else '—',f"По {s['kda_n']} матчам"),('ФАРМ / МИН',f"{s['csm']:.1f}" if s['csm'] is not None else '—',f"По {s['csm_n']} матчам")]
        for i,(label,value,note) in enumerate(texts):
            box=tk.Frame(totals,bg=c['panel']);box.grid(row=0,column=i,sticky='w');totals.columnconfigure(i,weight=1,uniform='totals')
            self.label(box,label,8,'mute').pack(anchor='w');self.label(box,value.replace('.',','),28,'fg',num=True).pack(anchor='w')
            self.label(box,note or 'В текущем фильтре',8,'mute').pack(anchor='w')
        note='Нажми на матч для подробностей. LP показывается только при наличии снимков ранга до и после одиночной игры.'
        self.label(self,note,9,'mute',wraplength=max(250,width-20),justify='left').pack(anchor='w',pady=(0,8))
        if self.source=='client' and self.message:self.label(self,self.message,9,'gold' if not self.busy else 'mute',wraplength=max(250,width-20),justify='left').pack(anchor='w',pady=(0,6))
        self.label(self,f'Найдено {len(selected)} из {len(rows)} · показано {min(self.limit,len(selected))}',9,'mute').pack(anchor='w',pady=(0,6))
        self.list_box=tk.Frame(self,bg=c['bg']);self.list_box.pack(fill='x');self.row_widgets=[]
        for record in selected[:self.limit]:self.match_row(record,width)
        if not selected:
            empty=self.panel(self,24);empty.pack(fill='x')
            title='Матчей пока нет' if not rows else 'Ничего не найдено'
            self.label(empty,title,17,'fg',head=True).pack(anchor='w')
            self.label(empty,'Обнови историю из клиента или измени фильтры.',10,'mute').pack(anchor='w',pady=(6,0))
        if len(selected)>self.limit:self.button(self,'Показать ещё '+core.plural(min(20,len(selected)-self.limit),'матч','матча','матчей'),self.more).pack(anchor='w',pady=(10,6))
        if editing:self.search.focus_set();self.search.icursor(min(cursor,len(self.query.get())))

    def match_row(self,r,width):
        c,fs,d=self.c,self.app.fs,self.app.data
        row=self.panel(self.list_box,14);row.pack(fill='x',pady=(0,10));self.row_widgets.append(row)
        tone='good' if r['win'] is True else 'bad' if r['win'] is False else 'mute'
        tk.Frame(row,bg=c[tone],width=3).place(x=-fs(14),y=0,relheight=1)
        portrait=tk.Frame(row,bg=c['panel']);portrait.grid(row=0,column=0,rowspan=2,sticky='w',padx=(0,8))
        self.image(portrait,'champ',r['champion'],54)
        body=tk.Frame(row,bg=c['panel']);body.grid(row=0,column=1,rowspan=2,sticky='ew')
        head=tk.Frame(body,bg=c['panel']);head.pack(anchor='w');self.image(head,'role',r['role'],18)
        self.label(head,d.cn(r['champion']),12,'fg').pack(side='left')
        date=time.strftime('%d.%m %H:%M',time.localtime(r['timestamp'])) if r['timestamp'] else 'Дата недоступна'
        self.label(body,core.QUEUE_RU.get(r['queue'],f"Очередь {r['queue']}" if r['queue'] else 'Режим неизвестен')+' · '+date,8,'mute',wraplength=max(fs(170),width-fs(900) if self.layout else width-fs(360)),justify='left').pack(anchor='w',pady=(2,3))
        equipment=tk.Frame(row if self.layout else body,bg=c['panel'])
        if self.layout:
            equipment.grid(row=0,column=2,rowspan=2,sticky='w',padx=(12,18))
            self.label(equipment,'ЗАКЛИНАНИЯ · РУНА · ПРЕДМЕТЫ',7,'mute').pack(anchor='w',pady=(0,3))
        else:equipment.pack(anchor='w')
        items=tk.Frame(equipment,bg=c['panel']);items.pack(anchor='w')
        for spell in r['spells']:self.image(items,'spell',core.SPELL_KEY.get(spell,spell),19)
        if r['perk']:self.image(items,'rune',r['perk'],19)
        self.item_icons(items,r['items'],20)
        if self.layout:
            facts=tk.Frame(row,bg=c['panel']);facts.grid(row=0,column=3,rowspan=2,sticky='w',padx=(0,12))
            participation=f"Участие {r['kp']:.0f}%" if r['kp'] is not None else f"Урон {r['dmg']/1000:.1f}k" if r['dmg'] is not None else 'Участие —'
            self.label(facts,participation,9,'mute').pack(anchor='w')
            self.label(facts,f"Обзор {r['vsm']:.2f}/мин" if r['vsm'] is not None else 'Обзор —',8,'mute').pack(anchor='w')
        kd=tk.Frame(row,bg=c['panel']);kd.grid(row=0,column=4 if self.layout else 2,rowspan=2,sticky='e',padx=(8,12))
        self.label(kd,' / '.join(str(r[k]) if r[k] is not None else '—' for k in ('k','d','a')),19,'fg',num=True).pack(anchor='e')
        self.label(kd,f"{r['csm']:.1f} CS/мин" if r['csm'] is not None else 'Фарм —',8,'mute').pack(anchor='e')
        end=tk.Frame(row,bg=c['panel']);end.grid(row=0,column=5 if self.layout else 3,rowspan=2,sticky='e')
        self.label(end,'ПОБЕДА' if r['win'] is True else 'ПОРАЖЕНИЕ' if r['win'] is False else 'НЕТ РЕЗУЛЬТАТА',9,tone).pack(anchor='e')
        self.label(end,core.mmss(r['duration']) if r['duration'] is not None else 'Время —',9,'mute').pack(anchor='e')
        self.label(end,f"{r['lp']:+d} LP" if type(r['lp']) is int else 'LP —',9,'good' if (r['lp'] or 0)>0 else 'bad' if (r['lp'] or 0)<0 else 'mute').pack(anchor='e')
        row.columnconfigure(1,weight=1)
        if self.layout:row.columnconfigure(2,weight=2)
        def bind_all(widget):
            widget.configure(cursor='hand2');widget.bind('<Button-1>',lambda e:self.open_record(r))
            for child in widget.winfo_children():bind_all(child)
        bind_all(row);row.configure(takefocus=1);row.bind('<Return>',lambda e:self.open_record(r));row.bind('<space>',lambda e:self.open_record(r))

    def open_record(self,record):
        snapshot=self.app.data.d.get('match_details',{}).get(record.get('match_id'))
        review=model.saved_details(snapshot,record.get('profile'),record.get('match_id')) if record['source']=='saved' else None
        window=MatchWindow(self.app,record,review=review)
        self.last_window=window
        if record['source']=='client' and record.get('gid'):window.load()
        return window


class MatchWindow(tk.Toplevel,Components):
    def __init__(self,app,record,review=None):
        from ui import C,F
        super().__init__(app.root);self.app,self.record,self.c,self.f=app,record,readable_palette(C),F
        self.review=review;self.loading=record['source']=='client' and bool(record.get('gid')) and review is None;self.error='Идентификатор матча недоступен' if record['source']=='client' and not record.get('gid') and review is None else '';self.closed=False;self.layout=None;self.job=None;self.analysis_open=False;self.last_width=None
        self.title('LoL Helper · подробности матча');self.configure(bg=C['bg'])
        sw,sh=self.winfo_screenwidth(),self.winfo_screenheight()
        self.geometry(f'{min(app.fs(1260),sw-40)}x{min(app.fs(960),sh-60)}+20+20')
        self.minsize(min(app.fs(800),sw-40),min(app.fs(540),sh-60))
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Escape>',lambda e:self.close())
        self.bind('<Destroy>',self.cleanup,add='+')
        footer=tk.Frame(self,bg=C['bg']);footer.pack(side='bottom',fill='x',padx=14,pady=8)
        self.button(footer,'Закрыть',self.close).pack(side='right')
        self.cv=ScrollCanvas(self,bg=C['bg'],highlightthickness=0);sb=ttk.Scrollbar(self,orient='vertical',command=self.cv.yview)
        sb.pack(side='right',fill='y');self.cv.pack(fill='both',expand=True);self.cv.configure(yscrollcommand=sb.set)
        self.body=tk.Frame(self.cv,bg=C['bg'],padx=app.fs(14),pady=app.fs(12));self.win=self.cv.create_window(0,0,window=self.body,anchor='nw')
        self.body.bind('<Configure>',lambda e:self.cv.configure(scrollregion=self.cv.bbox('all')))
        self.cv.bind('<Configure>',self.resized, add='+')
        self.bind('<MouseWheel>',self.cv.wheel);self.bind('<Button-4>',self.cv.wheel);self.bind('<Button-5>',self.cv.wheel)
        self.render()

    def cleanup(self,event):
        if event.widget is self:
            self.closed=True
            if self.job:self.after_cancel(self.job);self.job=None

    def close(self):
        self.closed=True
        if self.job:self.after_cancel(self.job);self.job=None
        self.destroy()

    def scroll(self,units):self.cv.yview_scroll(units,'units');return 'break'
    def wheel(self,event):return self.scroll(-max(1,abs(event.delta)//120)*(1 if event.delta>0 else -1)) if event.delta else 'break'

    def resized(self,event):
        self.cv.itemconfigure(self.win,width=event.width)
        mode=event.width>=self.app.fs(850)
        if mode!=self.layout or event.width!=self.last_width:
            if self.job:self.after_cancel(self.job)
            self.job=self.after(80,self.render_if_resized)

    def render_if_resized(self):
        self.job=None
        if not self.closed and self.winfo_exists() and self.cv.winfo_width()>1 and self.cv.winfo_width()!=self.last_width:self.render()

    def load(self):
        record=dict(self.record)
        def worker():
            review=None;error=''
            try:
                game=self.app.client.game(record['gid'])
                if not game:error='Клиент не отдал подробности этой игры.'
                elif str(game.get('gameId'))!=str(record['gid']):error='Клиент вернул другую игру. Подробности не показаны.'
                else:
                    review=model.details(game,record.get('owner'),self.app.data)
                    if not review:error='В ответе клиента нет состава матча.'
            except Exception:error='Не удалось получить подробности матча.'
            def done():
                if self.closed or not self.winfo_exists():return
                self.review,self.error,self.loading=review,error,False;self.render()
            try:self.app.root.after(0,done)
            except (RuntimeError,tk.TclError):pass
        threading.Thread(target=worker,daemon=True).start()

    def render(self):
        if self.closed or not self.winfo_exists():return
        if self.job:self.after_cancel(self.job);self.job=None
        for child in self.body.winfo_children():child.destroy()
        app,r,c,fs=self.app,dict(self.record),self.c,self.app.fs
        focus=(self.review or {}).get('me')
        if focus:
            r['champion']=focus.get('c') or r['champion'];r['role']=focus.get('pos') or r['role']
            for key in ('k','d','a','win'):
                if focus.get(key) is not None:r[key]=focus[key]
            if (self.review or {}).get('min'):r['duration']=round(self.review['min']*60)
            if focus.get('items') and all(item is not None for item in focus['items']):r['items']=focus['items']
        width=self.cv.winfo_width() if self.cv.winfo_width()>1 else app.fs(1200)
        self.layout=width>=fs(850);self.last_width=width
        head=self.panel(self.body,14);head.pack(fill='x')
        left=tk.Frame(head,bg=c['panel']);left.pack(side='left');self.image(left,'champ',r['champion'],62)
        text=tk.Frame(left,bg=c['panel']);text.pack(side='left')
        tone='good' if r['win'] is True else 'bad' if r['win'] is False else 'mute'
        self.label(text,'ПОБЕДА' if r['win'] is True else 'ПОРАЖЕНИЕ' if r['win'] is False else 'РЕЗУЛЬТАТ НЕИЗВЕСТЕН',10,tone).pack(anchor='w')
        self.label(text,app.data.cn(r['champion']),22,'gold',head=True).pack(anchor='w')
        self.label(text,core.ROLE_RU.get(r['role'],'Роль неизвестна')+' · '+core.QUEUE_RU.get(r['queue'],'Режим неизвестен'),9,'mute').pack(anchor='w')
        right=tk.Frame(head,bg=c['panel']);right.pack(side='right')
        self.label(right,' / '.join(str(r[k]) if r[k] is not None else '—' for k in ('k','d','a')),22,'fg',num=True).pack(anchor='e')
        self.label(right,core.mmss(r['duration']) if r['duration'] is not None else 'Время неизвестно',10,'mute').pack(anchor='e')
        self.label(right,f"{r['lp']:+d} LP" if type(r['lp']) is int else 'Изменение LP недоступно',9,'gold').pack(anchor='e')
        equipment=self.panel(self.body,10);equipment.pack(fill='x',pady=(8,0))
        self.label(equipment,'Заклинания · ключевая руна · предметы',11,'mute').pack(anchor='w',pady=(0,8))
        icons=tk.Frame(equipment,bg=c['panel']);icons.pack(anchor='w')
        for spell in r['spells']:self.image(icons,'spell',core.SPELL_KEY.get(spell,spell),24)
        if r['perk']:self.image(icons,'rune',r['perk'],24)
        self.item_icons(icons,r['items'],26)
        if self.loading:self.label(self.body,'Загружаю состав и разбор из клиента…',11,'mute').pack(anchor='w',pady=18);return
        if self.error:
            self.metrics(self.body,None)
            self.label(self.body,self.error,11,'mute',wraplength=max(300,width-fs(70)),justify='left').pack(anchor='w',pady=18);return
        if not self.review:
            self.label(self.body,'В сохранённой записи нет полного состава. Доступные показатели этой игры:',11,'mute',wraplength=max(300,width-fs(70)),justify='left').pack(anchor='w',pady=(14,8))
            self.metrics(self.body,None);return
        review=self.review;focus=review.get('me')
        self.metrics(self.body,focus)
        lines=review.get('lines') or []
        if lines:
            self.button(self.body,('▾' if self.analysis_open else '▸')+' Разбор матча',self.toggle_analysis).pack(anchor='w',pady=(12,6))
            if self.analysis_open:
                import player_comments
                order={'good':0,'fg':1,'gold':1,'bad':2}
                for text,color in sorted(lines,key=lambda line:order.get(line[1],1)):
                    text=text.removeprefix('Хорошо: ').removeprefix('Плохо: ')
                    tone='good' if color=='good' else 'bad' if color=='bad' else 'neutral'
                    bg,fg=player_comments.palette(c['dark'])[tone]
                    box=self.panel(self.body,8);box.configure(bg=bg);box.pack(fill='x',pady=(0,4))
                    label=self.label(box,text,10,'fg',wraplength=max(300,width-fs(70)),justify='left');label.configure(fg=fg);label.pack(anchor='w')
        elif not review.get('analysis_available'):
            note='Состав из сохранённого архива. Автоматический разбор для этой записи не сохранён.' if review.get('source')=='saved' else 'Для этой игры короткий разбор недоступен: недостаточно данных или другой режим.'
            self.label(self.body,note,9,'mute',wraplength=max(300,width-fs(70)),justify='left').pack(anchor='w',pady=(12,4))
        rows=review.get('rows') or [];participants_only=review.get('team_grouping')=='participants'
        teams=[None] if participants_only else list(dict.fromkeys(p['team'] for p in rows))
        if not participants_only and focus and focus['team'] in teams:teams.remove(focus['team']);teams.insert(0,focus['team'])
        columns=2 if self.layout else 1
        self.player_cards=[]
        for offset in range(0,len(teams),columns):
            group=tk.Frame(self.body,bg=c['bg']);group.pack(fill='x',pady=(12,0))
            for col,team in enumerate(teams[offset:offset+columns]):
                ours=not participants_only and bool(focus) and focus['team']==team
                own_player=ours and bool(r.get('owner')) and r.get('owner')==(app.account or {}).get('puuid')
                title='Участники матча' if participants_only else 'Твоя команда' if own_player else 'Команда игрока' if ours else 'Противники' if len(teams)==2 and focus else f'Команда {offset+col+1}'
                group_rows=sorted([p for p in rows if participants_only or p['team']==team],key=lambda p:core.ROLES.index(p['pos']) if p['pos'] in core.ROLES else len(core.ROLES))
                self.label(group,title+f' · {len(group_rows)} игроков',13,'mute' if participants_only else 'blue' if ours else 'red',head=True).grid(row=0,column=col,sticky='w',pady=(0,6))
                for i,p in enumerate(group_rows):self.player(group,p,i+1,col,review.get('min'))
                group.columnconfigure(col,weight=1,uniform='teams')

    def toggle_analysis(self):
        self.analysis_open=not self.analysis_open;self.render()

    def metrics(self,parent,focus):
        r=self.record;mins=(self.review or {}).get('min');source=focus or r
        csm=model.ratio(source.get('cs'),mins*60) if focus and mins else r.get('csm')
        vision=model.ratio(source.get('vis'),mins*60) if focus and mins else r.get('vsm')
        values=[('ФАРМ / МИН',f'{csm:.1f}' if csm is not None else '—'),('УРОН ЧЕМПИОНАМ',f"{source['dmg']:,}".replace(',',' ') if source.get('dmg') is not None else '—'),
                ('ОБЗОР / МИН',f'{vision:.2f}' if vision is not None else '—'),('ЗОЛОТО',f"{source['gold']:,}".replace(',',' ') if source.get('gold') is not None else '—')]
        row=tk.Frame(parent,bg=self.c['bg']);row.pack(fill='x',pady=(8,0))
        for i,(title,value) in enumerate(values):
            box=self.panel(row,9);box.grid(row=0,column=i,sticky='nsew',padx=(0,5));row.columnconfigure(i,weight=1,uniform='metrics')
            self.label(box,title,8,'mute').pack(anchor='w');self.label(box,value,24,'fg',num=True).pack(anchor='w',pady=(3,0))

    def player(self,parent,p,row,column,mins):
        app,c,fs=self.app,self.c,self.app.fs
        box=self.panel(parent,8);box.grid(row=row,column=column,sticky='nsew',padx=(0,5),pady=(0,5))
        if p['me']:box.configure(highlightbackground=c['gold'])
        self.player_cards.append(box);parent.rowconfigure(row,weight=1,uniform='player')
        stats=tk.Frame(box,bg=c['panel'])
        compact=self.last_width<fs(1150) if self.layout else self.last_width<fs(580)
        if compact:stats.pack(side='bottom',anchor='e',pady=(fs(7),0))
        else:stats.pack(side='right',padx=(fs(12),0))
        values=[('K / D / A',' / '.join(str(p[k]) if p.get(k) is not None else '—' for k in ('k','d','a'))),
                ('Золото',f"{p['gold']:,}".replace(',',' ') if p.get('gold') is not None else '—'),
                ('Урон чемпионам',f"{p['dmg']:,}".replace(',',' ') if p.get('dmg') is not None else '—')]
        for i,(title,value) in enumerate(values):
            metric=tk.Frame(stats,bg=c['deep'],width=fs(108),height=fs(96),padx=fs(5),pady=fs(7),highlightthickness=1,highlightbackground=c['line'])
            metric.pack_propagate(False)
            metric.grid(row=0,column=i,sticky='nsew',padx=(fs(4),0))
            self.label(metric,value,14 if len(value)>11 else 17,'gold' if i==1 else 'fg',num=True,pady=0,anchor='center').pack(fill='x')
            self.label(metric,title,9,'fg',pady=0,anchor='center',height=2,wraplength=fs(85),justify='center').pack(fill='x',pady=(fs(3),0))
        content=tk.Frame(box,bg=c['panel']);content.pack(side='left',fill='both',expand=True)
        line=tk.Frame(content,bg=c['panel']);line.pack(fill='x')
        self.image(line,'champ',p['c'],42);self.image(line,'role',p['pos'],18)
        text=tk.Frame(line,bg=c['panel']);text.pack(side='left',fill='x',expand=True)
        self.label(text,app.data.cn(p['c'])+(' · ты' if p['me'] and self.record.get('owner') and self.record.get('owner')==(app.account or {}).get('puuid') else ' · выбранный' if p['me'] else ''),10,'gold' if p['me'] else 'fg').pack(anchor='w')
        self.label(text,p.get('name') or 'Имя недоступно',8,'mute',wraplength=fs(160),justify='left').pack(anchor='w')
        items=tk.Frame(content,bg=c['panel']);items.pack(anchor='w',pady=(4,2));self.item_icons(items,p.get('items') or [],19)
        cs=f"{p['cs']} CS"+(f" · {p['cs']/mins:.1f}/мин" if mins else '') if p.get('cs') is not None else 'CS —'
        vision=f"обзор {p['vis']}" if p.get('vis') is not None else 'обзор —'
        self.label(content,' · '.join((cs,vision)),8,'mute',wraplength=fs(230),justify='left').pack(anchor='w')
