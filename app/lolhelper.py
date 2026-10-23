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


def latest_release():
    """Тег и ссылка на exe последнего релиза. Сначала API, иначе редирект github.com/releases/latest."""
    try:
        with get(f'https://api.github.com/repos/{REPO}/releases/latest', 10) as r: j = json.load(r)
        url = next((a['browser_download_url'] for a in j.get('assets', []) if a['name'].lower().endswith('.exe')), None)
        return j['tag_name'], url
    except Exception:
        with get(f'https://github.com/{REPO}/releases/latest', 10) as r:
            tag = r.geturl().rstrip('/').split('/')[-1]
        return tag, f'https://github.com/{REPO}/releases/download/{tag}/LoLHelper.exe'


def update_app(app):
    try:
        tag, url = latest_release()
    except Exception as e:
        return f'Не удалось проверить обновления: {e}'
    if tag == VERSION or not url: return f'Последняя версия: {tag}. У тебя актуальная.'
    if not FROZEN: return f'Есть версия {tag} (запущено из исходников, обновление не ставлю)'
    new = os.path.join(home(), 'LoLHelper.new.exe')
    try:
        with get(url, 120) as r, open(new + '.part', 'wb') as f:
            while True:
                b = r.read(1 << 20)
                if not b: break
                f.write(b)
        os.replace(new + '.part', new)
    except Exception as e:
        return f'Версия {tag} не скачалась: {e}'
    app.root.after(0, lambda: ask_restart(app, tag, new))
    return f'Скачана версия {tag}'


def ask_restart(app, tag, new):
    from tkinter import messagebox
    if not messagebox.askyesno('LoL Helper', f'Скачана новая версия {tag}. Перезапустить и обновить сейчас?'): return
    exe = sys.executable
    bat = os.path.join(tempfile.gettempdir(), 'lolhelper_update.bat')
    open(bat, 'w', encoding='cp866', errors='replace').write(
        '@echo off\r\n'
        f'for /l %%i in (1,1,20) do (move /y "{new}" "{exe}" >nul 2>&1 && goto ok & timeout /t 1 >nul)\r\n'
        ':ok\r\n'
        f'start "" "{exe}"\r\n'
        'del "%~f0"\r\n')
    subprocess.Popen(['cmd', '/c', bat], creationflags=0x08000000)
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
        out.append('ui ok')
        from voice import Voice
        v = Voice(home())
        out.append(f'piper {v.piper()} model {v.model("dmitri")}')
        wav = v.synth('Проверка голоса')
        out.append(f'wav {wav and os.path.getsize(wav)}')
        if FROZEN and not wav: ok = False
    except Exception:
        out.append(traceback.format_exc()); ok = False
    out.append('OK' if ok else 'FAIL')
    open(os.path.join(os.path.dirname(sys.executable if FROZEN else __file__), 'selftest.txt'), 'w', encoding='utf-8').write('\n'.join(out))
    sys.exit(0 if ok else 1)


def main():
    if '--selftest' in sys.argv: selftest()
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
