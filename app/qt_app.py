"""Полное настольное приложение LoL Helper на Qt. Tkinter не загружается."""
from __future__ import annotations
import os,sys,json,queue,threading,time,subprocess,urllib.request,base64,io,re
from PIL import Image
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QUrl
from PySide6.QtGui import QFontDatabase,QFont,QDesktopServices,QIcon,QShortcut,QKeySequence
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QStackedWidget,QScrollArea,QDialog,QMessageBox
import core,lcu,phone,player_evidence,champion_pool,render,app_config
from voice import Voice
from app_config import *
from app_services import ApplicationServices
from qt_ui.widgets import *
from qt_ui.pages import HomePage,HistoryPage,PoolPage,MatchDialog
from qt_ui.champion import ChampionPage
from qt_ui.settings import HintsPage,SettingsPage
from qt_ui.overlays import HintsOverlay,PerfOverlay,LaneOverlay,InventoryOverlay,ItemOverlay,TimersOverlay,ArenaOverlay
from qt_ui.tab_overlay import TabPlates
from qt_ui.dashboard import Dashboard

class Window(QMainWindow):
    def __init__(self,app):
        super().__init__();self.app=app;self.scheduler=Scheduler();self.after=self.scheduler.after;self.after_cancel=self.scheduler.after_cancel
    def closeEvent(self,event):self.app.shutdown();event.accept()
    def destroy(self):self.close()
    def clipboard_clear(self):QApplication.clipboard().clear()
    def clipboard_append(self,text):QApplication.clipboard().setText(text)

