"""Настройки Qt с прежними ключами settings.json."""
import json,os,urllib.request
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialog,QVBoxLayout,QTextEdit,QLineEdit,QSlider,QSpinBox,QDoubleSpinBox,QFileDialog,QKeySequenceEdit,QMessageBox
from .widgets import *
from app_config import *
from voice import VOICES,SOUNDS
from settings_validation import clock_seconds
import core,champion_pool

class HintsPage(Page):
    def __init__(self,app):
        super().__init__(app);self.query='';self.scope='all';self.mode='all'
        self.title('Подсказки');search=QLineEdit();search.setPlaceholderText('Поиск по названию, условиям и своему тексту');search.textChanged.connect(self.search)
        self.box.addWidget(row(combo(core.ROLE_RU,app.s['hint_preset'],self.role),search,combo({'all':'Все','role':'Для роли','common':'Общие'},'all',lambda v:self.filter('scope',v)),combo({'all':'Все режимы',**MODES},'all',lambda v:self.filter('mode',v))))
        self.box.addWidget(row(Label('Изменить только показанные:',10,'mute'),*[Button(n,lambda k=k:self.set_all(k)) for k,n in MODES.items()]))
        self.box.addWidget(Button('Режимы по умолчанию',self.reset));self.body=QWidget();self.body_box=QVBoxLayout(self.body);self.body_box.setContentsMargins(0,0,0,0);self.box.addWidget(self.body);self.box.addStretch();self.refresh()
    def search(self,q):self.query=q;self.refresh()
    def filter(self,key,v):setattr(self,key,v);self.refresh()
    def role(self,role):self.app.s['hint_preset']=role;self.app.s.save();self.refresh()
    def visible(self):
        role=self.app.s['hint_preset'];q=champion_pool.norm(self.query);result=[]
        for h in core.HINTS:
            hid,group,name,default,cooldown=h;rh=hid in core.HINT_ROLES
            if rh and role not in core.HINT_ROLES[hid]:continue
            if self.scope=='role' and not rh or self.scope=='common' and rh:continue
            if self.mode!='all' and self.app.hint_mode(hid)!=self.mode:continue
            custom=self.app.s['hint_text'].get(hid,{})
            if q and q not in champion_pool.norm(' '.join([name,group,core.HINT_DESC.get(hid,''),custom.get('text',''),custom.get('say','')])):continue
            result.append(h)
        return result
    def set_mode(self,hid,mode,save=True):
        if hid in core.HINT_ROLES:self.app.s['hints_role'].setdefault(self.app.s['hint_preset'],{})[hid]=mode
        else:self.app.s['hints'][hid]=mode
        if save:self.app.s.save()
    def set_all(self,mode):
        for h in self.visible():self.set_mode(h[0],mode,False)
        self.app.s.save();self.refresh()
    def reset(self):self.app.s.reset(SECTIONS['hints']);self.refresh()
    def refresh(self):
        clear_layout(self.body_box)
        for hid,group,name,default,cooldown in self.visible():
            p=Panel();p.box.addWidget(row(Label(name,13,bold=True),combo(MODES,self.app.hint_mode(hid),lambda v,hid=hid:self.set_mode(hid,v)),Button('Проверить',lambda hid=hid,name=name:self.app.test_hint(hid,name)),Button('Свой текст',lambda hid=hid,name=name:self.edit(hid,name))))
            p.box.addWidget(Label(group+' · интервал '+str(cooldown)+' с',9,'mute'));detail=Label(core.HINT_DESC.get(hid,name),11,'mute');detail.hide();p.box.addWidget(Button('Условия срабатывания',lambda detail=detail:detail.setVisible(not detail.isVisible())));p.box.addWidget(detail);self.body_box.addWidget(p)
    def edit(self,hid,name):
        d=QDialog(self.app.window);d.setWindowTitle('Свой текст подсказки');d.resize(700,480);b=QVBoxLayout(d);b.addWidget(Label(name,17,'gold'));b.addWidget(Label('{текст} подставляет исходную фразу. Пустые поля возвращают стандартный текст.',10,'mute'))
        old=self.app.s['hint_text'].get(hid,{});text=QTextEdit(old.get('text',''));say=QTextEdit(old.get('say',''));b.addWidget(Label('На экране'));b.addWidget(text);b.addWidget(Label('Для голоса'));b.addWidget(say)
        def save():
            t,s=text.toPlainText().strip(),say.toPlainText().strip()
            if t or s:self.app.s['hint_text'][hid]={'text':t,'say':s}
            else:self.app.s['hint_text'].pop(hid,None)
            self.app.s.save();d.accept()
        b.addWidget(row(Button('Сохранить',save),Button('Исходный текст',lambda:(text.clear(),say.clear())),Button('Отмена',d.reject)));d.exec()

