"""Чемпион, подтверждённые сборки и навыки на Qt."""
from PySide6.QtWidgets import QComboBox,QCompleter,QWidget,QVBoxLayout
from PySide6.QtCore import Qt
from .widgets import *
from .pages import fmt
import core,home_model,draft_model,champion_pool

def champion_choice(app,selected=None,changed=None,empty='Выбери чемпиона'):
    choices={'':empty,**{k:app.data.cn(k) for k in sorted(set(app.data.ids.values()),key=app.data.cn)}}
    c=combo(choices,selected or '',changed);c.setEditable(True);c.setInsertPolicy(QComboBox.InsertPolicy.NoInsert);c.completer().setFilterMode(Qt.MatchFlag.MatchContains);return c

def loadout(app,full,variant):
    p=Panel();p.box.addWidget(Label('Выбранный вариант',17,'gold',serif=True))
    if not variant:p.box.addWidget(Label('Подтверждённые руны и предметы пока недоступны.',11,'mute'));return p
    if (full or {}).get('external'):p.box.addWidget(Label(str(full['external'])+' · '+str(full.get('external_name','')),11,'gold'))
    p.box.addWidget(row(*[app.icons.label('rune',r,32) for r in variant.get('perks',[])[:6]],*[app.icons.label('rune',r,22) for r in variant.get('shards',[])]))
    for title,items in [('Старт',variant.get('start',[])),('Основа',core.lola_build_items(variant))]:
        icons=[]
        for item in items:
            icon=app.icons.label('item',item,32);icon.setToolTip(app.data.iname(item));icons.append(icon)
        p.box.addWidget(row(Label(title,11),*icons))
    p.box.addWidget(row(Label('Заклинания'),*[app.icons.label('spell',s,28) for s in variant.get('spells',[])[:2]]))
    for title,wr,n in [('Руны',variant.get('wr_runes'),variant.get('n_runes')),('Предметы',variant.get('wr_core'),variant.get('n_core'))]:p.box.addWidget(Label(title+': '+fmt(wr)+'% · '+(str(n)+' игр' if n is not None else 'выборка недоступна'),10,'mute'))
    p.box.addWidget(Label('Выборки рун и предметов раздельные; совместный винрейт не подтверждён.',9,'mute'))
    if (full or {}).get('stale'):p.box.addWidget(Label('Сохранённые данные: обновить источник не удалось.',10,'gold'))
    priority=variant.get('skill_prio') or [];skills=variant.get('skills') or []
    if priority:p.box.addWidget(Label('Умения: '+' › '.join(priority),14,'gold',bold=True))
    if skills:
        p.box.addWidget(table([str(i) for i in range(1,len(skills)+1)],[[str(x) for x in skills]]))
    for iid,short,when in (full or {}).get('situ',[])[:6]:p.box.addWidget(row(app.icons.label('item',iid,26),Label(short+' · '+when,10,'mute')))
    return p

