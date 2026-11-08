"""Главная, архив матчей и пул чемпионов на Qt."""
import time,threading
from PySide6.QtCore import Qt,QSize,QTimer
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QDialog,QScrollArea,QLineEdit,QListWidget,
    QListWidgetItem,QListView,QAbstractItemView,QHeaderView)
from .widgets import *
import core,home_model,history_model,champion_pool
from app_config import C,TIER_RU,RIOT_NOTE

def fmt(v,n=1):return f'{v:.{n}f}'.replace('.',',') if type(v) in (int,float) else '—'
def equipment(app,record,size=25):
    out=[]
    for s in record.get('spells',[]):out.append(app.icons.label('spell',core.SPELL_KEY.get(s,s),size))
    if record.get('perk'):out.append(app.icons.label('rune',record['perk'],size))
    for item in record.get('items',[]):
        if item:
            icon=app.icons.label('item',item,size);icon.setToolTip(app.data.iname(item));out.append(icon)
    return row(*out)

class MatchCard(Panel):
    def __init__(self,app,record):
        super().__init__(padding=10);self.record=record;self.mode=None;self.box.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.grid=QGridLayout();self.box.addLayout(self.grid);self.grid.setContentsMargins(0,0,0,0)
        self.portrait=app.icons.label('champ',record['champion'],46)
        self.text=Panel(padding=0,kind=None);self.text.box.addWidget(Label(app.data.cn(record['champion']),14,bold=True,serif=True))
        stamp=time.strftime('%d.%m %H:%M',time.localtime(record['timestamp'])) if record.get('timestamp') else '—'
        self.text.box.addWidget(Label(core.QUEUE_RU.get(record['queue'],'Режим неизвестен')+' · '+stamp,9,'mute'))
        self.items=equipment(app,record,24);self.values=Panel(padding=0,kind=None)
        self.values.box.addWidget(Label(' / '.join(str(record.get(k)) if record.get(k) is not None else '—' for k in ('k','d','a')),17,serif=True,bold=True))
        self.values.box.addWidget(Label(fmt(record.get('csm'))+' CS/мин',9,'mute'))
        self.extra=Label('Участие '+fmt(record.get('kp'),0)+'%\nОбзор '+fmt(record.get('vsm'),2)+'/мин',9,'mute')
        win=record.get('win');title='ПОБЕДА' if win is True else 'ПОРАЖЕНИЕ' if win is False else 'НЕТ ДАННЫХ'
        self.result=Panel(padding=0,kind=None);button=Button(title,lambda:app.open_record(record));button.text_color=C['good' if win is True else 'bad' if win is False else 'mute'];self.result.box.addWidget(button)
        duration=core.mmss(record['duration']) if record.get('duration') else '—';lp=f"{record['lp']:+d} LP" if type(record.get('lp')) is int else 'LP —';self.result.box.addWidget(Label(duration+' · '+lp,9,'mute'))
        self.arrange(True)
    def minimumSizeHint(self):return QSize(480,80 if self.mode else 125)
    def resizeEvent(self,event):super().resizeEvent(event);self.arrange(self.width()>=1000)
    def arrange(self,wide):
        if self.mode==wide:return
        self.mode=wide
        for w in (self.portrait,self.text,self.items,self.values,self.extra,self.result):self.grid.removeWidget(w)
        if wide:
            for i,w in enumerate((self.portrait,self.text,self.items,self.extra,self.values,self.result)):self.grid.addWidget(w,0,i)
        else:
            self.grid.addWidget(self.portrait,0,0);self.grid.addWidget(self.text,0,1,1,2);self.grid.addWidget(self.values,0,3);self.grid.addWidget(self.result,0,4,2,2);self.grid.addWidget(self.items,1,0,1,3);self.grid.addWidget(self.extra,1,3)
        self.grid.setColumnStretch(1,2);self.grid.setColumnStretch(2,3 if wide else 1);self.updateGeometry()
    def paintEvent(self,event):
        super().paintEvent(event);p=QPainter(self);p.setPen(QPen(QColor(C['good' if self.record.get('win') is True else 'bad' if self.record.get('win') is False else 'mute']),4));p.drawLine(5,15,5,self.height()-15)

def match_card(app,record):return MatchCard(app,record)

