"""Отдельное Qt-окно драфта, загрузки, живой игры и разбора."""
import time,json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QScrollArea,QDialog,QApplication,QLayout
from .widgets import *
from .champion import loadout
from .pages import equipment,fmt
from app_config import C,rank_short,hist_tags,scout_plan,scout_text
import core,draft_model,player_comments

class Dashboard(QWidget):
    def __init__(self,app):
        super().__init__();self.app=app;self.mode='idle';self._manual_hidden=False;self.draft_sig=None;self.log=[];self.cards={};self.deadline=0
        self.setWindowTitle('LoL Helper · драфт и игра');self.resize(1500,850);self.setMinimumSize(900,580)
        screens=QApplication.screens()
        if len(screens)>1:self.move(screens[1].availableGeometry().topLeft())
        b=QVBoxLayout(self);b.setContentsMargins(0,0,0,0);self.shell=Shell();b.addWidget(self.shell)
        content=QWidget();layout=QVBoxLayout(content);self.shell.box.addWidget(content);self.head=Label('Драфт и игра',23,'gold',serif=True);self.sub=Label('Ожидаю клиент League of Legends',10,'mute');layout.addWidget(self.head);layout.addWidget(self.sub)
        scroll=QScrollArea();scroll.setWidgetResizable(True);self.body=QWidget();self.box=QVBoxLayout(self.body);self.box.setContentsMargins(2,4,2,4);self.box.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize);scroll.setWidget(self.body);layout.addWidget(scroll);self.scroll=scroll;self.idle()
        geometry=app.s.get('qt_dashboard_geometry')
        if isinstance(geometry,list) and len(geometry)==4:self.setGeometry(*geometry)
    def closeEvent(self,e):
        self.app.s['qt_dashboard_geometry']=[self.x(),self.y(),self.width(),self.height()];self.app.s.save();self._manual_hidden=True;self.hide();e.ignore()
    def deiconify(self):QWidget.show(self)
    def lift(self):self.raise_()
    def clear(self,mode):self.mode=mode;clear_layout(self.box);self.cards={};self.import_lbl=None
    def idle(self):self.clear('idle');self.head.setText('Драфт и игра');self.sub.setText('Ожидаю выбор чемпионов');self.box.addWidget(Label('Во время выбора здесь появятся рекомендации, сборки и импорт. Во время игры — команды и показатели.',14,'mute'));self.box.addStretch()
    def reset(self):self.clear('game');self.log=[]
    def add_log(self,t,text):self.log.append((t,text));self.log=self.log[-60:]
    def tick(self):
        if self.deadline and self.mode=='draft':self.head.setText('Выбор чемпионов · '+str(max(0,int(self.deadline-time.time())))+' с')
    def player(self,p,r=None,side=0,allies=()):
        a=self.app;c=p.get('c');card=Panel(padding=10);card.setMinimumWidth(235)
        head=row(a.icons.label('champ',c,44),Label(a.data.cn(c) if c else 'Ещё не выбран',14,bold=True,serif=True));card.box.addWidget(head)
        card.box.addWidget(Label(core.ROLE_RU.get(p.get('pos'),'Роль неизвестна')+(' · ты' if p.get('me') else ''),9,'mute'))
        if p.get('rank') and a.s['show']['ranks']:card.box.addWidget(Label(rank_short(p['rank']),10,'gold'))
        summary,tags=hist_tags(p.get('hist'))
        if summary:card.box.addWidget(Label(summary,10,'mute'))
        for _,text,tone in player_comments.comments(p.get('hist')) if p.get('hist') else []:card.box.addWidget(Label(text,10,{'good':'good','bad':'bad','neutral':'warn'}.get(tone,'mute')))
        if p.get('pu'):card.box.addWidget(Button('История игрока',lambda pu=p['pu']:a.show_player_history(pu)))
        if r:
            for title,values in a.matchup_lines(p,side,allies,r):
                if isinstance(values,str):card.box.addWidget(Label(title,10,values));continue
                card.box.addWidget(Label(title,9,'mute'))
                for champion,value,color in values:card.box.addWidget(row(a.icons.label('champ',champion,24),Label(a.data.cn(champion)+' '+value,10,color)))
        return card
    def toolbar(self,cs,role):
        a=self.app;b=Panel();controls=row(combo({**core.ROLE_RU,'':'Авто'},a.role_override or '',lambda v:a.set_draft_role(v or None)),combo({'pool':'Советовать из пула','all':'Все чемпионы'},a.s['draft_scope'],a.set_draft_scope),Button('Экспортировать выбранное',lambda:a.do_import(tuple(k for k,v in a.s['auto_parts'].items() if v))))
        b.box.addWidget(controls)
        def part(key,value):a.s['auto_parts'][key]=value;a.s['auto_import']=any(a.s['auto_parts'].values());a.s.save();a.imported=None
        b.box.addWidget(row(check('Автоимпорт после подтверждения',a.s['auto_import'],lambda v:self.auto(v)),*[check(title,a.s['auto_parts'][key],lambda v,k=key:part(k,v)) for key,title in [('runes','Руны'),('items','Предметы'),('spells','Заклинания')]]))
        b.box.addWidget(row(*[Button('Импорт: '+title,lambda k=key:a.do_import((k,))) for key,title in [('runes','руны'),('items','предметы'),('spells','заклинания')]]))
        self.import_lbl=Label(a.import_text,10,'mute');b.box.addWidget(self.import_lbl);self.box.addWidget(b)
    def auto(self,value):self.app.s['auto_import']=value;self.app.s.save()
    def builds(self,parent,cs,role):
        a=self.app;c=cs.get('me')
        if not c:parent.addWidget(Label('Выбери чемпиона для сборки.',12,'mute'));return
        full=a.lola_build(c,role);options=row()
        for key,title in [('pick','Популярная'),('win','По винрейту')]:options.layout().addWidget(Button(title,lambda key=key:a.set_draft_build('general',key),a.s['draft_build_context']=='general' and a.s['rune_pick']==key))
        parent.addWidget(options)
        opponent=a.draft_opponent(cs,role) if role in core.ROLES else None
        if opponent:
            parent.addWidget(row(*[Button('Против '+a.data.cn(opponent)+' · '+title,lambda k=k:a.set_draft_build('matchup',k),a.s['draft_build_context']=='matchup' and a.s['rune_pick']==k) for k,title in [('pick','популярная'),('win','винрейт')]]))
        if role in core.ROLES:
            off=a.offmeta_build(c,role);players=a.player_builds(c,role)
            if off and off.get('variant'):parent.addWidget(Button('Оффметовая · Mobalytics',lambda:a.set_draft_build('offmeta','pick'),a.s['draft_build_context']=='offmeta'))
            for kind,title in [('OTP','Мейнеры'),('Pro','Проигроки')]:
                group=(players or {}).get('groups',{}).get(kind,[]);parent.addWidget(Label(title+f' · {len(group)}/3',11,'gold'))
                for p in group:
                    button=Button(p['name']+f" · {p['winrate']:.1f}%",lambda pid=p['id']:a.set_draft_build('player:'+pid,'pick'),a.s['draft_build_context']=='player:'+p['id']);button.setEnabled(bool(p.get('variant')));parent.addWidget(button)
        chosen=a.selected_draft_build(cs);variant=(chosen.get(a.s['rune_pick']) or chosen) if chosen else None
        parent.addWidget(loadout(a,chosen,variant))
    def show_draft(self,cs,r,bans):
        self.clear('draft');a=self.app;self.head.setText('Выбор чемпионов');self.sub.setText(core.ROLE_RU.get(r['role'],r['role'])+' · '+r.get('how',''));self.deadline=time.time()+cs.get('left',0);self.toolbar(cs,r['role'])
        columns=row();left=Panel(kind=None,padding=0);middle=Panel(kind=None,padding=0);right=Panel(kind=None,padding=0)
        columns.layout().addWidget(left,3);columns.layout().addWidget(middle,4);columns.layout().addWidget(right,3);self.box.addWidget(columns)
        for column,title in [(left,'Твоя команда'),(middle,'Выбор и сборка'),(right,'Противники')]:column.box.addWidget(Label(title,16,'gold',serif=True))
        allies=cs.get('allies') or []
        for p in draft_model.role_slots(allies,core.ROLES):left.box.addWidget(self.player(p,r,0,allies))
        roles=core.guess_enemy_roles(a.data,cs.get('enemies') or [])
        for p in draft_model.role_slots([{'c':c,'pos':role} for c,role in roles.items()],core.ROLES):right.box.addWidget(self.player(p,r,1,allies))
        for choice in r.get('picks',[]):
            p=Panel(padding=9,horizontal=True);p.box.addWidget(a.icons.label('champ',choice['c'],42));p.box.addWidget(Label(choice['name']+'\n'+choice['why'],11));middle.box.addWidget(p)
        self.builds(middle.box,cs,r['role'])
        comp=core.comp_advice(a.data,[p['c'] for p in allies if p.get('c') and not p.get('me')],r['role'],(a.player.pool.get(r['role']) if a.player else []) or [])
        if comp:middle.box.addWidget(Label(comp[0]+(' · Из пула: '+', '.join(a.data.cn(c) for c in comp[1]) if comp[1] else ''),11,'warn'))
        middle.box.addWidget(Label('Баны',15,'gold',serif=True))
        for c,score,why in bans:middle.box.addWidget(row(a.icons.label('champ',c,28),Label(a.data.cn(c)+' · '+why,10)))
        for column in (left,middle,right):column.box.addStretch()
        if not self._manual_hidden:self.deiconify()
    def show_aram(self,cs):
        self.clear('draft');self.head.setText('ARAM');self.sub.setText('Сборки ARAM и скамейка');self.toolbar(cs,'ARAM')
        for p in cs.get('allies',[]):self.box.addWidget(self.player(p))
        self.builds(self.box,cs,'ARAM');self.box.addWidget(Label('Скамейка',16,'gold',serif=True));self.box.addWidget(row(*[row(self.app.icons.label('champ',c,36),Label(self.app.data.cn(c))) for c in cs.get('bench',[])]))
        if not self._manual_hidden:self.deiconify()
    def show_arena(self,cs):
        self.clear('draft');self.head.setText('Арена');self.sub.setText('Статистика чемпионов и твоих матчей Арены');a=self.app;c=cs.get('me');games=a.arena_games()
        for p in cs.get('allies',[]):self.box.addWidget(self.player(p))
        if c:
            stats=core.arena_stats(games,c);external=a.lola_fetch('arena',c,'ARENA')
            self.box.addWidget(Label(a.data.cn(c),20,'gold',serif=True))
            if external:self.box.addWidget(Label(f"Изумруд+: {external['wr']:.1f}% · {external['n']} игр"))
            if stats:self.box.addWidget(Label(f"Ты: {stats['n']} игр · место {stats['avg']:.1f} · топ-4 {stats['top4']:.0f}%"))
        self.box.addWidget(Label('Твои лучшие в Арене',17,'gold',serif=True))
        for c,st in core.arena_best(games):self.box.addWidget(row(a.icons.label('champ',c,36),Label(f"{a.data.cn(c)} · место {st['avg']:.1f} · {st['n']} игр")))
        self.box.addWidget(table(['Чемпион','Место','K / D / A','Напарник'],[[a.data.cn(g['c']),g['place'],f"{g['k']}/{g['d']}/{g['a']}",a.data.cn(g.get('pc'))] for g in games[:8]]))
        if not self._manual_hidden:self.deiconify()
    def show_loading(self,players):
        self.clear('loading');self.head.setText('Загрузка матча');role=next((p.get('pos') for p in players if p.get('me')),'');self.sub.setText(' · '.join(scout_plan(self.app.data,players,role)))
        columns=row()
        for side,title in [(0,'Твоя команда'),(1,'Противники')]:
            panel=Panel(kind=None,padding=0);panel.box.addWidget(Label(title,17,'blue' if side==0 else 'red',serif=True))
            for p in players:
                if p.get('col')==side:panel.box.addWidget(self.player(p))
            panel.box.addStretch();columns.layout().addWidget(panel)
        self.box.addWidget(columns)
        if not self._manual_hidden:self.deiconify()
    def show(self,g,scout,ranks,hists):
        a=self.app;sig=tuple(p['riot'] for p in g.players)
        if self.mode!='game' or getattr(self,'game_roster',None)!=sig:
            self.clear('game');self.game_roster=sig;self.objectives=Label('',12,'gold');self.box.addWidget(self.objectives);columns=row()
            for side,team in enumerate((g.allies,g.enemies)):
                column=Panel(kind=None,padding=0);column.box.addWidget(Label('Твоя команда' if side==0 else 'Противники',17,'blue' if side==0 else 'red',serif=True))
                for p in sorted(team,key=lambda p:core.ROLES.index(p['pos']) if p['pos'] in core.ROLES else 9):
                    card=Panel(padding=10);pic=a.icons.label('champ',p['c'],48);name=Label('',16,bold=True,serif=True);line=Label('',11,'mute');comments=Label('',10);items=QWidget();items.setLayout(QHBoxLayout());card.box.addWidget(row(pic,name));card.box.addWidget(line);card.box.addWidget(items);card.box.addWidget(comments)
                    history=Button('История игрока',lambda riot=p['riot']:a.show_player_history(a.pus.get(riot)));card.box.addWidget(history);column.box.addWidget(card);self.cards[p['riot']]={'pic':pic,'name':name,'line':line,'comments':comments,'items':items,'sig':None}
                column.box.addStretch();columns.layout().addWidget(column)
            self.box.addWidget(columns);self.log_label=Label('',10,'mute');self.box.addWidget(self.log_label)
        self.head.setText('Игра · '+core.mmss(g.t));self.sub.setText(f'Перевес по стоимости предметов: {g.gold_diff():+,.0f}'.replace(',',' '))
        self.objectives.setText(' · '.join(f'{key}: {core.mmss(t-g.t) if t>g.t else "на карте"}' for key,t in g.objectives().items() if type(t) in (int,float)))
        for p in g.players:
            card=self.cards[p['riot']];card['name'].setText(a.data.cn(p['c'])+f" · {p['k']}/{p['d']}/{p['a']}"+(' · мёртв '+core.mmss(p['respawn']) if p['dead'] else ''))
            card['line'].setText(f"{core.ROLE_RU.get(p['pos'],'')} · {p['lvl']} ур. · CS {p['cs']} · предметы {p['igold']:.0f}"+'\n'+rank_short(ranks.get(p['riot'])))
            record={'items':p['items'] if a.s['show']['items'] else [],'spells':p['spells'] if a.s['show']['spells'] else [],'perk':p['keystone'] if a.s['show']['runes'] else None};new_sig=json.dumps(record)
            if new_sig!=card['sig']:clear_layout(card['items'].layout());card['items'].layout().addWidget(equipment(a,record,26));card['sig']=new_sig
            summary,tags=hist_tags(hists.get(p['riot']));card['comments'].setText(summary+'\n'+' · '.join(t[0] for t in tags)+('\n'+scout_text(scout[p['riot']]) if p['riot'] in scout and a.s['show']['scout'] else ''))
        self.log_label.setText('\n'.join(core.mmss(t)+' · '+text for t,text in self.log[-10:]))
        if not self._manual_hidden:self.deiconify()
