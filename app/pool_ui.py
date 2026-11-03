"""Separate champion-pool screen: portraits toggle the pool for the chosen role."""
import tkinter as tk
from tkinter import ttk
from scroll_canvas import ScrollCanvas
import webbrowser
import core
from view_components import readable_palette
import champion_pool as model


class PoolScreen(tk.Frame):
    def __init__(self, parent, app):
        from ui import C,F
        super().__init__(parent,bg=C['bg'])
        self.app,self.c,self.f=app,readable_palette(C),F
        self.pack(fill='both',expand=True)
        self.rows,self.source=model.load_catalog(app.data)
        self.role='MIDDLE'
        self.mode='all';self.columns=0;self.cards={};self.job=None;self.old_columns=0
        self.query=tk.StringVar();self.sort=tk.StringVar(value='По имени');self.filters={};self.option_maps={}
        self.role_buttons={};self.mode_buttons={}
        self.info=self.label(self,'Нажми на портрет: добавить в пул или убрать из него.',10,'mute',wraplength=850,justify='left');self.info.pack(anchor='w',pady=(2,12))
        line=tk.Frame(self,bg=C['panel'],padx=12,pady=10);line.pack(fill='x')
        self.label(line,'ПУЛ ДЛЯ РОЛИ',9,'mute',bg=C['panel']).pack(anchor='w',pady=(0,6))
        buttons=tk.Frame(line,bg=C['panel']);buttons.pack(fill='x')
        for i,r in enumerate(core.ROLES):
            b=self.button(buttons,core.ROLE_RU[r].capitalize(),lambda r=r:self.choose_role(r))
            if r in app.icons.a.get('role',{}): b.configure(image=app.img('role',r,.5),compound='left')
            b.grid(row=0,column=i,sticky='ew',padx=(0,5));buttons.columnconfigure(i,weight=1)
            self.role_buttons[r]=b
        self.count=self.label(line,'',10,'gold',bg=C['panel']);self.count.pack(anchor='w',pady=(8,0))
        bar=tk.Frame(self,bg=C['bg']);bar.pack(fill='x',pady=(12,8))
        self.label(bar,'Поиск',9,'mute').grid(row=0,column=0,sticky='w')
        entry=ttk.Entry(bar,textvariable=self.query,font=(F['font'],app.fs(11)),width=20)
        entry.grid(row=1,column=0,sticky='ew',padx=(0,10),ipady=4);bar.columnconfigure(0,weight=1)
        self.combo(bar,'classes','Класс',1)
        bar.columnconfigure(1,weight=0)
        self.label(bar,'Порядок',9,'mute').grid(row=0,column=2,sticky='w')
        sort=ttk.Combobox(bar,textvariable=self.sort,font=(F['font'],app.fs(11)),values=['По имени','Сначала выбранные','Новые сначала'],state='readonly',width=19)
        sort.grid(row=1,column=2,sticky='ew',ipady=4);sort.bind('<<ComboboxSelected>>',lambda e:self.refresh())
        modes=tk.Frame(self,bg=C['bg']);modes.pack(fill='x',pady=(0,8))
        for name,key in [('Все чемпионы','all'),('Для этой роли','role'),('Только мой пул','pool')]:
            b=self.button(modes,name,lambda key=key:self.choose_mode(key));b.pack(side='left',padx=(0,5));self.mode_buttons[key]=b
        advrow=tk.Frame(self,bg=C['bg']);advrow.pack(fill='x')
        self.advanced_btn=self.button(advrow,'▸ Дополнительные фильтры',self.toggle_advanced);self.advanced_btn.pack(side='left')
        self.button(advrow,'Сбросить фильтры',self.reset).pack(side='right')
        self.advanced=tk.Frame(self,bg=C['panel'],padx=10,pady=8)
        for i,(key,name) in enumerate(model.FIELDS):self.combo(self.advanced,key,name,i%3,i//3*2)
        self.result=self.label(self,'',9,'mute');self.result.pack(fill='x',pady=(8,5))
        viewport=tk.Frame(self,bg=C['bg']);viewport.pack(fill='both',expand=True)
        self.cv=ScrollCanvas(viewport,bg=C['bg'],highlightthickness=0)
        sb=ttk.Scrollbar(viewport,orient='vertical',command=self.cv.yview);sb.pack(side='right',fill='y')
        self.cv.pack(side='left',fill='both',expand=True);self.cv.configure(yscrollcommand=sb.set)
        self.grid_box=tk.Frame(self.cv,bg=C['bg']);self.window=self.cv.create_window(0,0,window=self.grid_box,anchor='nw')
        self.grid_box.bind('<Configure>',lambda e:self.cv.configure(scrollregion=self.cv.bbox('all')))
        self.cv.bind('<Configure>',self.resize)
        self.bind('<Configure>',lambda e:self.info.configure(wraplength=max(200,e.width-8)) if e.widget is self else None)
        # Integrate with the application's existing wheel handler without binding globally again.
        app.canvases[str(parent)]=self.cv
        foot=tk.Frame(self,bg=C['bg']);self.footer=foot;foot.pack(fill='x',side='bottom',before=viewport,pady=(8,0))
        self.saved=self.label(foot,'Изменения сохраняются автоматически',9,'mute');self.saved.pack(anchor='w')
        source_date=self.source.get('snapshot_date','неизвестна')
        note=('Игровые фильтры: '+self.source['gameplay_snapshot_date']+' · лор: '+source_date if self.source.get('gameplay_snapshot_date') else 'Данные на основе вики · снимок '+source_date)+' · неизвестное не угадывается'
        source=self.label(foot,note,8,'mute',wraplength=780,justify='left',cursor='hand2');source.pack(anchor='w',pady=(4,0))
        source.bind('<Button-1>',lambda e:webbrowser.open(self.source.get('url','https://wiki.leagueoflegends.com/en-us/')))
        self.query.trace_add('write',lambda *_:self.search_changed())
        self.bind('<Destroy>',self.cleanup,add='+')
        self.refresh()

    def cleanup(self,event):
        if event.widget is self and self.job:
            self.after_cancel(self.job);self.job=None

    def label(self,parent,text,size=10,color='fg',head=False,**kw):
        return tk.Label(parent,text=text,bg=kw.pop('bg',self.c['bg']),fg=self.c[color],
                        font=(self.f['head'] if head else self.f['font'],self.app.fs(max(11,size))),**kw)

    def button(self,parent,text,command):
        return tk.Button(parent,text=text,command=command,bg=self.c['deep'],fg=self.c['mute'],
                         activebackground=self.c['raise'],activeforeground=self.c['gold'],relief='flat',bd=0,
                         highlightthickness=1,highlightbackground=self.c['line'],highlightcolor=self.c['gold'],
                         font=(self.f['font'],self.app.fs(11)),padx=self.app.fs(9),pady=self.app.fs(6),cursor='hand2')

    def combo(self,parent,key,title,column,row=0):
        var=tk.StringVar(value='Любой' if key not in ('classes','species','regions') else 'Все')
        empty=var.get();options=model.options(self.rows,key)
        mapping={empty:'', 'Нет данных':'?'}
        mapping.update({model.LABELS.get(v,v):v for v in options})
        self.filters[key]=var;self.option_maps[key]=mapping
        bg=parent.cget('bg')
        self.label(parent,title,9,'mute',bg=bg).grid(row=row,column=column,sticky='w')
        cb=ttk.Combobox(parent,textvariable=var,values=list(mapping),state='readonly',width=18,font=(self.f['font'],self.app.fs(11)))
        cb.grid(row=row+1,column=column,sticky='ew',padx=(0,10),pady=(0,5),ipady=4)
        parent.columnconfigure(column,weight=1)
        cb.bind('<<ComboboxSelected>>',lambda e:self.refresh())

    def pool(self):return self.app.current_pool()

    def choose_role(self,role):
        self.role=role;self.cv.yview_moveto(0);self.refresh()

    def choose_mode(self,mode):
        self.mode=mode;self.cv.yview_moveto(0);self.refresh()

    def toggle_advanced(self):
        if self.advanced.winfo_manager():self.advanced.pack_forget();prefix='▸'
        else:self.advanced.pack(fill='x',before=self.result,pady=(8,0));prefix='▾'
        self.advanced_btn.configure(text=prefix+' Дополнительные фильтры')

    def reset(self):
        for key,var in self.filters.items():var.set(next(iter(self.option_maps[key])))
        self.query.set('');self.mode='all';self.sort.set('По имени');self.refresh()

    def search_changed(self):
        if self.job:self.after_cancel(self.job)
        self.job=self.after(120,self.search_now)

    def search_now(self):
        self.job=None;self.cv.yview_moveto(0);self.refresh()

    def resize(self,event):
        self.cv.itemconfigure(self.window,width=event.width)
        cols=max(1,event.width//self.app.fs(148))
        if cols!=self.columns:self.columns=cols;self.refresh()

    def refresh(self):
        if not self.winfo_exists():return
        pool=self.pool();selected=set(pool.get(self.role,[]))
        profile=(self.app.data.d['players'].get(self.app.who or '') or {}).get('riot','Локальный профиль')
        self.count.configure(text=f'{profile}  ·  {len(selected)} в пуле: {core.ROLE_RU[self.role]}  ·  {len(set(c for xs in pool.values() for c in xs))} всего')
        for key,b in self.role_buttons.items():b.configure(bg=self.c['raise'] if key==self.role else self.c['deep'],fg=self.c['gold'] if key==self.role else self.c['fg'],highlightbackground=self.c['gold'] if key==self.role else self.c['line'])
        for key,b in self.mode_buttons.items():b.configure(bg=self.c['raise'] if key==self.mode else self.c['deep'],fg=self.c['gold'] if key==self.mode else self.c['fg'])
        active={key:self.option_maps[key].get(var.get(),'') for key,var in self.filters.items()}
        n=sum(bool(v) for k,v in active.items() if k!='classes')
        prefix='▾' if self.advanced.winfo_manager() else '▸'
        self.advanced_btn.configure(text=prefix+' Дополнительные фильтры'+(f' · {n}' if n else ''))
        sort={'По имени':'name','Сначала выбранные':'selected','Новые сначала':'year'}[self.sort.get()]
        self.visible=model.filtered(self.rows,pool,self.role,self.query.get(),self.mode,active,sort)
        self.result.configure(text=f'Найдено {len(self.visible)} из {len(self.rows)}  ·  поиск по русскому и английскому имени')
        for w in self.grid_box.winfo_children():w.destroy()
        self.cards={};cols=max(1,self.columns)
        for i in range(max(cols,self.old_columns)):
            self.grid_box.columnconfigure(i,weight=1 if i<cols else 0,uniform='champ' if i<cols else '',minsize=0)
        self.old_columns=cols
        if not self.visible:
            self.label(self.grid_box,'Ничего не найдено. Измени поиск или сбрось фильтры.',11,'mute',wraplength=450).grid(row=0,column=0,columnspan=cols,pady=45)
        for i,row in enumerate(self.visible):self.draw_card(row,selected,i//cols,i%cols)

    def draw_card(self,row,selected,y,x):
        champion=row['id'];on=champion in selected;c=self.c;fs=self.app.fs
        border=tk.Frame(self.grid_box,bg=c['gold'] if on else c['line'],padx=2,pady=2,takefocus=1,
                        highlightthickness=1,highlightbackground=c['bg'],highlightcolor=c['gold'],cursor='hand2')
        border.grid(row=y,column=x,sticky='nsew',padx=4,pady=4)
        inside=tk.Frame(border,bg=c['panel']);inside.pack(fill='both',expand=True)
        image=self.app.icons.get('champ',champion,fs(100)) if champion in self.app.icons.a.get('champ',{}) else None
        portrait=tk.Label(inside,image=image or '',text='' if image else 'Нет иконки',bg=c['panel'],fg=c['mute'],width=0 if image else 10)
        portrait.pack(padx=6,pady=(8,4))
        name=self.label(inside,row['name'],10,'gold' if on else 'fg',bg=c['panel'],wraplength=fs(132),height=2,justify='center');name.pack(fill='x')
        state=self.label(inside,'✓ В пуле' if on else 'Добавить',8,'gold' if on else 'mute',bg=c['panel']);state.pack(pady=(0,7))
        def toggle(event=None):
            on=champion in self.pool().get(self.role,[])
            try:self.app.toggle_pool(champion,self.role)
            except (OSError,ValueError) as error:
                self.saved.configure(text='Не удалось сохранить пул: '+str(error),fg=c['bad']);return 'break'
            self.saved.configure(text=('Добавлен: ' if not on else 'Убран: ')+row['name']+' · сохранено',fg=c['good'])
            self.refresh()
            if champion in self.cards:self.cards[champion].focus_set()
            return 'break'
        for w in (border,inside,portrait,name,state):w.bind('<Button-1>',toggle)
        border.bind('<Return>',toggle);border.bind('<space>',toggle)
        self.cards[champion]=border