class HomePage(Page):
    def refresh(self):
        self.clear();a=self.app;d=a.data;profile=d.d['players'].get(a.who or '',{});own=home_model.live_profile(profile,a.account);account=(a.account or {}) if own else {}
        self.box.addWidget(row(Label('ПРОСМОТР ПРОФИЛЯ',9,'mute'),combo({k:p['riot'] for k,p in d.d['players'].items()},a.who,self.choose)))
        hero=Panel(horizontal=True);identity=Panel(kind=None,padding=4)
        if account.get('icon') is not None:a.ensure_home_icon(account['icon']);hero.box.addWidget(a.icons.label('profile',account['icon'],76))
        identity.box.addWidget(Label(profile.get('riot') or account.get('riot') or 'Профиль не выбран',26,serif=True,bold=True))
        identity.box.addWidget(Label('Клиент подключён' if account else 'Сохранённая статистика',10,'mute'));hero.box.addWidget(identity,2)
        for key,title in [('solo','СОЛО / ДУО'),('flex','ФЛЕКС'),('arena','АРЕНА'),('tft','TFT')]:
            r=(account.get('ranks') or {}).get(key) or {};rank=Panel(padding=8,kind=None);rank.box.addWidget(Label(title,9,'mute'))
            tier=r.get('tier');fallback=profile.get('rank','') if key=='solo' else ''
            if not tier and fallback:tier=next((k for k,v in TIER_RU.items() if fallback.startswith(v)),None)
            name=(TIER_RU.get(tier,tier or '')+' '+r.get('div','')).strip() if r.get('state')=='ranked' else 'Без ранга' if r.get('state')=='unranked' else 'Калибровка' if r.get('state')=='provisional' else fallback or 'Нет данных'
            if key=='arena':name='Слава'
            if a.s['show']['ranks'] and tier:rank.box.addWidget(a.icons.label('tft_emb' if key=='tft' else 'emb',TIER_RU.get(tier),42))
            rank.box.addWidget(Label(name,12,bold=True));rank.box.addWidget(Label(f"{r['lp']} LP" if r.get('lp') is not None else 'Рангов больше нет' if key=='arena' else '—',10,'gold'));hero.box.addWidget(rank,1)
        self.box.addWidget(hero)
        self.box.addWidget(row(Button('Окно драфта и игры',a.open_dash),Button('Мой пул',lambda:a.navigate(10)),Button('Сайт со статистикой',a.open_site)))
        self.box.addWidget(row(Label('Статистика',19,'gold',serif=True),combo({'season':'Сезон','recent':'Последние 20'},a.s['home_period'],self.period)))
        games=a.player.games if a.player else [];snap=home_model.snapshot(games,a.s['home_period']);st=snap['stats'];metrics=[]
        for title,key,count in [('Винрейт','wr','results'),('KDA','kda','kda_n'),('Фарм / мин','csm','csm_n'),('Обзор / мин','vsm','vsm_n')]:
            p=Panel();p.box.addWidget(Label(title.upper(),10,'mute'));p.box.addWidget(Label(fmt(st[key],2 if key in ('kda','vsm') else 1)+('%' if key=='wr' and st[key] is not None else ''),30,bold=True,serif=True));p.box.addWidget(Label(f"По {st[count]} матчам",9,'mute'))
            vals=[]
            for g in reversed(snap['selected'][:20]):
                v=g.get(key)
                if key=='wr':v=100*g['w'] if g.get('w') in (0,1) else None
                if key=='kda':v=(g['k']+g['a'])/max(1,g['d']) if all(type(g.get(k)) in (int,float) for k in ('k','d','a')) else None
                vals.append(v)
            p.box.addWidget(Chart(vals));metrics.append(p)
        self.box.addWidget(AdaptiveGrid(metrics));self.note('Графики — последние 20 игр выбранного периода. Пропуски означают отсутствие данных.')
        self.title('Последние матчи')
        for record in history_model.saved(games,d,a.who)[:6]:self.box.addWidget(match_card(a,record))
        if not games:self.note('Для выбранного профиля ещё нет загруженных матчей.')
        self.box.addWidget(Button('Открыть всю историю матчей',lambda:a.navigate(1)))
        self.title('Частые чемпионы')
        champions=row()
        for r in snap['frequent']:
            c=r['champion'];p=Panel();p.box.addWidget(a.icons.label('champ',c,48));p.box.addWidget(Button(d.cn(c),lambda c=c,r=r:a.cp_pick(c,r['role'])));p.box.addWidget(Label(f"{r['stats']['n']} игр · {fmt(r['stats']['wr'])}% побед",10,'mute'));champions.layout().addWidget(p)
        self.box.addWidget(champions)
        pool=Panel();pool.box.addWidget(Label('Твой пул',17,'gold',serif=True))
        for role,champions in a.current_pool().items():pool.box.addWidget(Label(core.ROLE_RU[role]+': '+str(len(champions)),10,'mute'))
        self.box.addWidget(pool)
        recent,season=snap['recent'],snap['season'];worst=(None,0)
        if recent['n']>=5 and season['n']>recent['n']:
            for key in ('wr','kda','csm','vsm'):
                count='results' if key=='wr' else key+'_n';v,baseline=recent[key],season[key]
                if recent[count]>=5 and season[count]>recent[count] and v is not None and baseline and (baseline-v)/baseline>worst[1]:worst=key,(baseline-v)/baseline
        if worst[0]:self.box.addWidget(Label(a.TIPS[worst[0]],11,'warn'))
        self.note(f"Данные от {d.d.get('t','—')} · патч {d.d.get('patch','—')}");self.note(RIOT_NOTE);self.box.addStretch()
    def choose(self,who):self.app.s['who']=who;self.app.s.save();self.app.set_who(who);self.refresh()
    def period(self,key):self.app.s['home_period']=key;self.app.s.save();self.refresh()

