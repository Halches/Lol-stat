"""Native widget gallery using the same images as real overlays and existing settings actions."""
import tkinter as tk
from tkinter import ttk
from view_components import Components

DESCRIPTIONS={
    'tab':('Перевес по Tab','Разница предметов напротив пар игроков и общий баланс сверху. На рисунке — увеличенные фрагменты надстройки.'),
    'hints':('Подсказки','Короткие напоминания о ганках, обзоре, объектах и действиях по ходу матча.'),
    'perf':('Твои показатели','Фарм, золото, KDA, участие в убийствах и обзор в сравнении с выбранным ориентиром.'),
    'lane':('Оппонент на линии','Перевес по предметам, уровни, фарм и счёт твоего оппонента.'),
    'inventory':('Стоимость инвентаря','Все десять чемпионов по стоимости предметов. Зелья, варды и тотемы исключены.'),
    'item':('До следующего предмета','Сколько золота осталось до компонента или следующего предмета.'),
    'timers':('Таймеры объектов','Время до дракона, личинок, Барона и других известных объектов.'),
    'arena':('Арена','Твой счёт, доступное золото и стоимость инвентаря в режиме Арены.')}

class WindowsScreen(tk.Frame,Components):
    def __init__(self,parent,app):
        from ui import C,F,WIDGETS
        super().__init__(parent,bg=C['bg']);self.app,self.c,self.f=app,C,F;self.pack(fill='both',expand=True)
        self.job=None;self.columns=None;self.photos={};self.previews={};self.cards={};self.advanced_open=False
        self.vars={key:tk.BooleanVar(value=app.s['widgets'].get(key,False)) for key in WIDGETS};app.w_vars=self.vars
        self.tab_var=tk.BooleanVar(value=app.s['scoreboard'])
        self.label(self,'Виджеты и окна',22,'gold',head=True).pack(anchor='w')
        self.label(self,'Выбери, что видеть во время игры. На изображениях — примеры, а не текущий матч.',10,'mute',wraplength=app.fs(850),justify='left').pack(anchor='w',pady=(3,10))
        actions=tk.Frame(self,bg=C['bg']);actions.pack(fill='x',pady=(0,10))
        self.button(actions,'Только Tab',self.only_tab).pack(side='left',padx=(0,8))
        app.demo_btn=self.button(actions,'Завершить расстановку' if app.demo_on else 'Показать виджеты для расстановки',app.toggle_demo)
        app.demo_btn.pack(side='left');self.state_label=self.label(actions,'',10,'gold');self.state_label.pack(side='right')
        self.label(self,f"Двигать: {app.s['keys']['drag'].upper()} + перетаскивание · булавка закрепляет виджет · Tab настраивается своей ручкой.",9,'mute',wraplength=app.fs(900),justify='left').pack(anchor='w',pady=(0,12))
        self.grid_box=tk.Frame(self,bg=C['bg']);self.grid_box.pack(fill='x')
        self.advanced_button=self.button(self,'▸ Раскладка, показатели, Tab, телефон и второй монитор',self.toggle_advanced)
        self.advanced_button.pack(anchor='w',pady=(8,10))
        self.advanced=tk.Frame(self,bg=C['bg']);app.build_windows_options(self.advanced)
        self.advanced.bind('<Configure>',self.wrap_options)
        self.bind('<Configure>',self.resized);self.bind('<Map>',self.mapped);self.bind('<Destroy>',self.cleanup,add='+')
        self.refresh()

    def cleanup(self,e):
        if e.widget is self and self.job:self.after_cancel(self.job);self.job=None
    def mapped(self,e):
        if e.widget is self:self.refresh()
    def resized(self,e):
        if e.widget is self and self.columns!=(2 if e.width>=self.app.fs(850) else 1):
            if self.job:self.after_cancel(self.job)
            self.job=self.after(100,self.refresh)
    def toggle_advanced(self):
        self.advanced_open=not self.advanced_open
        if self.advanced_open:self.advanced.pack(fill='x')
        else:self.advanced.pack_forget()
        self.advanced_button.configure(text=('▾' if self.advanced_open else '▸')+' Раскладка, показатели, Tab, телефон и второй монитор')
    def wrap_options(self,event):
        width=max(200,event.width-self.app.fs(20))
        for widget in self.advanced.winfo_children():
            if isinstance(widget,(tk.Label,ttk.Label)) and int(str(widget.cget('wraplength')) or 0)>0:widget.configure(wraplength=min(width,self.app.fs(660)))
        self.app.phone_lbl.configure(wraplength=width)
    def only_tab(self):
        for key in self.vars:self.app.s['widgets'][key]=False
        self.app.s['scoreboard']=True;self.app.s.save();self.app.apply_visibility();self.sync_demo();self.refresh()
    def sync_demo(self):
        if self.app.demo_on:
            self.app.set_unlocked(True)
            if not self.app.s['scoreboard']:
                for window in self.app.tab.values():window.withdraw()
    def toggle(self,key):
        if key=='tab':self.app.s['scoreboard']=self.tab_var.get();self.app.s.save()
        else:self.app.toggle_widget(key)
        self.sync_demo();self.refresh()
    def pin(self,key):
        overlay=self.app.ov.get(key)
        if overlay:overlay.toggle_pin()
        self.refresh()
    def thumbnail(self,key):
        from PIL import Image,ImageTk
        import widget_previews
        if key not in self.previews:self.previews[key]=widget_previews.render_preview(self.app,key)
        im=self.previews[key]
        if im is None:return None
        im=im.copy();im.thumbnail((self.app.fs(440),self.app.fs(150)),Image.Resampling.LANCZOS)
        photo=ImageTk.PhotoImage(im);self.photos[key]=photo;return photo
    def enlarge(self,key):
        im=self.previews.get(key)
        if im is None:return
        from PIL import Image,ImageTk
        win=tk.Toplevel(self.app.root);win.title(DESCRIPTIONS[key][0]+' · пример виджета');win.configure(bg=self.c['bg'])
        body=self.panel(win,14);body.pack(fill='both',expand=True,padx=12,pady=12)
        self.label(body,DESCRIPTIONS[key][0],20,'gold',head=True).pack(anchor='w')
        self.label(body,'Демонстрационные данные · тот же рисунок, что в игровом виджете',10,'mute').pack(anchor='w',pady=(5,12))
        shot=im.copy();shot.thumbnail((min(self.app.fs(1000),win.winfo_screenwidth()-100),win.winfo_screenheight()-220),Image.Resampling.LANCZOS)
        photo=ImageTk.PhotoImage(shot);win.preview_photo=photo;tk.Label(body,image=photo,bg=self.c['deep']).pack(pady=(0,10))
        self.label(body,DESCRIPTIONS[key][1],11,'fg',wraplength=min(self.app.fs(800),win.winfo_screenwidth()-150),justify='left').pack(anchor='w')
        self.button(body,'Закрыть',win.destroy).pack(anchor='e',pady=(12,0));win.bind('<Escape>',lambda e:win.destroy());self.preview_window=win
    def refresh(self):
        if self.job:self.after_cancel(self.job);self.job=None
        if not self.winfo_exists():return
        for child in self.grid_box.winfo_children():child.destroy()
        for col in (0,1):self.grid_box.columnconfigure(col,weight=0,uniform='')
        self.columns=2 if self.winfo_width()>=self.app.fs(850) else 1
        self.cards={};self.toggles={};self.tab_var.set(self.app.s['scoreboard'])
        for key,var in self.vars.items():var.set(self.app.s['widgets'].get(key,False))
        count=int(self.tab_var.get())+sum(v.get() for v in self.vars.values());self.state_label.configure(text=f'Включено {count} / 8')
        for i,(key,(title,description)) in enumerate(DESCRIPTIONS.items()):
            enabled=self.tab_var.get() if key=='tab' else self.vars[key].get()
            box=self.panel(self.grid_box,12);box.configure(highlightbackground=self.c['gold' if enabled else 'line'])
            box.grid(row=i//self.columns,column=i%self.columns,sticky='nsew',padx=(0,8) if i%self.columns==0 and self.columns==2 else 0,pady=(0,8));self.cards[key]=box
            self.grid_box.columnconfigure(i%self.columns,weight=1,uniform='widgets')
            head=tk.Frame(box,bg=self.c['panel']);head.pack(fill='x')
            self.label(head,title,15,'gold' if enabled else 'fg',head=True).pack(side='left')
            var=self.tab_var if key=='tab' else self.vars[key]
            toggle=ttk.Checkbutton(head,text='Включён' if enabled else 'Выключен',variable=var,command=lambda k=key:self.toggle(k));toggle.pack(side='right');self.toggles[key]=toggle
            preview=tk.Frame(box,bg=self.c['deep'],height=self.app.fs(160));preview.pack(fill='x',pady=(9,8));preview.pack_propagate(False)
            try:photo=self.thumbnail(key)
            except (OSError,ValueError,ImportError):photo=None
            image=tk.Label(preview,image=photo if photo else '',text='' if photo else 'Предпросмотр недоступен',bg=self.c['deep'],fg=self.c['mute'],cursor='hand2')
            image.pack(expand=True);image.bind('<Button-1>',lambda e,k=key:self.enlarge(k))
            self.label(box,description,10,'fg',wraplength=self.app.fs(430 if self.columns==2 else 720),justify='left').pack(anchor='w')
            bottom=tk.Frame(box,bg=self.c['panel']);bottom.pack(side='bottom',fill='x',pady=(10,0))
            enlarge=self.button(bottom,'Увеличить',lambda k=key:self.enlarge(k));enlarge.pack(side='left')
            if photo is None:enlarge.configure(state='disabled')
            if key!='tab':
                pinned=bool(self.app.s.get('widget_pins',{}).get(key))
                pin=self.button(bottom,'Закреплён' if pinned else 'Закрепить',lambda k=key:self.pin(k),pinned);pin.pack(side='right')
                if photo is not None:
                    from PIL import ImageTk
                    import render
                    pin.pin_photo=ImageTk.PhotoImage(render.pin_icon(pinned,self.app.s['scale']/100))
                    pin.configure(image=pin.pin_photo,compound='left')
            else:self.label(bottom,self.app.s['keys']['scoreboard'].upper()+' · при удержании',9,'gold').pack(side='right')
