"""Проверка настоящих Qt-окон в изолированном профиле, без игры и сети."""
import io,json,os,sys,tempfile,time,traceback
from pathlib import Path
from unittest.mock import Mock,patch
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QCheckBox,QDialog,QLabel,QPushButton
import core,lcu,lolhelper
from app_config import THEMES
from qt_app import App


def live_fixture(data):
    champions=['Sett','RekSai','Viktor','Jinx','Rakan','Darius','LeeSin','Ahri','Caitlyn','Lux']
    snap={'activePlayer':{'riotId':'Halch#9200','currentGold':850},'gameData':{'gameTime':900,'gameMode':'CLASSIC','mapNumber':11},'events':{'Events':[]},'allPlayers':[]}
    for i,c in enumerate(champions):snap['allPlayers'].append({'riotId':'Halch#9200' if i==0 else f'Проверка{i}#1','rawChampionName':'game_character_displayname_'+c,'team':'ORDER' if i<5 else 'CHAOS','position':core.ROLES[i%5],'level':11,'isDead':False,'respawnTimer':0,'items':[{'itemID':1055,'count':1},{'itemID':3006,'count':1}],'scores':{'kills':i%4,'deaths':2,'assists':5,'creepScore':95+i*4,'wardScore':12},'summonerSpells':{'summonerSpellOne':{'rawDisplayName':'SummonerFlash'},'summonerSpellTwo':{'rawDisplayName':'SummonerSmite' if i%5==1 else 'SummonerTeleport'}}})
    return core.Game(snap,data)


def verify_audit(app, check, cs):
    app.s['dashboard'] = False
    app.set_dashboard_enabled()
    app.on_draft(dict(cs,locked=False))
    app.on_loading([])
    check('Выключенное второе окно остаётся скрытым', not app.dash.isVisible())
    app.open_dash()
    check('Второе окно открывается вручную', app.dash.isVisible() and app.dash.mode=='draft')

    def flush():
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        QTest.qWait(30)
    flush()
    boxes = {control.text():control for control in app.dash.findChildren(QCheckBox)}
    boxes['Руны'].click()
    check('Состав импорта не меняет автоматику', not boxes['Автоимпорт после подтверждения'].isChecked()
          and not app.s['auto_import'] and app.s['auto_parts']['runes'])
    with patch.object(app,'do_import') as write:
        app.on_draft(cs)
        check('При выключенной автоматике подтверждение не вызывает импорт', not write.called)

    app.on_draft(None)

    record = app.history_view.filtered[0]
    previous = len(app.window.findChildren(QDialog))
    for _ in range(3):
        app.open_record(record)
        app.dialogs[-1].close()
        flush()
    check('Закрытые диалоги удалены', len(app.window.findChildren(QDialog))==previous and not app.dialogs)

    tasks = []
    with patch.object(app,'background',side_effect=lambda work,done:tasks.append(done)):
        app.history_view.load_client()
        with patch.object(app.voice,'ready',return_value=False):
            app.pages[6].pick_voice('edge_svetlana')
        app.navigate(4)
        app.pages[4].reset('windows')
    flush()
    tasks[0](None,RuntimeError('Ответ старой страницы'))
    tasks[1](None,RuntimeError('Ответ панели голоса после смены оформления'))
    check('Поздний ответ не меняет новую страницу истории',
          app.history_view.busy and app.history_view.message == 'Загружаю историю…')
    tasks[2](None, RuntimeError('Новый запрос завершился'))
    check('Запрос новой страницы завершает загрузку', not app.history_view.busy and
          app.history_view.message == 'Новый запрос завершился')
    check('Поздняя загрузка голоса не меняет новую панель',not app.pages[6].voice_msg.text())
    app.demo_btn.click()
    check('Расстановка работает после сброса окон',app.demo_on)
    app.stop_demo()

    p = app.pool_view
    p.mode_choice.setCurrentIndex(1)
    p.filter_choices['classes'].setCurrentIndex(1)
    p.search.setText('Сетт')
    p.reset()
    check('Сброс пула синхронизирует все фильтры',not p.filters and p.mode_choice.currentData()=='all'
          and not p.search.text() and all(not c.currentData() for c in p.filter_choices.values()))

    for theme in THEMES:
        app.s['theme'] = theme
        app.apply_settings()
        flush()
        check('Тема отрисовывается · '+theme,not app.window.grab().isNull())

    app.s['scale'] = 170
    app.apply_settings()
    app.window.resize(1366,768)
    app.navigate(10)
    flush()
    check('Навигация помещается при 170%',all(b.fontMetrics().horizontalAdvance(b.text())<=b.width()-44
          for b in app.nav_buttons.values()))
    p = app.pool_view
    check('Имена чемпионов помещаются при 170%',all(
          p.list.fontMetrics().horizontalAdvance('✓ '+r['name'])<=p.list.gridSize().width()-16 for r in p.rows))

    key = ('counter','Ahri','MIDDLE')
    app.lola_state[key] = 'fail'
    app.cp_pick('Ahri','MIDDLE')
    with patch.object(app,'retry_lola') as retry:
        button = next(b for b in app.champion_view.findChildren(QPushButton) if b.text()=='Повторить')
        button.click()
        check('У сетевого сбоя есть кнопка повтора',retry.call_args.args==(key,'Ahri','MIDDLE'))