class HistoryPage(Page):
    def __init__(self,app):
        super().__init__(app);self.source='saved';self.client_rows=[];self.client_owner=None;self.client_name='';self.generation=0;self.busy=False;self.query='';self.role='';self.queue='';self.result='all';self.limit=30;self.message=''
        self.title('Матчи и разбор');self.source_choice=combo({'saved':'Сохранённые матчи','client':'Из клиента LoL'},'saved',self.use_source)
        self.box.addWidget(row(self.source_choice,Button('Обновить из клиента',self.load_client),Button('Сайт со статистикой',app.open_site)))
        self.search=QLineEdit();self.search.setPlaceholderText('Поиск чемпиона или оппонента');self.search.textChanged.connect(self.search_changed)
        self.role_choice=combo({**core.ROLE_RU,'':'Все роли'},'',lambda v:self.set_filter('role',v))
        queues=sorted({r.get('q') for r in (app.player.games if app.player else []) if type(r.get('q')) is int})
        self.queue_choice=combo({'':'Все режимы',**{k:core.QUEUE_RU.get(k,str(k)) for k in queues}},'',lambda v:self.set_filter('queue',v))
        self.role_choice.setMinimumWidth(135);self.queue_choice.setMinimumWidth(165);self.box.addWidget(row(self.search,self.role_choice,self.queue_choice))
        self.result_choice=combo({'all':'Все результаты','win':'Победы','loss':'Поражения'},'all',lambda v:self.set_filter('result',v))
        self.box.addWidget(row(self.result_choice,Button('Сбросить',self.reset)))
        self.summary=Panel(horizontal=True);self.box.addWidget(self.summary);self.msg=Label('',10,'mute');self.box.addWidget(self.msg)
        self.matches=QWidget();self.matches_box=QVBoxLayout(self.matches);self.matches_box.setContentsMargins(0,0,0,0);self.matches_box.setSpacing(6);self.box.addWidget(self.matches)
        self.more=Button('Показать ещё',self.show_more);self.box.addWidget(self.more);self.box.addStretch();self.refresh()
    def search_changed(self,text):self.query=text;self.limit=30;self.refresh()
    def set_filter(self,key,value):setattr(self,key,value);self.limit=30;self.refresh()
    def reset(self):
        self.query='';self.role='';self.queue='';self.result='all';self.limit=30
        for widget in (self.search,self.role_choice,self.queue_choice,self.result_choice):widget.blockSignals(True)
        self.search.clear();self.role_choice.setCurrentIndex(self.role_choice.findData(''));self.queue_choice.setCurrentIndex(0);self.result_choice.setCurrentIndex(0)
        for widget in (self.search,self.role_choice,self.queue_choice,self.result_choice):widget.blockSignals(False)
        self.refresh()
    def show_more(self):self.limit+=30;self.refresh()
    def profile_changed(self):self.refresh()
    def account_changed(self,me):
        self.generation+=1;self.busy=False
        if self.client_owner!=(me or {}).get('puuid'):self.client_rows=[];self.client_owner=None
        self.refresh()
    def rows(self):return self.client_rows if self.source=='client' else history_model.saved(self.app.player.games if self.app.player else [],self.app.data,self.app.who)
    def use_source(self,key):
        self.source=key;self.limit=30
        if key=='client' and not self.client_rows:self.load_client()
        else:self.refresh()
    def refresh(self):
        rows=self.rows();self.filtered=history_model.filtered(rows,self.app.data,self.query,self.role,self.queue,self.result);stats=history_model.stats(self.filtered)
        clear_layout(self.summary.box)
        for title,value in [('МАТЧИ',str(stats['n'])),('ПОБЕДЫ',fmt(stats['wr'])+'%'),('KDA',fmt(stats['kda'],2)),('ФАРМ / МИН',fmt(stats['csm']))]:
            p=Panel(kind=None,padding=4);p.box.addWidget(Label(title,10,'mute'));p.box.addWidget(Label(value,30,bold=True,serif=True));self.summary.box.addWidget(p)
        self.msg.setText((self.message+' · ' if self.message else '')+f'Найдено {len(self.filtered)} из {len(rows)} · показано {min(self.limit,len(self.filtered))}')
        clear_layout(self.matches_box)
        for record in self.filtered[:self.limit]:self.matches_box.addWidget(match_card(self.app,record))
        if not self.filtered:self.matches_box.addWidget(Label('Матчей по выбранным условиям нет.',13,'mute'))
        self.more.setVisible(len(self.filtered)>self.limit)
    def load_client(self,background=False):
        if self.busy:return
        if not background:
            self.source='client';self.source_choice.blockSignals(True);self.source_choice.setCurrentIndex(1);self.source_choice.blockSignals(False)
        self.busy=True;self.generation+=1;token=self.generation;self.message='Загружаю историю…';self.refresh()
        def work():
            me=self.app.client.me() or {};pu=me.get('puuid')
            if not pu:raise RuntimeError('Клиент LoL недоступен. Предыдущая история сохранена.')
            games=self.app.client.history(pu,30)
            if games is None:raise RuntimeError('Клиент не отдал историю. Предыдущая история сохранена.')
            lp=core.lp_changes(games,self.app.lp_snaps(self.app.client.rank(pu),puuid=pu))
            return me,games,lp
        def done(value,error):
            if token!=self.generation:return
            self.busy=False
            if error:self.message=str(error)
            else:
                me,games,lp=value;current=(self.app.account or {}).get('puuid')
                if current and current!=me['puuid']:self.message='Аккаунт изменился. Обнови историю ещё раз.'
                else:self.client_rows=history_model.client(games,self.app.data,me['puuid'],lp);self.client_owner=me['puuid'];self.client_name=me.get('riot','');self.message='История обновлена'
            self.refresh()
        self.app.background(work,done)

