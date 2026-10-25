# LoL Helper: точка входа. Загружает статистику, проверяет обновления, запускает окна.
# Запуск из исходников: python app/lolhelper.py ; проверка сборки: LoLHelper.exe --selftest
import json, os, subprocess, sys, tempfile, threading, time, traceback, urllib.request

HERE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import core

REPO = 'Halches/Lol-stat'
RAW = f'https://raw.githubusercontent.com/{REPO}/main/app/data.json'
try: VERSION = open(os.path.join(HERE, 'version.txt')).read().strip()
except Exception: VERSION = 'dev'
FROZEN = getattr(sys, 'frozen', False)


def home():
    d = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'LoLHelper')
    os.makedirs(d, exist_ok=True)
    return d


def load_data():
    """Берём более свежую статистику: встроенную в exe или скачанную ранее."""
    best = None
    for p in (os.path.join(HERE, 'data.json'), os.path.join(home(), 'data.json')):
        try:
            d = json.load(open(p, encoding='utf-8'))
            if not best or d['t'] > best['t']: best = d
        except Exception:
            pass
    return core.Data(best)


def get(url, timeout=20):
    r = urllib.request.Request(url, headers={'User-Agent': 'LoLHelper/' + VERSION})
    return urllib.request.urlopen(r, timeout=timeout)