def verify_live_audit(app, check, cs):
    history = app.history_view
    me = {'puuid':'review', 'riot':app.data.d['players'][app.who]['riot']}
    with patch.object(app, 'background') as background:
        app.on_me(me)
        history.load_client()
        app.on_me(dict(me))
        background.call_args.args[1]((me, [], {}), None)
    check('Обновление того же аккаунта сохраняет загрузку истории', history.client_owner == me['puuid']
          and not history.busy and history.message == 'История обновлена')

    game = {'gid': 102, 'champ': 103, 'q': 420, 'win': True, 'dur': 1200, 't': 120000}
    with patch.object(app, 'background') as background:
        history.load_client()
        background.call_args.args[1]((me, [game], {}), None)
    history.search.setText('Ahri')
    app.apply_settings()
    history = app.history_view
    check('Оформление сохраняет историю клиента и поисковый запрос', history.source == 'client'
          and history.search.text() == 'Ahri' and [r['gid'] for r in history.filtered] == [102])
    with (patch.object(app.client, 'me', return_value=me), patch.object(app.client, 'find', return_value=True),
          patch('lcu._req', side_effect=TimeoutError), patch.object(app, 'background') as background):
        history.refresh_button.click()
        work, done = background.call_args.args
        try:
            work()
        except RuntimeError as error:
            done(None, error)
    check('Таймаут сохраняет матчи и предлагает повторить', [r['gid'] for r in history.filtered] == [102]
          and history.refresh_button.text() == 'Повторить загрузку' and 'сохранена' in history.message)

    app.navigate(2)
    chooser = app.champion_view.select
    for query, key in [('Sett', 'Sett'), ('Ahri', 'Ahri'), ('Сетт', 'Sett')]:
        completer = chooser.completer()
        completer.setCompletionPrefix(query)
        check(f'Поиск чемпиона по запросу {query}', completer.completionCount() == 1
              and completer.currentIndex().data(Qt.ItemDataRole.UserRole) == key)

    app.s['dashboard'] = True
    app.on_draft(dict(cs, phase='PLANNING', left=0, locked=False))
    build_label = app.dash.import_lbl
    app.on_draft(dict(cs, phase='BAN_PICK', left=30, locked=False))
    check('Таймер меняет фазу без пересоздания драфта',
          app.dash.head.text().endswith(' · 30 с') and app.dash.import_lbl is build_label)
    aram = dict(cs, aram=True, bench=['Lux'], left=50, locked=False)
    app.on_draft(aram)
    app.on_draft(dict(aram, bench=['Viktor']))
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    labels = {label.text() for label in app.dash.body.findChildren(QLabel)}
    check('Скамейка ARAM обновляется без смены пиков', app.data.cn('Viktor') in labels and app.data.cn('Lux') not in labels
          and app.dash.head.text().startswith('ARAM · '))
    app.on_draft(None)

    game = live_fixture(app.data)
    roster = {'games':[{'players':[{'c':p['c'], 'sc':{'r':[7,3]}} for p in game.players]}]}
    with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(roster).encode())):
        app.scout = app.fetch_scout(game)
    app.s['show']['scout'] = True
    app.s['show']['ranks'] = False
    app.ranks = {game.my_riot:{'tier':'EMERALD', 'div':'I', 'lp':83, 'w':15, 'l':10}}
    app.on_game(game, [], None)
    check('Разведка отображается у десяти участников', len(app.dash.cards) == 10
          and all('последние 10: 7–3' in card['comments'].text() for card in app.dash.cards.values()))
    check('Выключенный ранг скрыт в игре', 'LP' not in app.dash.cards[game.my_riot]['line'].text())
    app.dash.add_log(game.t, 'Подсказка до смены темы')
    app.navigate(5)
    next(b for b in app.pages[5].findChildren(QPushButton) if b.text()=='Применить оформление').click()
    QTest.qWait(40)
    check('Смена оформления сохраняет десять карточек и журнал',
          len(app.dash.cards) == 10 and 'Подсказка до смены темы' in app.dash.log_label.text())

    app.last_game = None
    app.engine = None
    app.s['postgame'] = True
    app.s['hints']['postgame'] = 'text'
    later = dict(game.raw, gameData=dict(game.raw['gameData'], gameTime=902))
    snapshots = [game.raw, None, None, later, None, None]
    states = []
    def drain_sample(_):
        app.drain()
        states.append((app.last_game, app.status.text(), len(app.dash.cards)))
    stopper = Mock()
    stopper.is_set.side_effect = lambda: len(states) >= len(snapshots)
    stopper.wait.side_effect = drain_sample
    with (patch.object(lcu, 'live_data', side_effect=snapshots),
          patch.object(app.client, 'live_match_id', return_value=102),
          patch.object(app.client, 'phase', side_effect=[None, 'Reconnect', 'EndOfGame', 'EndOfGame']),
          patch.object(app.client, 'me', return_value=None),
          patch.object(app, 'stopping', stopper), patch.object(app.root, 'after'),
          patch.object(app, 'fetch_scout', return_value={}), patch.object(app, 'fetch_people'),
          patch.object(app, 'show_postgame') as postgame):
        app.poll()
    check('Обрыв связи и переподключение сохраняют снимок и карточки', states[0][0] is states[1][0] is states[2][0]
          and 'последние данные в 15:00' in states[1][1] and states[1][2] == states[2][2] == 10
          and states[3][0].t == 902 and 'Игра: 15:02' in states[3][1])
    check('Подтверждённый конец матча показывает итог один раз',
          states[4][0] is None and states[4][1] == 'Игра закончилась' and postgame.call_count == 1
          and postgame.call_args.args[0].get('match_id') == 102)