class MatchDialog(QDialog):
    def __init__(self,app,record):
        super().__init__(app.window);self.app=app;self.record=record;self.closed=False;self.setWindowTitle('Разбор матча');self.resize(1100,760)
        self.box=QVBoxLayout(self);self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.body=Page(app);self.scroll.setWidget(self.body);self.box.addWidget(self.scroll)
        self.review=None;self.error='';self.loading=False
        if record['source']=='saved':self.review=history_model.saved_details(app.data.d,record.get('profile'),record.get('match_id'))
        if not self.review and record.get('gid'):
            self.loading=True
            def work():
                g=app.client.game(record['gid'])
                if not g or str(g.get('gameId'))!=str(record['gid']):raise RuntimeError('Клиент не отдал подробности этой игры.')
                return history_model.details(g,record.get('owner'),app.data)
            def done(value,error):
                if self.closed:return
                self.review=value;self.error=str(error) if error else '';self.loading=False;self.refresh()
            app.background(work,done)
        self.refresh()
    def closeEvent(self,event):self.closed=True;super().closeEvent(event)
    def refresh(self):
        b=self.body;b.clear();r=self.record;a=self.app;b.title(a.data.cn(r['champion'])+' · разбор матча');b.box.addWidget(equipment(a,r,32))
        b.box.addWidget(table(['K / D / A','Фарм / мин','Урон','Золото','Обзор','LP'],[[' / '.join(str(r.get(k)) if r.get(k) is not None else '—' for k in ('k','d','a')),fmt(r.get('csm')),r.get('dmg'),r.get('gold'),r.get('vis'),r.get('lp')]]))
        if self.loading:b.note('Загружаю состав из клиента…')
        elif self.error:b.note(self.error)
        if self.review:
            for text,tone in self.review.get('lines',[]):b.box.addWidget(Label(text,11,tone if tone in C else 'fg'))
            rows=self.review.get('rows') or []
            for team in dict.fromkeys(p.get('team') for p in rows):
                b.title('Команда '+str(team))
                for p in [x for x in rows if x.get('team')==team]:
                    panel=Panel(horizontal=True,padding=8);panel.box.addWidget(a.icons.label('champ',p.get('c'),40));panel.box.addWidget(Label(a.data.cn(p.get('c'))+' · '+str(p.get('name','')),11,bold=True),2)
                    panel.box.addWidget(Label(' / '.join(str(p.get(k)) if p.get(k) is not None else '—' for k in ('k','d','a')),13,serif=True))
                    panel.box.addWidget(equipment(a,p,24));panel.box.addWidget(Label(f"CS {p.get('cs','—')} · Урон {p.get('dmg','—')}\nЗолото {p.get('gold','—')} · Обзор {p.get('vis','—')}",10,'mute'));b.box.addWidget(panel)
        elif not self.loading:b.note('Полный состав и анализ отсутствуют в доступных данных. Показаны сохранённые показатели.')
        b.box.addStretch()

