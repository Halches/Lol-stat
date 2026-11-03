"""Native hint settings; existing trigger catalogue, per-role modes and custom texts."""
import tkinter as tk
from tkinter import ttk
import core
import champion_pool
from view_components import Components

# Короткая строка для просмотра списка; точные условия остаются в раскрытии.
SUMMARIES = {
    'scout': 'Личная история против этого чемпиона на выбранной роли.',
    'jungler': 'Оценка стиля лесника по чемпиону — в начале игры.',
    'trinket': 'Напомнить о тотеме, если его слот пуст в начале игры.',
    'early_ward': 'Совет по первому варду для твоей роли.',
    'crab': 'За 25 секунд до краба — сравнение соседних линий.',
    'gank1': 'Ранний выход: ориентир 2:50–3:20, ганк возможен раньше.',
    'gank2': 'После зачистки: ориентир 3:20–4:00, маршрут неизвестен.',
    'gank3': 'Оценка по прошлым играм лесника или его чемпиону.',
    'jg_path': 'Маршруты из прошлых игр, а не текущая позиция лесника.',
    'jg_seen': 'Лесник участвовал в убийстве — проверь миникарту.',
    'cs_norm': 'На 5, 10 и 15 минуте — сравнение с твоей нормой фарма.',
    'lane_gold': 'Разница стоимости предметов на линии — от 900 золота.',
    'levels': 'Кто первым получил 2-й или 3-й уровень на линии.',
    'skills': 'Что прокачать на текущем уровне по выбранной сборке.',
    'bench': 'На 10 и 15 минуте — фарм и доступные показатели линии.',
    'early_deaths': 'После двух смертей до 14-й минуты — играть осторожнее.',
    'base': 'От 1300 золота — оценить возможность вернуться на базу.',
    'hoard': 'Напомнить о покупке, если накопилось 2000 золота.',
    'tp': 'Перед драконом проверить телепорт; готовность неизвестна.',
    'cannon': 'Появление осадной волны на базе — только до 14:00.',
    'control': 'После покупки — проверить контрольный тотем, деньги и место.',
    'lens': 'Предмет поддержки даёт варды — можно проверить линзу.',
    'vision': 'На 10 и 20 минуте — сравнение обзора с твоей целью.',
    'enemy_dmg': 'Оценка по предметам врагов, а не измерение их урона.',
    'enemy_item': 'Сообщить, когда оппонент закончил предмет.',
    'next_item': 'Следующая покупка по твоим успешным играм на чемпионе.',
    'objectives': 'Предупредить об объектах за 60 и 30 секунд.',
    'fight_won': 'Перевес недавних убийств — повод оценить доступные объекты.',
    'team_gold': 'От 3000 преимущества по стоимости предметов команды.',
    'side_lane': 'На 15–25 минуте при преимуществе — вард перед сплитом.',
    'baron_jungle': 'За 30 секунд до Барона — осторожнее в лесу.',
    'inhib': 'Предупредить за минуту до восстановления ингибитора.',
    'powerspike': 'Ключевые уровни и законченные предметы на линии.',
    'postgame': 'После матча — выполненные цели и главная ошибка.',
}
SHORT_TITLES = {
    'scout': 'История против оппонента', 'jungler': 'Стиль вражеского лесника',
    'crab': 'Подготовка к крабу', 'jg_path': 'Прошлые маршруты лесника',
    'jg_seen': 'Недавняя активность лесника', 'bench': 'Итоги линии на 10 и 15 минуте',
    'lens': 'Линза для поддержки', 'objectives': 'Скоро появится объект',
    'powerspike': 'Ключевые уровни и предметы',
}