class App(ApplicationServices):
    def __init__(self,data,version,updater=None,*,offline=False,home=None,assets=None):
        self.qt=QApplication.instance() or QApplication(sys.argv[:1]);self.qt.setApplicationName('LoL Helper');self.qt.setOrganizationName('LoLHelper')
        self.offline=offline;self.stopping=threading.Event();self.errors=[]
        self.home=home or app_home();os.makedirs(self.home,exist_ok=True);self.s=Settings(self.home);app_config.LOG_HOME=self.home
        self.previous_exception_hook=sys.excepthook
        def exception_hook(kind,error,tb):
            self.errors.append(str(error));log_error('Qt',error)
            if hasattr(self,'status'):self.status.setText('Ошибка интерфейса: '+str(error))
        sys.excepthook=exception_hook
        self.data,self.version,self.updater=data,version,updater;core.OBJ.update(self.s['obj'])
        self.client=lcu.LCU();self.voice=Voice(self.home)
        self.q=queue.Queue();self.hidden=False;self.account=None;self.my_rank=None;self.ranks={};self.hists={};self.rank_pu={};self.hraw={};self.jg_cache={}
        self.evidence=player_evidence.Evidence();self.evidence_region=None;self.evidence_region_at=0;self.pus={};self.hist_exp=set()
        self.role_override=None;self.lola={};self.lola_state={};self.import_text='';self.cp_sel=None;self.phone_srv=None;self.player=None;self.engine=None
        self.draft=None;self.draft_sig=None;self.imported=None;self.scout={};self.last_game=None;self.result=None;self.keys_prev={};self.demo_on=False;self.pending_data=None;self.dash=None
        self.icons=Icons(assets);self.icons.settings=self.s;self.dialogs=[];self.pages={};self.ov={};self.tab={};self.active_page=0
        self.window=Window(self);self.root=self.window;self.root.scheduler.failed.connect(lambda error:self.errors.append(str(error)));self.window.setWindowTitle('LoL Helper '+version);self.window.setWindowIcon(QIcon(str(Path(bundle_dir())/'icon.png')));self.window.resize(1536,864);self.window.setMinimumSize(940,640)
        for folder in (Path(bundle_dir())/'fonts',Path(bundle_dir())/'qt_ui/fonts'):
            for font in folder.glob('*.ttf'):QFontDatabase.addApplicationFont(str(font))
        self.configure_theme();self.set_who(self.s['who'] or 'halch')
        self.create_overlays();self.build_window();self.sync_voice()
        self.shortcut=QShortcut(QKeySequence('Escape'),self.window);self.shortcut.activated.connect(self.stop_demo)
        if not offline:
            self.sync_phone();threading.Thread(target=self.poll,daemon=True,name='client-poll').start();threading.Thread(target=self.load_lanes,daemon=True,name='lane-data').start();self.root.after(300,self.drain);self.root.after(40,self.keys);self.root.after(1000,self.tick_ui)
        self.window.show()
    def configure_theme(self):
        C.clear();C.update(THEMES.get(self.s['theme'],THEMES['lol'])[1])
        if self.s['accent']!='theme':C['gold']=self.s['accent']
        F['font']=self.s['font'];self.qt.setProperty('uiScale',self.s['scale']/100);self.qt.setFont(QFont(self.s['font'],round(11*self.s['scale']/100)))
        self.qt.setStyleSheet(f'''
            QWidget {{color:{C['fg']};background:transparent;}}
            QMainWindow,QDialog {{background:{C['bg']};}}
            QScrollArea {{border:0;background:transparent;}}
            QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QTextEdit,QListWidget,QTableWidget {{background:{C['deep']};border:1px solid {C['line']};border-radius:7px;padding:6px;selection-background-color:{C['raise']};}}
            QComboBox QAbstractItemView {{background:{C['panel']};color:{C['fg']};selection-background-color:{C['raise']};}}
            QCheckBox {{padding:5px;spacing:7px;}}
            QCheckBox::indicator {{width:16px;height:16px;border:1px solid {C['line']};border-radius:3px;background:{C['deep']};}}
            QCheckBox::indicator:checked {{background:{C['gold']};border:1px solid {C['fg']};}}
            QHeaderView::section {{background:{C['panel']};color:{C['mute']};border:0;padding:7px;}}
            QTableWidget {{alternate-background-color:{C['panel']};gridline-color:{C['line']};}}
            QScrollBar:vertical {{background:{C['deep']};width:9px;border:0;}}
            QScrollBar::handle:vertical {{background:{C['raise']};min-height:24px;border-radius:4px;}}
            QToolTip {{background:{C['panel']};color:{C['fg']};border:1px solid {C['line']};}}
        ''')
        surface.cache_clear()
    def build_window(self):
        old=self.window.centralWidget()
        if old:old.deleteLater()
        self.shell=Shell();self.window.setCentralWidget(self.shell);rail=Panel(kind=None,padding=8);rail.setFixedWidth(192);self.shell.box.addWidget(rail)
        rail.box.addWidget(Label('⬡  LOL HELPER',13,'gold',bold=True,serif=True));rail.box.addSpacing(12);self.nav_buttons={}
        for i in (0,1,10,2,3,4,5,6,7,8,9):
            if i in (0,3):rail.box.addWidget(Label('ИГРА' if i==0 else 'НАСТРОЙКИ',9,'mute'))
            if i==9:rail.box.addStretch()
            name,icon=self.NAV[i];button=NavButton(name,icon,lambda i=i:self.navigate(i));rail.box.addWidget(button);self.nav_buttons[i]=button
        rail.box.addWidget(Label(self.version,9,'mute'))
        right=QWidget();b=QVBoxLayout(right);b.setContentsMargins(12,0,0,0);self.shell.box.addWidget(right,1)
        self.page_title=Label('',21,'gold',serif=True);self.status_dot=Label('●',10,'good');self.status=Label('Ищу клиент League of Legends…' if not self.offline else 'Автономная проверка · клиент отключён',9,'mute');header=QWidget();header_box=QHBoxLayout(header);header_box.setContentsMargins(0,0,0,0);header_box.addWidget(self.page_title,1);header_box.addWidget(self.status_dot);header_box.addWidget(self.status);b.addWidget(header)
        self.banner=Panel(horizontal=True,padding=7);self.banner_label=Label('');self.banner.box.addWidget(self.banner_label,1);self.banner_button=Button('Обновить');self.banner.box.addWidget(self.banner_button);self.banner.hide();b.addWidget(self.banner)
        self.stack=QStackedWidget();b.addWidget(self.stack,1);self.pages={};self.scrolls={}
        # Construct each page once. Navigation preserves filters and scroll positions.
        kinds={0:lambda:HomePage(self),1:lambda:HistoryPage(self),2:lambda:ChampionPage(self),3:lambda:HintsPage(self),10:lambda:PoolPage(self)}
        for i in range(11):
            page=kinds[i]() if i in kinds else SettingsPage(self,{4:'windows',5:'look',6:'voice',7:'keys',8:'timers',9:'updates'}[i]);self.pages[i]=page
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(page);self.scrolls[i]=scroll;self.stack.addWidget(scroll)
        self.home_view=self.pages[0];self.history_view=self.pages[1];self.champion_view=self.pages[2];self.hints_view=self.pages[3];self.pool_view=self.pages[10]
        self.home_view.refresh();self.navigate(self.active_page)
        if getattr(self,'upd',None):self.update_state(*self.upd)
    def navigate(self,index):
        self.active_page=index;self.stack.setCurrentIndex(index);self.page_title.setText(self.NAV[index][0].upper())
        for i,b in self.nav_buttons.items():b.active=i==index;b.update()
    def create_overlays(self):
        _,(pw,ph),_=screens()
        classes={'hints':HintsOverlay,'perf':PerfOverlay,'lane':LaneOverlay,'inventory':InventoryOverlay,'item':ItemOverlay,'timers':TimersOverlay,'arena':ArenaOverlay}
        defaults={'hints':(40,int(ph*.3)),'perf':(pw-330,80),'lane':(pw-330,300),'inventory':(max(40,pw-650),80),'item':(pw-330,400),'timers':(pw-330,490),'arena':(pw-330,80)}
        self.ov={key:cls(self,defaults[key]) for key,cls in classes.items()};self.tab={'tab':TabPlates(self)}
    def fs(self,n):return max(7,round(n*self.s['scale']/100))
    def pimg(self,group,key,k=1,gray=False,ring=None):return self.icons.pil(group,key,max(12,int(self.s['icon']*k*self.s['scale']/100)),gray)
    def background(self,work,done):
        def job():
            try:value,error=work(),None
            except Exception as exc:value,error=None,exc;log_error('фоновая задача Qt',exc)
            if not self.stopping.is_set():self.root.after(0,lambda:done(value,error))
        threading.Thread(target=job,daemon=True).start()
    def sync_voice(self):
        for key in ('voice','volume','rate','master','beep_volume','sound'):setattr(self.voice,key,self.s[key])
        if not self.offline:self.voice.warm()
    def lola_fetch(self,kind,champ,role):
        if self.offline:return self.lola.get((champ,role) if kind=='build' else (kind,champ,role))
        return super().lola_fetch(kind,champ,role)
    def lola_matchup(self,c,r,o):
        if self.offline:return self.lola.get(('matchup',c,r,o))
        return super().lola_matchup(c,r,o)
    def offmeta_build(self,c,r):
        if self.offline:return self.lola.get(('offmeta',c,r))
        return super().offmeta_build(c,r)
    def player_builds(self,c,r):
        if self.offline:return self.lola.get(('players',c,r))
        return super().player_builds(c,r)
    def ensure_home_icon(self,icon):
        if self.offline:return
        key=str(icon);pending=self.__dict__.setdefault('_home_icons',set());failed=self.__dict__.setdefault('_home_icon_failures',{})
        if not key.isdigit() or key in self.icons.a.get('profile',{}) or key in pending or time.time()-failed.get(key,0)<300:return
        pending.add(key)
        def work():
            value=self.client.image(f'/lol-game-data/assets/v1/profile-icons/{key}.jpg')
            patch=self.data.d.get('patch','')
            if not value and re.fullmatch(r'\d+\.\d+\.\d+',patch):
                with urllib.request.urlopen(f'https://ddragon.leagueoflegends.com/cdn/{patch}/img/profileicon/{key}.png',timeout=8) as response:value=response.read(1_000_001)
            if not isinstance(value,bytes) or len(value)>1_000_000:raise ValueError('Иконка профиля недоступна')
            with Image.open(io.BytesIO(value)) as image:image.verify()
            return value
        def done(value,error):
            pending.discard(key)
            if error:failed[key]=time.time();return
            self.icons.a.setdefault('profile',{})[key]=base64.b64encode(value).decode();self.icons.pil.cache_clear();self.home_fill()
        self.background(work,done)
    def panel_sync(self):
        self.status_dot.configure(fg=C['good'] if self.account else C['mute'])
        if not self.last_game and not self.draft:self.status.setText('Клиент League of Legends подключён' if self.account else 'Клиент League of Legends недоступен')
        self.home_fill()
    def home_fill(self):
        if hasattr(self,'home_view'):self.home_view.refresh()
    def cp_pick(self,champ,role=None):self.champion_view.choose(champ,role);self.navigate(2)
    def cp_show(self):self.champion_view.refresh()
    def hist_refresh(self):self.history_view.load_client(background=True)
    def open_record(self,record):
        dialog=MatchDialog(self,record);self.dialogs.append(dialog);dialog.finished.connect(lambda _:self.dialogs.remove(dialog) if dialog in self.dialogs else None);dialog.show()
    def show_player_history(self,pu):
        if not pu:self.status.setText('История этого игрока недоступна');return
        def done(value,error):
            if error:self.status.setText('История недоступна: '+str(error));return
            import history_model
            dialog=QDialog(self.window);dialog.setWindowTitle('История игрока');dialog.resize(850,650);layout=QVBoxLayout(dialog);scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();box=QVBoxLayout(body)
            from qt_ui.pages import match_card
            for record in history_model.client(value or [],self.data,pu):box.addWidget(match_card(self,record))
            if not value:box.addWidget(Label('История недоступна'))
            scroll.setWidget(body);layout.addWidget(scroll);self.dialogs.append(dialog);dialog.show()
        self.background(lambda:self.hraw.get(pu) or self.client.history(pu,20),done)
    def open_dash(self):
        if not self.dash:self.dash=Dashboard(self)
        self.dash._manual_hidden=False;self.dash.deiconify();self.dash.lift()
    def sync_phone(self,restart=False):
        if self.offline:return
        if self.phone_srv and (restart or not self.s['phone']):self.phone_srv.stop();self.phone_srv=None
        if self.s['phone'] and not self.phone_srv:
            try:
                self.phone_srv=phone.PhoneServer(self.s['phone_port'],lambda:self.root.after(0,self.do_import),self.s['phone_token'] or None);self.s['phone_token']=self.phone_srv.token;self.s.save()
            except Exception as error:log_error('сервер телефона',error);self.status.setText('Не удалось запустить телефон: '+str(error))
        if hasattr(self,'phone_lbl'):self.phone_lbl.setText(self.phone_srv.url if self.phone_srv else 'Выключено')
    def set_import_msg(self,text):
        self.import_text=text
        if self.phone_srv and self.phone_srv.state.get('mode')=='draft':self.phone_srv.state['imp']=text
        if self.dash and self.dash.import_lbl:self.dash.import_lbl.setText(text)
    def toggle_demo(self):
        self.demo_on=not self.demo_on;self.keys_prev['drag']=self.demo_on;self._demo_epoch=getattr(self,'_demo_epoch',0)+1;epoch=self._demo_epoch
        if hasattr(self,'demo_btn'):self.demo_btn.setText('Завершить расстановку (Esc)' if self.demo_on else 'Показать все виджеты для расстановки')
        if not self.demo_on:self.set_unlocked(False);return
        pending=iter(list(self.tab)+list(self.ov))
        def show_next():
            if not self.demo_on or epoch!=self._demo_epoch:return
            key=next(pending,None)
            if key is None:return
            self.set_unlocked(True,(key,));self.root.after(16,show_next)
        self.root.after(0,show_next)
    def set_tab(self,key,value):
        self.s[key]=value;self.s.save()
        for w in self.tab.values():
            w.auto_layout=None;w._auto_cancel.set();w._auto_epoch+=1
            if self.last_game:w.show(self.last_game)
            elif self.demo_on:w.demo()
    def preset_layout(self,kind):
        gx,gy,gw,gh=game_rect();k=gh/1080;cx=gx+gw/2;half=gw/2 if kind=='edges' else min(gw/2,gh*16/9/2);left,right=cx-half+24*k,cx+half-340*k
        positions={'hints':(left,gy+.3*gh),'perf':(right,gy+.1*gh),'lane':(right,gy+.3*gh),'item':(right,gy+.4*gh),'timers':(right,gy+.49*gh),'inventory':(max(gx,right-310*k),gy+.1*gh),'arena':(right,gy+.1*gh)}
        for key,xy in positions.items():self.layout()[key]=[int(v) for v in xy];self.ov[key].move_physical(*self.layout()[key])
        self.s.save()
    def reset_layout(self):
        self.s['layout'].pop(screens()[0],None);self.s.save();self.preset_layout('edges')
    def apply_settings(self):
        index=self.active_page;self.stop_demo();self.configure_theme();self.sync_voice();core.OBJ.update(self.s['obj'])
        for w in list(self.ov.values())+list(self.tab.values()):w.close()
        self.create_overlays();self.build_window();self.navigate(index);self.sync_phone()
        if self.dash:
            self.dash.draft_sig=None;self.draft_sig=None
            if self.draft:self.on_draft(self.draft)
            elif self.last_game:self.dash.reset();self.dash.show(self.last_game,self.scout,self.ranks,self.hists)
            else:self.dash.idle()
        self.apply_visibility()
    def offer_update(self,tag,start):self.update_state('Доступна версия '+tag,start,'Обновить')
    def update_state(self,text,action=None,label=None):
        self.upd=(text,action,label);self.banner_label.setText(text);self.banner.show();self.banner_button.setText(label or 'Обновить');self.banner_button.setVisible(bool(action))
        try:self.banner_button.clicked.disconnect()
        except RuntimeError:pass
        if action:self.banner_button.clicked.connect(lambda _:action())
    def check_updates(self,manual=False):
        if self.updater:self.background(lambda:self.updater(self),lambda result,error:self.upd_msg.setText(str(error or result)))
    def open_url(self,url):QDesktopServices.openUrl(QUrl(url))
    def open_site(self,game=None):
        args=[sys.executable,'--site'] if getattr(sys,'frozen',False) else [sys.executable,str(Path(bundle_dir())/'lolhelper.py'),'--site']
        if game:args.append('--game='+str(game))
        env={k:v for k,v in os.environ.items() if not k.startswith(('_PYI','_MEI'))};env['PYINSTALLER_RESET_ENVIRONMENT']='1'
        try:subprocess.Popen(args,env=env)
        except Exception as error:QMessageBox.warning(self.window,'Сайт',str(error))
    def open_last_game(self):
        def work():
            pu=(self.account or {}).get('puuid');h=self.client.history(pu,1) if pu else None;return f"EUW1_{h[0]['gid']}" if h else None
        self.background(work,lambda game,error:self.open_site(game))
    def copy_report(self):
        self.background(self.report_text,lambda text,error:(QApplication.clipboard().setText(text or str(error)),self.status.setText('Диагностика скопирована')))
    def show_arena_post(self,res):
        stats=core.arena_stats(self.arena_games()) or {};body=Page(self);body.title(f"{res.get('place','—')}-е место · Арена");body.box.addWidget(table(['Показатель','Сейчас','Обычно'],[['Место',res.get('place'),stats.get('avg')],['Урон',res.get('dmg'),stats.get('dmg')],['Счёт',f"{res['k']}/{res['d']}/{res['a']}",'—']]));self.show_dialog('Итог Арены',body)
    def show_postgame(self,res,result):
        body=Page(self);body.title({'Win':'Победа','Lose':'Поражение'}.get(result,'Игра завершена')+' · '+self.data.cn(res['me']['c']))
        for name,v,target,ok,dec in res['goals']:body.box.addWidget(Label(f"{'✓' if ok else '✗'} {name}: {v:.{dec}f} · цель {target}",13,'good' if ok else 'bad'))
        for name,v,target,tip in res.get('mistakes',[]):body.box.addWidget(Label(name+' · '+tip,11,'warn'))
        body.box.addWidget(Label(f"Подсказок за игру: {len(res.get('hints',[]))}",10,'mute'));body.box.addWidget(Button('Разбор на сайте',self.open_last_game));dialog=self.show_dialog('Итог игры',body);self.postgame_timeline(body,res,dialog)
    def show_dialog(self,title,body):
        d=QDialog(self.window);d.setWindowTitle(title);d.resize(950,720);b=QVBoxLayout(d);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(body);b.addWidget(scroll);self.dialogs.append(d);d.show();return d
    def postgame_timeline(self,body,res,dialog):
        note=Label('Ожидаю таймлайн из клиента…',10,'mute');body.box.addWidget(note);pu=(self.account or {}).get('puuid');started=time.time()
        def attempt(tries=0):
            if not dialog.isVisible() or self.offline:return
            def work():
                h=self.client.history(pu,1) if pu else None
                if not h or h[0].get('t',0)/1000<started-7200 or h[0]['champ']!=int(self.cid(res['me']['c']) or 0):return None
                gid=h[0]['gid'];tl,gm=self.client.timeline(gid),self.client.game(gid);marks=core.timeline_marks(tl,gm,pu);gs=core.gold_series(tl,gm,pu,int(self.cid(res.get('opp')) or 0) if res.get('opp') else None);return marks,gs
            def done(value,error):
                if not dialog.isVisible():return
                if not value or value[0] is None:
                    if tries<6 and pu:self.root.after(20000,lambda:attempt(tries+1))
                    else:note.setText('Клиент не отдал таймлайн')
                    return
                marks,gs=value;picture=QLabel();picture.setPixmap(pixmap(render.death_map(marks,280,C)));body.box.addWidget(picture);note.setText('Карта смертей: ✕ смерти · ● убийства и помощь')
                if gs:
                    picture=QLabel();picture.setPixmap(pixmap(render.gold_chart(gs,400,150,C)));body.box.addWidget(picture);body.box.addWidget(Label(core.gold_note(gs),10,'mute'))
            self.background(work,done)
        self.root.after(15000,attempt)
    def tick_ui(self):
        self.ov['hints'].show()
        if self.dash:self.dash.tick()
        self.root.after(1000,self.tick_ui)
    def shutdown(self):
        if self.stopping.is_set():return
        self.stopping.set();self.root.scheduler.stop();self._import_generation=getattr(self,'_import_generation',0)+1
        for w in list(self.ov.values())+list(self.tab.values()):w.close()
        if self.phone_srv:self.phone_srv.stop();self.phone_srv=None
        if self.dash:self.dash.hide();self.dash.deleteLater();self.dash=None
        for d in list(self.dialogs):d.close()
        self.dialogs=[];self.voice.muted=True;sys.excepthook=self.previous_exception_hook
    def run(self):return self.qt.exec()
