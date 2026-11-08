"""Проверка настоящих Qt-окон в изолированном профиле, без игры и сети."""
import json,os,sys,tempfile,time,traceback
from pathlib import Path
from unittest.mock import Mock,patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import core,lolhelper
from qt_app import App


def live_fixture(data):
    champions=['Sett','RekSai','Viktor','Jinx','Rakan','Darius','LeeSin','Ahri','Caitlyn','Lux']
    snap={'activePlayer':{'riotId':'Halch#9200','currentGold':850},'gameData':{'gameTime':900,'gameMode':'CLASSIC','mapNumber':11},'events':{'Events':[]},'allPlayers':[]}
    for i,c in enumerate(champions):snap['allPlayers'].append({'riotId':'Halch#9200' if i==0 else f'Проверка{i}#1','rawChampionName':'game_character_displayname_'+c,'team':'ORDER' if i<5 else 'CHAOS','position':core.ROLES[i%5],'level':11,'isDead':False,'respawnTimer':0,'items':[{'itemID':1055,'count':1},{'itemID':3006,'count':1}],'scores':{'kills':i%4,'deaths':2,'assists':5,'creepScore':95+i*4,'wardScore':12},'summonerSpells':{'summonerSpellOne':{'rawDisplayName':'SummonerFlash'},'summonerSpellTwo':{'rawDisplayName':'SummonerSmite' if i%5==1 else 'SummonerTeleport'}}})
    return core.Game(snap,data)


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
    from PySide6.QtWidgets import QLabel
    build_title=next(w for w in app.dash.findChildren(QLabel) if w.text()=='Выбранный вариант')
    check('Сборка не сжата до нуля',build_title.height()>15)
    check('Драфт прокручивается до сборки',app.dash.scroll.verticalScrollBar().maximum()>0)
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
    for width,height in [(940,640),(1060,740),(1366,768),(1536,864),(1920,1080)]:
        app.window.resize(width,height);pump(100);check(f'Размер окна {width}x{height}',app.window.width()==width and app.window.height()==height);capture(f'history-{width}x{height}')
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