class HintsScreen(tk.Frame,Components):
    def __init__(self,parent,app):
        from ui import C,F,MODES
        super().__init__(parent,bg=C['bg']);self.app,self.c,self.f=app,dict(C),F;self.pack(fill='both',expand=True)
        self.query=tk.StringVar();self.scope='all';self.mode=tk.StringVar(value='Все режимы');self.job=None;self.wide=None;self.last_test=None;self.expanded=set();self.bulk_open=False
        # Более контрастный вторичный текст только на этом экране, во всех темах.
        fg,bg=self.c['fg'],self.c['deep']
        self.c['hint_detail']='#'+''.join(f'{round(int(fg[i:i+2],16)*.8+int(bg[i:i+2],16)*.2):02x}' for i in (1,3,5))
        self.label(self,'Выбери роль и настрой напоминания',15,'fg').pack(anchor='w',pady=(2,8))
        self.label(self,'Общие настройки действуют для всех ролей.',11,'hint_detail').pack(anchor='w',pady=(0,14))
        self.roles=tk.Frame(self,bg=C['bg']);self.roles.pack(fill='x',pady=(0,14))
        row=tk.Frame(self,bg=C['bg']);row.pack(fill='x')
        self.label(row,'Поиск',11).pack(side='left',padx=(0,8));entry=ttk.Entry(row,textvariable=self.query,width=32,font=(F['font'],app.fs(12)));entry.pack(side='left',fill='x',expand=True,ipady=5)
        ttk.Style(self).configure('Hints.TCombobox',padding=(5,5))
        cb=ttk.Combobox(row,textvariable=self.mode,state='readonly',values=['Все режимы']+list(MODES.values()),width=15,font=(F['font'],app.fs(11)),style='Hints.TCombobox');cb.pack(side='left',padx=(10,0));cb.bind('<<ComboboxSelected>>',lambda e:self.refresh())
        self.query_trace=self.query.trace_add('write',lambda *_:self.search_changed())
        self.scopes=tk.Frame(self,bg=C['bg']);self.scopes.pack(fill='x',pady=(10,14))
        self.bulk_toggle=self.button(self,'Настроить все показанные ▾',self.toggle_bulk);self.bulk_toggle.pack(anchor='w',pady=(0,10))
        self.controls=self.panel(self,14)
        self.bulk_label=self.label(self.controls,'',12,'gold');self.bulk_label.pack(anchor='w')
        row=tk.Frame(self.controls,bg=C['panel']);row.pack(fill='x',pady=(8,0))
        for mode,title in MODES.items():self.button(row,title,lambda m=mode:self.set_all(m)).pack(side='left',padx=(0,6))
        self.label(self.controls,'Изменятся только подсказки в текущем списке.',11,'hint_detail').pack(anchor='w',pady=(8,10))
        self.button(self.controls,'Сбросить режимы всех ролей',self.reset_modes).pack(anchor='w')
        self.label(self.controls,'Свои тексты сохранятся.',11,'hint_detail').pack(anchor='w',pady=(6,0))
        self.summary=self.label(self,'',11,'hint_detail');self.summary.pack(anchor='w',pady=(0,8))
        self.body=tk.Frame(self,bg=C['bg']);self.body.pack(fill='x')
        self.bind('<Configure>',self.resized);self.bind('<Destroy>',self.cleanup,add='+');self.refresh()
    def cleanup(self,e):
        if e.widget is self:
            self.query.trace_remove('write',self.query_trace)
            if self.job:self.after_cancel(self.job);self.job=None
    def resized(self,e):
        if e.widget is not self:return
        if getattr(self,'layout_width',None)!=e.width:
            if self.job:self.after_cancel(self.job)
            self.job=self.after(100,self.refresh)
    def search_changed(self):
        if self.job:self.after_cancel(self.job)
        self.job=self.after(150,self.refresh)
    def choose_role(self,role):
        if role not in core.ROLES:return
        self.app.s['hint_preset']=role;self.app.s.save();self.refresh()
    def choose_scope(self,scope):self.scope=scope;self.refresh()
    def visible(self):
        from ui import MODES
        role=self.app.s['hint_preset'];q=champion_pool.norm(self.query.get());out=[]
        for hint in core.HINTS:
            hid,group,name,default,cooldown=hint;role_hint=hid in core.HINT_ROLES
            if role_hint and role not in core.HINT_ROLES[hid]:continue
            if self.scope=='role' and not role_hint or self.scope=='common' and role_hint:continue
            if self.mode.get()!='Все режимы' and MODES.get(self.app.hint_mode(hid))!=self.mode.get():continue
            custom=self.app.s['hint_text'].get(hid,{})
            haystack=' '.join([name,SHORT_TITLES.get(hid,''),SUMMARIES.get(hid,''),group,core.HINT_DESC.get(hid,''),custom.get('text',''),custom.get('say','')])
            if q and q not in champion_pool.norm(haystack):continue
            out.append(hint)
        return out
    def change_mode(self,hid):self.app.set_hint(hid);self.refresh()
    def set_all(self,mode):
        if mode not in ('off','text','beep','voice'):return
        ids=[hint[0] for hint in self.visible()];role=self.app.s['hint_preset']
        for hid in ids:
            if hid in core.HINT_ROLES:self.app.s['hints_role'].setdefault(role,{})[hid]=mode
            else:self.app.s['hints'][hid]=mode
        if ids:self.app.s.save()
        self.refresh()
    def reset_modes(self):
        from ui import SECTIONS
        self.app.s.reset(SECTIONS['hints']);self.refresh()
    def button(self,parent,text,command,on=False):
        button=Components.button(self,parent,text,command,on)
        button.configure(font=(self.f['font'],self.app.fs(11)),fg=self.c['gold'] if on else self.c['fg'])
        return button
    def toggle_bulk(self):
        self.bulk_open=not self.bulk_open
        if self.bulk_open:self.controls.pack(fill='x',pady=(0,14),before=self.summary)
        else:self.controls.pack_forget()
        self.bulk_toggle.configure(text='Настроить все показанные '+('▴' if self.bulk_open else '▾'))
    def toggle_details(self,hid):
        frame,button=self.details[hid]
        if hid in self.expanded:self.expanded.remove(hid);frame.pack_forget()
        else:self.expanded.add(hid);frame.pack(fill='x',pady=(10,0))
        button.configure(text='Свернуть ▴' if hid in self.expanded else 'Подробнее ▾')
    def test(self,hid,name):
        self.last_test=hid
        label=self.inline_previews[hid]
        if self.app.hint_mode(hid)=='off':label.configure(text='Подсказка выключена. Выбери режим для проверки.')
        else:
            hint=core.Hint(hid,name,None);self.app.apply_text(hint);label.configure(text=hint.text)
            self.app.test_hint(hid,name)
        label.pack(anchor='w',pady=(10,0))
    def refresh(self):
        from ui import MODES
        if self.job:self.after_cancel(self.job);self.job=None
        if not self.winfo_exists():return
        self.layout_width=self.winfo_width();self.wide=self.layout_width>=self.app.fs(1050)
        for child in self.roles.winfo_children():child.destroy()
        for role in core.ROLES:
            b=self.button(self.roles,core.ROLE_RU[role].capitalize(),lambda r=role:self.choose_role(r),role==self.app.s['hint_preset'])
            if role in self.app.icons.a.get('role',{}):b.configure(image=self.app.icons.get('role',role,self.app.fs(16)),compound='left')
            b.pack(side='left',padx=(0,4))
        for child in self.scopes.winfo_children():child.destroy()
        for key,title in (('all','Все'),('role','Для роли'),('common','Общие')):self.button(self.scopes,title,lambda s=key:self.choose_scope(s),key==self.scope).pack(side='left',padx=(0,4))
        for child in self.body.winfo_children():child.destroy()
        self.shown=self.visible();self.app.hint_vars={};self.rows={};self.mode_boxes={};self.inline_previews={};self.details={}
        self.bulk_label.configure(text=f'Для показанных подсказок: {len(self.shown)}')
        active=sum(self.app.hint_mode(h[0])!='off' for h in self.shown)
        self.summary.configure(text=f'{core.ROLE_RU[self.app.s["hint_preset"]].capitalize()} · показано {len(self.shown)} · включено {active}')
        groups={}
        for hint in self.shown:
            title='Для роли: '+core.ROLE_RU[self.app.s['hint_preset']] if hint[0] in core.HINT_ROLES else 'Общие · '+hint[1].lower()
            groups.setdefault(title,[]).append(hint)
        if not groups:
            self.label(self.body,'Подсказки не найдены. Измени поиск или фильтр режима.',12,'mute',wraplength=self.app.fs(700),justify='left').pack(anchor='w',pady=20)
        for title,hints in groups.items():
            box=self.panel(self.body,12);box.pack(fill='x',pady=(0,10))
            self.label(box,title+f' · {len(hints)}',15,'gold',head=True).pack(anchor='w',pady=(0,8))
            for hid,group,name,default,cooldown in hints:
                row=tk.Frame(box,bg=self.c['deep'],padx=self.app.fs(16),pady=self.app.fs(15));row.pack(fill='x',pady=(0,10));self.rows[hid]=row
                main=tk.Frame(row,bg=self.c['deep']);main.pack(fill='x')
                actions=tk.Frame(main,bg=self.c['deep']);actions.pack(side='right' if self.wide else 'bottom',anchor='w',padx=(18,0) if self.wide else 0,pady=0 if self.wide else (12,0))
                var=tk.StringVar(value=MODES[self.app.hint_mode(hid)]);self.app.hint_vars[hid]=var
                cb=ttk.Combobox(actions,textvariable=var,state='readonly',values=list(MODES.values()),width=8,font=(self.f['font'],self.app.fs(11)),style='Hints.TCombobox');cb.pack(side='left',padx=(0,8));cb.bind('<<ComboboxSelected>>',lambda e,k=hid:self.change_mode(k));self.mode_boxes[hid]=cb
                self.button(actions,'Проверить',lambda k=hid,n=name:self.test(k,n)).pack(side='left',padx=(0,6))
                self.button(actions,'Текст…',lambda k=hid,n=name:self.app.edit_hint(k,n)).pack(side='left')
                text=tk.Frame(main,bg=self.c['deep']);text.pack(side='left',fill='both',expand=True)
                width=max(220,self.winfo_width()-self.app.fs(440 if self.wide else 100))
                title=self.label(text,SHORT_TITLES.get(hid,name),13,'fg',wraplength=width,justify='left');title.configure(font=(self.f['font'],self.app.fs(13),'bold'));title.pack(anchor='w')
                self.label(text,SUMMARIES[hid],11,'hint_detail',wraplength=width,justify='left').pack(anchor='w',pady=(6,0))
                links=tk.Frame(text,bg=self.c['deep']);links.pack(anchor='w',pady=(8,0))
                detail_button=self.button(links,'Свернуть ▴' if hid in self.expanded else 'Подробнее ▾',lambda k=hid:self.toggle_details(k))
                detail_button.configure(highlightthickness=0,padx=0,pady=0,fg=self.c['gold']);detail_button.pack(side='left')
                if self.app.s['hint_text'].get(hid):self.label(links,'Свой текст',11,'hint_detail').pack(side='left',padx=(16,0))
                details=tk.Frame(row,bg=self.c['panel'],padx=self.app.fs(12),pady=self.app.fs(12));self.details[hid]=(details,detail_button)
                self.label(details,core.HINT_DESC.get(hid,''),12,'fg',wraplength=max(220,self.winfo_width()-self.app.fs(110)),justify='left').pack(anchor='w')
                if cooldown:self.label(details,f'Повтор — не чаще раза в {cooldown} с',11,'hint_detail').pack(anchor='w',pady=(8,0))
                if hid in self.expanded:details.pack(fill='x',pady=(10,0))
                self.inline_previews[hid]=self.label(row,'',12,'gold',wraplength=max(220,self.winfo_width()-self.app.fs(100)),justify='left')