class ChampionPage(Page):
    def __init__(self,app):
        super().__init__(app);self.champion=None;self.role='TOP';self.opponent=None;self.context='general';self.variant='pick'
        self.title('Чемпион');self.select=champion_choice(app,changed=lambda c:self.choose(c or None));self.role_select=combo(core.ROLE_RU,self.role,lambda role:self.choose(self.champion,role));self.enemy=champion_choice(app,changed=self.select_opponent,empty='Все оппоненты');self.box.addWidget(row(self.select,self.role_select,self.enemy))
        self.body=QWidget();self.body_box=QVBoxLayout(self.body);self.body_box.setContentsMargins(0,0,0,0);self.box.addWidget(self.body);self.box.addStretch();self.refresh()
    def choose(self,champion,role=None):
        self.champion=champion;self.role=role or self.role;self.app.cp_sel=(champion,self.role) if champion else None
        for widget,val in ((self.select,champion or ''),(self.role_select,self.role)):
            widget.blockSignals(True);widget.setCurrentIndex(max(0,widget.findData(val)));widget.blockSignals(False)
        self.refresh()
    def select_opponent(self,c):self.opponent=c or None;self.context='matchup' if c else 'general';self.variant='pick';self.refresh()
    def select_build(self,context,variant):self.context=context;self.variant=variant;self.refresh()
    def refresh(self):
        clear_layout(self.body_box);a=self.app;c=self.champion
        if not c:
            self.body_box.addWidget(Label('Выбери чемпиона по русскому или английскому имени.',13,'mute'));return
        role=self.role;full=a.lola_build(c,role);offmeta=a.offmeta_build(c,role);players=a.player_builds(c,role);match=a.lola_matchup(c,role,self.opponent) if self.opponent else None
        self.body_box.addWidget(row(a.icons.label('champ',c,68),Label(a.data.cn(c),25,bold=True,serif=True),Button('Убрать из пула' if c in a.current_pool()[role] else 'Добавить в пул',self.toggle_pool)))
        self.body_box.addWidget(row(Button('Все матчапы',lambda:self.select_build('general','pick'),self.context=='general'),Button('Против оппонента',lambda:self.select_build('matchup','pick'),self.context=='matchup')) if self.opponent else Label('EUW · Изумруд+ · все матчапы',10,'mute'))
        source=match if self.context=='matchup' else full;options=draft_model.build_options(source);buttons=row()
        selected=next((o['variant'] for o in options if o['key']==self.variant),None)
        for opt in options:
            buttons.layout().addWidget(Button(opt['title'],lambda k=opt['key']:self.select_build(self.context,k),self.variant==opt['key']))
        if self.context=='general' and offmeta and offmeta.get('variant'):
            buttons.layout().addWidget(Button('Оффметовая',lambda:self.select_build('general','offmeta'),self.variant=='offmeta'))
            if self.variant=='offmeta':source=offmeta;selected=offmeta['variant']
        for group in (players or {}).get('groups',{}).values():
            for p in group:
                if self.variant=='player:'+p['id']:source=p;selected=p.get('variant')
        self.body_box.addWidget(buttons);self.body_box.addWidget(loadout(a,source,selected))
        games=a.player.on(c,role) if a.player else []
        if self.context=='matchup':games=[g for g in games if g.get('opp')==self.opponent]
        st=home_model.stats(games);self.body_box.addWidget(Label('Твоя статистика',17,'gold',serif=True));self.body_box.addWidget(table(['Матчи','Победы','KDA','Фарм / мин'],[[st['n'],fmt(st['wr'])+'%',fmt(st['kda'],2),fmt(st['csm'])]]))
        counters=core.lola_counters(a.lola_fetch('counter',c,role),a.data)
        self.body_box.addWidget(Label('Матчапы на линии',17,'gold',serif=True))
        for enemy,values in sorted(counters.items(),key=lambda r:-r[1][1])[:12]:
            wr,delta,n=values
            self.body_box.addWidget(row(a.icons.label('champ',enemy,28),Button(a.data.cn(enemy),lambda e=enemy:self.pick_enemy(e)),Label(f'{wr:.1f}% · {delta:+.1f} · {n} игр',11,'good' if delta>0 else 'bad')))
        if not counters:self.body_box.addWidget(Label('Матчапы пока недоступны.',10,'mute'))
        for kind,title in [('OTP','Мейнеры'),('Pro','Проигроки')]:
            group=(players or {}).get('groups',{}).get(kind,[]);self.body_box.addWidget(Label(title+f' · {len(group)}/3',17,'gold',serif=True))
            for p in group:
                b=Button(p['name']+f" · {p['winrate']:.1f}% · {p['games']} игр",lambda pid=p['id']:self.select_build('general','player:'+pid));b.setEnabled(bool(p.get('variant')));self.body_box.addWidget(b);self.body_box.addWidget(Label('Mobalytics · патч '+p.get('patch','—'),9,'mute'))
            if len(group)<3:self.body_box.addWidget(Label('Источник пока не подтвердил остальные сборки для этой роли.',10,'mute'))
    def pick_enemy(self,c):
        self.enemy.blockSignals(True);self.enemy.setCurrentIndex(self.enemy.findData(c));self.enemy.blockSignals(False);self.select_opponent(c)
    def toggle_pool(self):self.app.toggle_pool(self.champion,self.role);self.refresh()