class SettingsPage(Page):
    def __init__(self,app,kind):super().__init__(app);self.kind=kind;self.refresh()
    def section(self,name):p=Panel();p.box.addWidget(Label(name,16,'gold',serif=True));self.box.addWidget(p);return p.box
    def set(self,key,value,group=None):
        a=self.app
        if group:a.s[group][key]=value
        else:a.s[key]=value
        a.s.save()
        if self.kind=='voice':a.sync_voice()
        if self.kind=='windows':
            a.apply_visibility()
            if a.demo_on:a.set_unlocked(True)
        if key=='phone':a.sync_phone()
    def number(self,b,title,key,lo,hi,decimals=0):
        w=QDoubleSpinBox() if decimals else QSpinBox();w.setRange(lo,hi)
        if decimals:w.setDecimals(decimals);w.setSingleStep(.1)
        w.setValue(self.app.s[key]);w.valueChanged.connect(lambda value:self.set(key,value));b.addWidget(row(Label(title),w))
    def reset(self,section):
        self.app.s.reset(SECTIONS[section]);self.app.apply_settings();self.refresh()
    def refresh(self):
        self.clear();getattr(self,'build_'+self.kind)();self.box.addStretch()
    def build_windows(self):
        a=self.app;b=self.section('Виджеты поверх игры')
        for key,title in WIDGETS.items():b.addWidget(row(check(title,a.s['widgets'].get(key),lambda v,k=key:self.set(k,v,'widgets')),check('Закреплён',a.s['widget_pins'].get(key),lambda v,k=key:self.pin(k,v))))
        a.demo_btn=Button('Завершить расстановку (Esc)' if a.demo_on else 'Показать все виджеты для расстановки',a.toggle_demo);b.addWidget(a.demo_btn)
        b.addWidget(row(Button('По краям окна игры',lambda:a.preset_layout('edges')),Button('По краям области 16:9',lambda:a.preset_layout('center')),Button('Сбросить позиции',a.reset_layout)))
        b=self.section('Показатели')
        for key,title in [('csm','Фарм / мин'),('gpm','Золото / мин'),('kda','KDA'),('kp','Участие'),('vsm','Обзор / мин')]:b.addWidget(check(title,a.s['perf']['metrics'].get(key),lambda v,k=key:self.perf('metrics',v,k)))
        b.addWidget(combo({'vertical':'В столбец','horizontal':'В строку'},a.s['perf']['layout'],lambda v:self.perf('layout',v)))
        b.addWidget(combo({'norm':'Сравнение с твоей нормой','emerald':'Сравнение с Изумруд+'},a.s['perf']['compare'],lambda v:self.perf('compare',v)))
        b=self.section('Tab и второе окно')
        for key,title in [('scoreboard','Перевес поверх таблицы Tab'),('tab_auto','Автоматически находить таблицу Tab'),('dashboard','Окно драфта и игры'),('postgame','Послематчевый разбор')]:b.addWidget(check(title,a.s[key],lambda v,k=key:self.set(k,v)))
        a.tab_auto_label=Label(next(iter(a.tab.values())).auto_status if a.tab else 'Ожидаю Tab',10,'mute');b.addWidget(a.tab_auto_label)
        b.addWidget(Label('Ручная настройка: отключи автоподгонку, удерживай Tab + Alt и тяни ручку. Shift меняет размер. Остальная поверхность пропускает клики.',10,'mute'))
        b.addWidget(row(Button('Вернуть рамку Tab',lambda:a.set_tab('tab_rect',None)),Button('Открыть второе окно',a.open_dash)))
        b.addWidget(Button('Все настройки окон по умолчанию',lambda:self.reset('windows')))
    def pin(self,key,value):self.set(key,value,'widget_pins');self.app.ov[key].unlock(self.app.ov[key].unlocked)
    def perf(self,key,value,sub=None):
        if sub:self.app.s['perf'][key][sub]=value
        else:self.app.s['perf'][key]=value
        self.app.s.save()
    def build_look(self):
        a=self.app;b=self.section('Оформление')
        for title,key,options in [('Тема','theme',{k:v[0] for k,v in THEMES.items()}),('Акцент','accent',ACCENTS),('Шрифт','font',FONTS),('Фон виджетов','widget_bg',{'panel':'Плашка','none':'Без фона'})]:b.addWidget(row(Label(title),combo(options,a.s[key],lambda v,k=key:self.set(k,v))))
        self.number(b,'Масштаб интерфейса, %','scale',70,170);self.number(b,'Размер иконок','icon',20,64);self.number(b,'Непрозрачность виджетов, %','alpha',30,100)
        b.addWidget(Button('Применить оформление',a.apply_settings));b=self.section('Что показывать')
        for key,title in SHOW.items():b.addWidget(check(title,a.s['show'].get(key),lambda v,k=key:self.set(k,v,'show')))
        b.addWidget(Button('Вид по умолчанию',lambda:self.reset('look')))
    def build_voice(self):
        a=self.app;b=self.section('Голос подсказок');self.voice_msg=Label('',10,'mute');a.voice.on_error=lambda message:a.root.after(0,lambda:self.voice_msg.setText(message))
        b.addWidget(row(combo({k:v+('' if a.voice.ready(k) else ' (скачать)') for k,v in VOICES.items()},a.s['voice'],self.pick_voice),Button('Прослушать',lambda:a.voice.say('Окно ганка через двадцать секунд, поставь вард в реку',force=True))))
        b.addWidget(self.voice_msg)
        for title,key in [('Общая громкость','master'),('Голос','volume'),('Сигнал','beep_volume')]:self.number(b,title,key,0,100)
        self.number(b,'Скорость речи','rate',.7,1.6,1);b.addWidget(row(combo({k:v[0] for k,v in SOUNDS.items()},a.s['sound'],lambda v:self.set('sound',v)),Button('Проверить сигнал',lambda:a.voice.beep(force=True))))
        b.addWidget(Button('Звук по умолчанию',lambda:self.reset('voice')))
    def pick_voice(self,key):
        a=self.app
        if a.voice.ready(key):self.set('voice',key);self.voice_msg.setText('Выбран '+VOICES[key]);return
        self.voice_msg.setText('Скачиваю '+VOICES[key]+'…')
        def work():a.voice.fetch(key,lambda p:a.root.after(0,lambda:self.voice_msg.setText(f'Загрузка: {p*100:.0f}%')))
        def done(_,error):
            if error:self.voice_msg.setText('Не удалось скачать: '+str(error))
            else:self.set('voice',key);self.voice_msg.setText('Голос установлен: '+VOICES[key])
        a.background(work,done)
    def build_keys(self):
        b=self.section('Горячие клавиши');a=self.app
        for key,title in [('mute','Выключить звук'),('hide','Скрыть виджеты'),('scoreboard','Таблица Tab'),('drag','Перемещение виджетов')]:
            field=QLineEdit(a.s['keys'][key]);field.setPlaceholderText('ctrl+shift+m, tab, alt…')
            field.editingFinished.connect(lambda k=key,f=field:self.save_key(k,f));b.addWidget(row(Label(title),field))
        b.addWidget(Label('Удерживай клавишу перемещения для расстановки. Закреплённые виджеты пропускают клики; открепление — кнопкой в углу.',10,'mute'));b.addWidget(Button('Клавиши по умолчанию',lambda:self.reset('keys')))
    def save_key(self,key,field):
        value=field.text().strip().lower();parts=value.split('+')
        if not value or any(p not in VK for p in parts):field.setText(self.app.s['keys'][key]);self.app.status.setText('Неизвестная клавиша. Пример: ctrl+shift+m');return
        self.set(key,value,'keys')
    def build_timers(self):
        b=self.section('Время объектов');a=self.app;names={'dragon_first':'Первый дракон','dragon_respawn':'Дракон: возрождение','elder_respawn':'Древний дракон: возрождение','grubs':'Личинки Бездны','herald':'Герольд','baron_first':'Барон','baron_respawn':'Барон: возрождение','inhib_respawn':'Ингибитор: восстановление'}
        for key,title in names.items():
            field=QLineEdit(core.mmss(a.s['obj'].get(key,core.OBJ[key])));field.editingFinished.connect(lambda k=key,f=field:self.timer(k,f));b.addWidget(row(Label(title),field))
        b.addWidget(Button('Таймеры по умолчанию',lambda:self.reset('obj')))
    def timer(self,key,field):
        try:value=clock_seconds(field.text(),positive=key.endswith('respawn'))
        except ValueError as error:field.setText(core.mmss(self.app.s['obj'][key]));self.app.status.setText(str(error));return
        self.set(key,value,'obj');core.OBJ.update(self.app.s['obj'])
    def build_updates(self):
        a=self.app;b=self.section('Обновления · '+a.version);b.addWidget(check('Проверять обновления автоматически',a.s['auto_update'],lambda v:self.set('auto_update',v)));b.addWidget(Button('Проверить обновления',lambda:a.check_updates(True)));a.upd_msg=Label('',11,'mute');b.addWidget(a.upd_msg)
        b.addWidget(row(Button('Список выпусков',lambda:a.open_url(RELEASES)),Button('Скопировать диагностику',a.copy_report),Button('Сохранить настройки',self.backup_save),Button('Восстановить настройки',self.backup_load)))
        b=self.section('Драфт на телефоне');b.addWidget(check('Разрешить просмотр драфта в домашней сети',a.s['phone'],lambda v:self.set('phone',v)));self.number(b,'Порт','phone_port',1024,65535);a.phone_lbl=Label(a.phone_srv.url if a.phone_srv else 'Выключено',10,'mute');b.addWidget(a.phone_lbl);b.addWidget(Button('Применить порт',lambda:a.sync_phone(restart=True)))
        b.addWidget(Label('Первоначальные настройки версии 1 сохранены в settings.json.pre-v2. Импорт рун и предметов на телефоне выполняется только по твоему действию.',10,'mute'));b.addWidget(Label(RIOT_NOTE,8,'mute'))
    def backup_save(self):
        path,_=QFileDialog.getSaveFileName(self,'Сохранить настройки','LoLHelper-settings.json','JSON (*.json)')
        if path:
            try:
                with open(path,'w',encoding='utf-8') as f:json.dump(self.app.s.export(self.app.version),f,ensure_ascii=False,indent=2)
                self.app.status.setText('Настройки сохранены')
            except OSError as e:QMessageBox.warning(self,'Не удалось сохранить',str(e))
    def backup_load(self):
        path,_=QFileDialog.getOpenFileName(self,'Восстановить настройки','','JSON (*.json)')
        if path:
            try:
                with open(path,encoding='utf-8') as f:self.app.s.load_backup(json.load(f))
                self.app.apply_settings();self.refresh();self.app.status.setText('Настройки восстановлены')
            except (ValueError,OSError) as e:QMessageBox.warning(self,'Не удалось восстановить',str(e))