def update_data(app):
    try:
        with get(RAW) as r: d = json.load(r)
        if d['t'] <= app.data.d['t']: return False
        p = os.path.join(home(), 'data.json')
        json.dump(d, open(p + '.tmp', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        os.replace(p + '.tmp', p)
        app.root.after(0, lambda: app.reload_data(core.Data(d)))
        return True
    except Exception:
        return False


SIZES = {}   # ожидаемый размер exe по данным GitHub API


def latest_release():
    """Тег и ссылка на exe последнего релиза. Сначала API, иначе редирект github.com/releases/latest."""
    try:
        with get(f'https://api.github.com/repos/{REPO}/releases/latest', 10) as r: j = json.load(r)
        a = next((a for a in j.get('assets', []) if a['name'].lower().endswith('.exe')), None)
        if a: SIZES[a['browser_download_url']] = a.get('size')
        return j['tag_name'], a and a['browser_download_url']
    except Exception:
        with get(f'https://github.com/{REPO}/releases/latest', 10) as r:
            tag = r.geturl().rstrip('/').split('/')[-1]
        return tag, f'https://github.com/{REPO}/releases/download/{tag}/LoLHelper.exe'


def log(msg):
    try:
        with open(os.path.join(home(), 'update.log'), 'a', encoding='utf-8') as f: f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + '\n')
    except Exception:
        pass


def update_app(app):
    """Проверка новой версии. Если есть — в окне программы появляется плашка с кнопкой «Обновить»."""
    try:
        tag, url = latest_release()
    except Exception as e:
        log(f'check failed: {e!r}')
        return f'Не удалось проверить обновления: {e}'
    log(f'latest {tag}, mine {VERSION}')
    if tag == VERSION or not url: return f'Последняя версия: {tag}. У тебя актуальная.'
    app.root.after(0, lambda: app.offer_update(tag, lambda: start_download(app, tag, url)))
    if not FROZEN: return f'Есть версия {tag} (запущено из исходников, обновление не ставлю)'
    return f'Есть новая версия {tag}: нажми «Обновить» вверху окна'


def start_download(app, tag, url):
    if not FROZEN:
        app.update_state('Запущено из исходников: обновление ставится только в exe'); return
    def job():
        new = os.path.join(home(), 'LoLHelper.new.exe')
        try:
            with get(url, 60) as r, open(new + '.part', 'wb') as f:
                total, got, last = int(r.headers.get('Content-Length') or 0), 0, 0
                while True:
                    b = r.read(1 << 18)
                    if not b: break
                    f.write(b); got += len(b)
                    if time.time() - last > .3:
                        last = time.time()
                        txt = f'Скачиваю {tag}: {got * 100 // total}% ({got >> 20} из {total >> 20} МБ)' if total else f'Скачиваю {tag}: {got >> 20} МБ'
                        app.root.after(0, lambda t=txt: app.update_state(t))
            want = SIZES.get(url) or total
            if want and got != want: raise IOError(f'скачано {got} из {want} байт')
            with open(new + '.part', 'rb') as f:
                if f.read(2) != b'MZ' or got < 20 << 20: raise IOError('файл повреждён')
            os.replace(new + '.part', new)
            log(f'downloaded {tag} {got} bytes')
            app.root.after(0, lambda: app.update_state(f'Версия {tag} скачана', lambda: restart_into(app, new)))
        except Exception as e:
            log(f'download failed: {e!r}')
            msg = f'Не скачалось: {e}. Попробуй ещё раз или скачай вручную с GitHub'
            app.root.after(0, lambda: app.update_state(msg, lambda: start_download(app, tag, url)))
    app.update_state(f'Скачиваю {tag}…')
    threading.Thread(target=job, daemon=True).start()


def restart_into(app, new):
    """Заменить exe новым и перезапустить: bat ждёт, пока старый процесс закроется."""
    exe = sys.executable
    bat = os.path.join(tempfile.gettempdir(), 'lolhelper_update.bat')
    open(bat, 'w', encoding='cp866', errors='replace').write(
        '@echo off\r\n'
        f'for /l %%i in (1,1,30) do (move /y "{new}" "{exe}" >nul 2>&1 && goto ok & timeout /t 1 >nul)\r\n'
        ':ok\r\n'
        f'start "" "{exe}"\r\n'
        'del "%~f0"\r\n')
    log(f'restart via {bat}')
    # Новый exe не должен унаследовать переменные PyInstaller старого процесса: иначе он ищет
    # python312.dll во временной папке старого, которую тот удаляет при выходе.
    env = {k: v for k, v in os.environ.items() if not k.startswith(('_PYI', '_MEI'))}
    env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    subprocess.Popen(['cmd', '/c', bat], creationflags=0x08000000, env=env)
    app.root.destroy()
    os._exit(0)


def updater(app):
    """Кнопка «Проверить сейчас»: и статистика, и программа."""
    got = update_data(app)
    msg = update_app(app)
    return ('Статистика обновлена. ' if got else '') + msg


def background(app):
    time.sleep(5)
    if app.s['auto_update']: update_app(app)
    while True:
        update_data(app)
        time.sleep(1800)


def selftest():
    """Проверка собранного exe в CI: данные, логика, окна, голос. Результат в selftest.txt рядом с exe."""
    out = []
    ok = True
    try:
        d = load_data()
        out.append(f"data {d.d['t']} players {len(d.d['players'])}")
        snap = {'activePlayer': {'riotId': 'Halch#9200', 'currentGold': 500}, 'gameData': {'gameTime': 160},
                'events': {'Events': []},
                'allPlayers': [{'riotId': f'P{i}#1', 'rawChampionName': 'game_character_displayname_' + c, 'team': 'ORDER' if i < 5 else 'CHAOS',
                                'position': core.ROLES[i % 5], 'level': 3, 'items': [], 'scores': {},
                                'summonerSpells': {'summonerSpellOne': {'rawDisplayName': 'SummonerSmite' if i % 5 == 1 else 'SummonerFlash'}}}
                               for i, c in enumerate(['Sett', 'RekSai', 'Viktor', 'Jinx', 'Rakan', 'Darius', 'LeeSin', 'Ahri', 'Caitlyn', 'Lux'])]}
        snap['allPlayers'][0]['riotId'] = 'Halch#9200'
        e = core.Engine(d, core.Player(d, 'halch'))
        hs = e.tick(core.Game(snap, d))
        out.append(f'hints {len(hs)}')
        import ui
        app = ui.App(d, VERSION)
        app.root.after(2500, app.root.destroy)
        app.root.mainloop()
        n = len(app.icons.a.get('champ', {}))
        out.append(f'ui ok, portraits {n}, pillow {ui.Image is not None}')
        import render
        fdir = os.path.join(HERE, 'fonts')
        out.append(f"fonts {sorted(os.listdir(fdir)) if os.path.isdir(fdir) else 'нет папки'}; pil {render.font('Manrope', 14).getname()}")
        if FROZEN and not os.path.isdir(fdir): ok = False
        if FROZEN and (n < 150 or ui.Image is None): ok = False
        try:
            tag, url = latest_release()
            with get(url, 30) as r: chunk = r.read(1 << 20)
            out.append(f'release {tag} reachable, {len(chunk)} bytes')
        except Exception as e:
            out.append(f'release check failed: {e!r}')
        from voice import Voice
        v = Voice(home())
        out.append(f'piper {v.piper()} model {v.model("dmitri")}')
        wav = v.synth('Проверка голоса')
        out.append(f'wav {wav and os.path.getsize(wav)}')
        if FROZEN and not wav: ok = False
        try:   # голос Microsoft: библиотека в exe и связь с сервисом (на сборочной машине)
            mp3 = v.synth_edge('Проверка голоса', 'ru-RU-SvetlanaNeural')
            out.append(f'edge mp3 {mp3 and os.path.getsize(mp3)}')
        except Exception as e:
            out.append(f'edge failed: {e!r}')
        import edge_tts  # noqa: F401  (должен быть внутри exe)
        import webview, sitewin  # noqa: F401  (окно сайта)
        p = sitewin.page(home())
        out.append(f'site page {p and os.path.getsize(p)}')
    except Exception:
        out.append(traceback.format_exc()); ok = False
    out.append('OK' if ok else 'FAIL')
    open(os.path.join(os.path.dirname(sys.executable if FROZEN else __file__), 'selftest.txt'), 'w', encoding='utf-8').write('\n'.join(out))
    sys.exit(0 if ok else 1)


def main():
    if '--selftest' in sys.argv: selftest()
    if '--site' in sys.argv:
        try:
            import sitewin; sitewin.run(home())
        except Exception:
            open(os.path.join(home(), 'site_error.txt'), 'w', encoding='utf-8').write(traceback.format_exc())
            import webbrowser; webbrowser.open('https://halches.github.io/Lol-stat/')
        return
    try:
        import ui
        app = ui.App(load_data(), VERSION, updater)
        threading.Thread(target=background, args=(app,), daemon=True).start()
        app.run()
    except Exception:
        open(os.path.join(home(), 'crash.txt'), 'w', encoding='utf-8').write(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
