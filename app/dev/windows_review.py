"""Проверка ветки разработки на Windows в отдельном профиле, без обновления EXE."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
SMOKE_TRACE=None


def smoke_stage(text):
    if SMOKE_TRACE is not None:
        print(time.strftime('%H:%M:%S'),text,file=SMOKE_TRACE,flush=True)


def main():
    if os.name!='nt':raise SystemExit('Этот запуск предназначен для Windows с установленным LoL.')
    smoke_stage('import ui and application data')
    import ui,lolhelper
    frozen=bool(getattr(sys,'frozen',False));smoke='--smoke-test' in sys.argv
    review=Path(ui.app_home())/'development-review';review.mkdir(parents=True,exist_ok=True)
    report=review/'review-report.txt'
    with report.open('w',encoding='utf-8') as output:
        output.write(f'Проверка приложения · {time.strftime("%d.%m.%Y %H:%M")}\n{platform.platform()}\nPython {platform.python_version()}\n')
        output.flush()
        commands=() if frozen or smoke else ([sys.executable,'-m','unittest','discover','-s','app','-p','test_*.py'],[sys.executable,'app/test_core.py'])
        for args in commands:
            result=subprocess.run(args,cwd=APP.parent,stdout=output,stderr=subprocess.STDOUT)
            if result.returncode:raise SystemExit('Есть ошибки тестов. Отчёт: '+str(report))
    # Отдельные настройки и кэши; личный рабочий профиль не перезаписывается.
    ui.app_home=lambda:str(review)
    lolhelper.home=lambda:str(review)
    settings=review/'settings.json'
    if not settings.exists():settings.write_text(json.dumps({'design3':True,'auto_import':False,'phone':False}),encoding='utf-8')
    # updater и сервер телефона не участвуют в проверке приложения.
    ui.App.check_updates=lambda *a,**k:None
    ui.App.sync_phone=lambda *a:None
    if smoke:
        for method in ('poll','load_lanes','load_changelog','hist_refresh','ensure_home_icon'):
            setattr(ui.App,method,lambda *a,**k:None)
        ui.Voice.warm=lambda *a:None
    smoke_stage('construct application')
    app=ui.App(lolhelper.load_data(),'ПРОВЕРКА РАЗРАБОТКИ',None)
    smoke_stage('application constructed')
    errors=[]
    if smoke:
        def callback_error(et,ev,tb):
            errors.append(str(ev))
            if SMOKE_TRACE is not None:traceback.print_exception(et,ev,tb,file=SMOKE_TRACE);SMOKE_TRACE.flush()
        app.root.report_callback_exception=callback_error
    app.root.title('LoL Helper · ПУЛ И ИСТОРИЯ v5 · отдельные настройки')
    latency=None
    if not smoke and hasattr(app.root,'tk'):
        from ui_latency import LatencyLog
        latency=LatencyLog(app.root,review/'ui-latency.json')
    def close():
        smoke_stage('close application')
        if latency:latency.close()
        with report.open('a',encoding='utf-8') as output:
            if not smoke:output.write('\n'+app.report_text()+'\n')
            output.write(('SMOKE FAIL: '+repr(errors) if errors else 'SMOKE OK: интерфейс и ресурсы')+'\n' if smoke else 'Проверка закрыта пользователем. Результаты ручного прогона надо указать отдельно.\n')
        if sys.stdout is not None:
            try:print('Отчёт:',report)
            except UnicodeEncodeError:print('Report:',ascii(str(report)))
        app.root.destroy()
        smoke_stage('application closed')
    app.root.protocol('WM_DELETE_WINDOW',close)
    if smoke:
        for key,window in app.ov.items():
            smoke_stage('render overlay '+key)
            window.demo()
        smoke_stage('update geometry')
        app.root.update_idletasks()
        assert len(app.icons.a.get('champ',{}))>=173,'Не упакованы портреты'
        assert Path(lolhelper.HERE,'fonts').is_dir(),'Не упакованы шрифты'
        assert Path(lolhelper.HERE,'champion_catalog.json').is_file(),'Не упакован каталог'
        app.root.after(1000,close)
    smoke_stage('enter mainloop')
    app.run()
    smoke_stage('mainloop returned')
    if smoke and errors:raise SystemExit(1)


if __name__=='__main__':
    if '--smoke-test' in sys.argv:
        import faulthandler
        folder=Path(os.environ.get('APPDATA') or Path.home())/'LoLHelper'/'development-review'
        folder.mkdir(parents=True,exist_ok=True)
        with (folder/'smoke-trace.txt').open('w',encoding='utf-8') as SMOKE_TRACE:
            faulthandler.enable(file=SMOKE_TRACE)
            faulthandler.dump_traceback_later(20,repeat=True,file=SMOKE_TRACE)
            try:main()
            except BaseException:
                traceback.print_exc(file=SMOKE_TRACE);SMOKE_TRACE.flush()
                if getattr(sys,'frozen',False):os._exit(1)
                raise
            finally:faulthandler.cancel_dump_traceback_later()
    else:main()