class HintEditor(tk.Toplevel,Components):
    button=HintsScreen.button
    def __init__(self,view,hid,name):
        self.app,self.c,self.f=view.app,view.c,view.f;self.view,self.hid=view,hid
        super().__init__(self.app.root);self.title('Свой текст подсказки');self.configure(bg=self.c['bg']);self.transient(self.app.root)
        self.geometry(f'{self.app.fs(800)}x{self.app.fs(600)}');self.minsize(self.app.fs(640),self.app.fs(540))
        body=self.panel(self,16);body.pack(fill='both',expand=True,padx=12,pady=12)
        self.label(body,name,19,'gold',head=True,wraplength=self.app.fs(650),justify='left').pack(anchor='w')
        self.label(body,'Свой текст общий для всех ролей. {текст} подставляет исходную фразу.',12,'hint_detail',wraplength=self.app.fs(700),justify='left').pack(anchor='w',pady=(7,12))
        old=self.app.s['hint_text'].get(hid,{})
        self.label(body,'На экране',11).pack(anchor='w')
        self.text=tk.Text(body,height=3,wrap='word',bg=self.c['deep'],fg=self.c['fg'],insertbackground=self.c['gold'],font=(self.f['font'],self.app.fs(13)),spacing1=3,spacing3=5,relief='flat',padx=8,pady=8);self.text.pack(fill='both',expand=True,pady=(4,10));self.text.insert('1.0',old.get('text',''))
        self.label(body,'Для голоса · пусто — как на экране',11).pack(anchor='w')
        self.say=tk.Text(body,height=3,wrap='word',bg=self.c['deep'],fg=self.c['fg'],insertbackground=self.c['gold'],font=(self.f['font'],self.app.fs(13)),spacing1=3,spacing3=5,relief='flat',padx=8,pady=8);self.say.pack(fill='both',expand=True,pady=(4,10));self.say.insert('1.0',old.get('say',''))
        row=tk.Frame(body,bg=self.c['panel']);row.pack(fill='x')
        self.button(row,'Сохранить',self.save,True).pack(side='left',padx=(0,5))
        self.button(row,'Исходный текст',self.reset).pack(side='left',padx=(0,5));self.button(row,'Отмена',self.destroy).pack(side='right')
        self.bind('<Escape>',lambda e:self.destroy());self.bind('<Control-Return>',lambda e:self.save());self.text.focus_set()
    def reset(self):self.text.delete('1.0','end');self.say.delete('1.0','end')
    def save(self):
        text,say=self.text.get('1.0','end-1c').strip(),self.say.get('1.0','end-1c').strip()
        if text or say:self.app.s['hint_text'][self.hid]={'text':text,'say':say}
        else:self.app.s['hint_text'].pop(self.hid,None)
        self.app.s.save();self.destroy()
        if self.view.winfo_exists():self.view.refresh()