def verify(app,directory=None):
    checks=[]
    def check(name,condition):
        if not condition:raise AssertionError(name)
        checks.append(name)
    def pump(ms=40):QTest.qWait(ms)
    def capture(name):
        if directory:
            directory.mkdir(parents=True,exist_ok=True)
            check('Снимок '+name,app.window.grab().save(str(directory/(name+'.png'))))
    pump(200);check('Все 11 страниц созданы',len(app.pages)==11);check('Tkinter не импортирован','tkinter' not in sys.modules)
    for index in range(11):
        app.navigate(index);pump();check('Навигация '+str(index),app.stack.currentIndex()==index);capture('page-'+str(index))
    history=app.history_view;app.navigate(1);pump();original=len(history.filtered);history.search.setText('Сетт');pump();check('Поиск фильтрует реальную историю',0<len(history.filtered)<original);history.reset();check('Сброс возвращает историю',len(history.filtered)==original)
    if history.filtered:
        app.open_record(history.filtered[0]);pump();check('Открытие подробностей',app.dialogs[-1].isVisible());app.dialogs[-1].close()
    pool=app.pool_view;app.navigate(10);pool.search.setText('Сетт');pump();check('Поиск в пуле',pool.list.count()==1);item=pool.list.item(0);c=item.data(Qt.ItemDataRole.UserRole);before=c in app.current_pool()[pool.role];pool.toggle(item);check('Добавление / удаление пула',(c in app.current_pool()[pool.role])!=before);pool.toggle(item);check('Повторный клик восстанавливает выбор',(c in app.current_pool()[pool.role])==before);pool.search.clear()
    build={'prim':8100,'sec':8200,'perks':[8112,8126,8140,8135,8226,8210],'shards':[5008,5008,5001],'spells':['SummonerFlash','SummonerTeleport'],'start':[1056,2003],'core':[6655,3020,3118],'i4':[3089],'i5':[3135],'i6':[3157],'skills':'QWEQQRQWQWRWWEEREE','skill_prio':'QWE','wr_runes':52.4,'n_runes':4200,'wr_core':58.1,'n_core':1600}
    app.lola[('Ahri','MIDDLE')]=dict(build,pick=build,win=dict(build,wr_runes=54.1));app.cp_pick('Ahri','MIDDLE');pump();check('Экран чемпиона',app.cp_sel==('Ahri','MIDDLE'));capture('champion-fixture')
    cs={'role':'MIDDLE','me':'Ahri','enemies':['Darius','LeeSin','Viktor','Caitlyn','Lux'],'unavailable':set(),'locked':True,'left':24,'allies':[{'c':c,'pos':r,'me':r=='MIDDLE','rank':None,'hist':None,'pu':None} for c,r in zip(['Sett','RekSai','Ahri','Jinx','Rakan'],core.ROLES)]}
    app.on_draft(cs);pump();check('Драфт Qt',app.dash is not None and app.dash.mode=='draft');check('Импорт виден',app.dash.import_lbl is not None)
    build_title=next(w for w in app.dash.findChildren(QLabel) if w.text().endswith('Общая · популярная'))
    check('Сборка не сжата до нуля',build_title.height()>15)
    build_step=next(w for w in app.dash.findChildren(QLabel) if w.text()=='18 E')
    viewport=app.dash.scroll.viewport()
    check('Прокачка видна без прокрутки',viewport.rect().contains(build_step.mapTo(viewport,build_step.rect().bottomLeft())))
    if directory:check('Снимок драфта',app.dash.grab().save(str(directory/'draft-fixture.png')))
    app.dash.show_aram(dict(cs,aram=True,bench=['Lux','Viktor']));pump();check('ARAM Qt',app.dash.mode=='draft')
    app.dash.show_arena(dict(cs,arena=True));pump();check('Арена Qt',app.dash.mode=='draft')
    app.on_draft(None);g=live_fixture(app.data);app.new_engine();app.s['widgets']={k:True for k in app.ov};app.on_game(g,[],None);pump();check('Живая игра Qt',app.dash.mode=='game')
    for k,w in app.ov.items():
        w.demo();w.deiconify();pump(10);check('Рендер виджета '+k,w._rgba is not None and w._rgba.width>0)
    widget=app.ov['inventory'];widget.unlock(True);widget.toggle_pin();check('Закрепление сохраняется',app.s['widget_pins']['inventory']);
    if os.name=='nt':
        from qt_ui.native import user
        check('Закреплённый HWND пропускает клики',bool(user.GetWindowLongW(int(widget.winId()),-20)&0x20))
        check('Кнопка закрепления принимает клики',not bool(user.GetWindowLongW(int(widget.pin.winId()),-20)&0x20))
        check('Кнопка не забирает фокус',bool(user.GetWindowLongW(int(widget.pin.winId()),-20)&0x08000000))
    widget.toggle_pin();check('Открепление сохраняется',not app.s['widget_pins']['inventory'])
    tab=app.tab['tab'];tab.show(g);tab.deiconify();pump();check('Перевес строк и команд',tab._rgba is not None and tab.totals is not None);tab.unlock(True);tab.refresh_geometry();tab.withdraw();check('Tab скрывается вместе с ручкой',not tab.isVisible() and not tab.handle.isVisible())
    if directory:
        app.dash.grab().save(str(directory/'game-fixture.png'))
        for key,w in app.ov.items():w.grab().save(str(directory/('overlay-'+key+'.png')))
    app.last_game=None;app.apply_visibility();check('Оверлеи исчезают после игры',all(not w.isVisible() for k,w in app.ov.items() if k!='hints'))
    app.dash.hide();app.navigate(1)
    available=app.window.screen().availableGeometry()
    frame=app.window.frameGeometry();client=app.window.geometry()
    max_width=available.width()-max(0,frame.width()-client.width())
    max_height=available.height()-max(0,frame.height()-client.height())
    tested=set()
    for width,height in [(940,640),(1060,740),(1366,768),(1536,864),(1920,1080)]:
        requested=(width,height)
        if os.name=='nt':width=min(width,max_width);height=min(height,max_height)
        if width<app.window.minimumWidth() or height<app.window.minimumHeight():
            raise AssertionError(f'Рабочий стол слишком мал для минимального окна: {available.width()}x{available.height()}')
        print(f'Размер Qt: запрос {requested}, доступно {available.width()}x{available.height()}, проверяется {width}x{height}',flush=True)
        if (width,height) in tested:continue
        tested.add((width,height))
        app.window.resize(width,height);pump(100);check(f'Размер окна {width}x{height}',app.window.width()==width and app.window.height()==height);capture(f'history-{width}x{height}')
    verify_audit(app,check,cs)
    verify_live_audit(app,check,cs)
    check('Нет ошибок обработчиков Qt',not app.errors)
    return checks


def main(output=None):
    output=Path(output or os.environ.get('QT_REVIEW_OUT','dist/qt-review'));output.mkdir(parents=True,exist_ok=True)
    report={'platform':sys.platform,'checks':[],'success':False};app=None
    try:
        with tempfile.TemporaryDirectory(prefix='lolhelper-qt-review-') as home:
            app=App(lolhelper.load_data(),'v2.0.0 · самопроверка',offline=True,home=home)
            report['checks']=verify(app,output);app.window.close();QTest.qWait(60);report['success']=app.stopping.is_set();report['tkinter_loaded']='tkinter' in sys.modules
    except Exception:
        report['error']=traceback.format_exc();print(report['error'])
        if app and (Path(app.home)/'errors.log').exists():print((Path(app.home)/'errors.log').read_text())
    finally:
        if app:app.shutdown()
        (output/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Qt checks:',len(report['checks']),'OK' if report['success'] else 'FAILED')
    return 0 if report['success'] else 1

if __name__=='__main__':raise SystemExit(main())