class PoolPage(Page):
    def __init__(self,app):
        super().__init__(app);self.rows,self.source=champion_pool.load_catalog(app.data);self.role='TOP';self.mode='all';self.query='';self.filters={};self.sort='name'
        self.title('Мой пул чемпионов');self.search=QLineEdit();self.search.setPlaceholderText('Найти чемпиона');self.search.textChanged.connect(lambda s:self.change('query',s))
        self.box.addWidget(row(combo(core.ROLE_RU,self.role,lambda v:self.change('role',v)),self.search,combo({'all':'Все чемпионы','role':'На выбранной роли','pool':'Мой пул'},self.mode,lambda v:self.change('mode',v)),combo({'name':'По имени','selected':'Выбранные сначала','year':'По году'},self.sort,lambda v:self.change('sort',v))))
        self.advanced=Panel();grid=QGridLayout();self.advanced.box.addLayout(grid)
        for i,(key,title) in enumerate([('classes','Класс'),*champion_pool.FIELDS]):
            opts={'':'Все: '+title}
            for option in champion_pool.options(self.rows,key):
                opts[option]=champion_pool.LABELS.get(str(option),str(option))
            c=combo(opts,'',lambda v,k=key:self.filter(k,v));grid.addWidget(c,i//4,i%4)
        self.advanced.hide();self.box.addWidget(row(Button('Дополнительные фильтры',lambda:self.advanced.setVisible(not self.advanced.isVisible())),Button('Сбросить фильтры',self.reset)));self.box.addWidget(self.advanced)
        self.msg=Label('',10,'mute');self.box.addWidget(self.msg)
        self.list=QListWidget();self.list.setViewMode(QListView.ViewMode.IconMode);self.list.setResizeMode(QListView.ResizeMode.Adjust);self.list.setMovement(QListView.Movement.Static);self.list.setIconSize(QSize(70,70));self.list.setGridSize(QSize(120,110));self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection);self.list.itemClicked.connect(self.toggle);self.list.setMinimumHeight(420);self.box.addWidget(self.list,1);self.refresh()
    def change(self,key,v):setattr(self,key,v);self.refresh()
    def filter(self,key,v):self.filters[key]=v;self.refresh()
    def reset(self):self.filters={};self.query='';self.search.clear();self.mode='all';self.refresh()
    def refresh(self):
        selected=self.app.current_pool();shown=champion_pool.filtered(self.rows,selected,self.role,self.query,self.mode,self.filters,self.sort);self.list.clear()
        for r in shown:
            chosen=r['id'] in selected[self.role];item=QListWidgetItem(self.app.icons.icon('champ',r['id'],70),('✓ ' if chosen else '')+r['name']);item.setData(Qt.ItemDataRole.UserRole,r['id']);item.setToolTip(r['name']+' · '+', '.join(core.ROLE_RU.get(x,x) for x in r['roles']));item.setSizeHint(QSize(116,106))
            if chosen:item.setBackground(QColor(C['raise']));item.setForeground(QColor(C['gold']))
            self.list.addItem(item)
        self.msg.setText(f'{len(shown)} чемпионов · в пуле роли {len(selected[self.role])} · нажатие добавляет или убирает')
    def toggle(self,item):
        c=item.data(Qt.ItemDataRole.UserRole);self.app.toggle_pool(c,self.role)
        selected=c in self.app.current_pool()[self.role];item.setText(('✓ ' if selected else '')+self.app.data.cn(c));item.setBackground(QColor(C['raise'] if selected else 'transparent'));item.setForeground(QColor(C['gold'] if selected else C['fg']))
        if self.mode=='pool':self.refresh()
