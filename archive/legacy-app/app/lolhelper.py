# LoL Helper: точка входа. Загружает статистику, проверяет обновления, запускает окна.
# Запуск из исходников: python app/lolhelper.py ; проверка сборки: LoLHelper.exe --selftest
import copy, json, os, re, subprocess, sys, tempfile, threading, time, traceback, urllib.request
from datetime import datetime

HERE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import core

REPO = 'Halches/Lol-stat'
RAW = f'https://raw.githubusercontent.com/{REPO}/main/app/data.json'
try: VERSION = open(os.path.join(HERE, 'version.txt')).read().strip()
except Exception: VERSION = 'dev'
FROZEN = getattr(sys, 'frozen', False)
DATA_WRITE_LOCK = threading.Lock()


def home():
    d = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'LoLHelper')
    os.makedirs(d, exist_ok=True)
    return d


def with_history(data):
    import history_archive
    matches={}
    try:
        with open(os.path.join(HERE,'history-details.json'),encoding='utf-8') as source:archive=json.load(source)
        if isinstance(archive,dict) and archive.get('version')==1 and isinstance(archive.get('matches'),dict):matches.update(archive['matches'])
    except (OSError,ValueError,TypeError):pass
    if isinstance(data.get('match_details'),dict):matches.update(data['match_details'])
    return history_archive.attach(data,matches)


def validated_data(d):
    """Check the saved statistics format before choosing or writing a cache."""
    if not isinstance(d, dict):
        raise ValueError('Ожидается объект со статистикой')
    stamp = d.get('t')
    if not isinstance(stamp, str):
        raise ValueError('У статистики нет даты')
    date = datetime.fromisoformat(stamp)
    for key in ('names', 'ids', 'items', 'lola', 'players', 'pools'):
        if not isinstance(d.get(key), dict):
            raise ValueError(f'Некорректный раздел статистики «{key}»')
    for key in ('champs', 'arena', 'match_details'):
        if key in d and not isinstance(d[key], dict):
            raise ValueError(f'Некорректный раздел статистики «{key}»')
    if 'patch' in d and not isinstance(d['patch'], str):
        raise ValueError('Некорректный патч статистики')
    for key in ('names', 'ids'):
        if not all(isinstance(value, str) for value in d[key].values()):
            raise ValueError(f'Некорректные имена в разделе «{key}»')
    if not d['names'] or not d['ids']:
        raise ValueError('Список чемпионов пуст')
    if not all(isinstance(item, dict) and isinstance(item.get('n'), str)
               and type(item.get('g')) is int for item in d['items'].values()):
        raise ValueError('Некорректные данные предметов')
    if not all(isinstance(value, dict) for value in d['lola'].values()):
        raise ValueError('Некорректные данные сборок')
    if not all(isinstance(pool, dict) and all(isinstance(picks, list) and
               all(isinstance(champ, str) for champ in picks) for picks in pool.values())
               for pool in d['pools'].values()):
        raise ValueError('Некорректные пулы чемпионов')
    for player in d['players'].values():
        if not isinstance(player, dict) or not isinstance(player.get('riot'), str) or not isinstance(player.get('g'), list):
            raise ValueError('Некорректный профиль игрока')
        if player.get('rank') is not None and not isinstance(player['rank'], str):
            raise ValueError('Некорректный ранг игрока')
        for game in player['g']:
            if (not isinstance(game, dict) or not isinstance(game.get('c'), str)
                    or not isinstance(game.get('pos', ''), str)
                    or game.get('q') is not None and type(game['q']) is not int):
                raise ValueError('Некорректная запись матча')
            for field in ('it', 'spells', 'pk'):
                value = game.get(field)
                if value is not None and (not isinstance(value, list) or any(type(item) not in (int, str) for item in value)):
                    raise ValueError(f'Некорректный список «{field}» в записи матча')
    # Current and legacy datasets use local, timezone-free timestamps.
    return date.replace(tzinfo=None), core.Data(with_history(d))


def load_data():
    """Берём более свежую статистику: встроенную в exe или скачанную ранее."""
    best = None
    for p in (os.path.join(HERE, 'data.json'), os.path.join(home(), 'data.json')):
        try:
            with open(p, encoding='utf-8') as source:
                candidate = validated_data(json.load(source))
            if best is None or candidate[0] > best[0]:
                best = candidate
        except FileNotFoundError:
            continue
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            log(f'Пропущены некорректные данные ({p}): {error}')
    if best is None:
        raise ValueError('Не удалось загрузить встроенную статистику или сохранённый кэш')
    return best[1]


def get(url, timeout=20):
    r = urllib.request.Request(url, headers={'User-Agent': 'LoLHelper/' + VERSION})
    return urllib.request.urlopen(r, timeout=timeout)


def update_data(app):
    try:
        with get(RAW) as r: d = json.load(r)
        date, data = validated_data(copy.deepcopy(d))
        with DATA_WRITE_LOCK:
            if date <= datetime.fromisoformat(app.data.d['t']).replace(tzinfo=None): return False
            p = os.path.join(home(), 'data.json')
            try:
                with open(p, encoding='utf-8') as source:
                    current, _ = validated_data(json.load(source))
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                current = None
            if current is not None and date <= current:return False
            temp = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=os.path.dirname(p), delete=False) as output:
                    temp = output.name
                    json.dump(d, output, ensure_ascii=False, separators=(',', ':'))
                os.replace(temp, p)
            finally:
                if temp and os.path.exists(temp):
                    os.unlink(temp)
            app.root.after(0, lambda: app.reload_data(data))
        return True
    except Exception as error:
        log(f'Не удалось обновить статистику: {error}')
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


def release_number(tag):
    """Номер стабильного выпуска; dev и служебные теги не являются версиями."""
    match = re.fullmatch(r'v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', str(tag))
    return tuple(map(int, match.groups())) if match else None


def update_app(app):
    """Проверка новой версии. Если есть — в окне программы появляется плашка с кнопкой «Обновить»."""
    try:
        tag, url = latest_release()
    except Exception as e:
        log(f'check failed: {e!r}')
        return f'Не удалось проверить обновления: {e}'
    log(f'latest {tag}, mine {VERSION}')
    latest, current = release_number(tag), release_number(VERSION)
    if latest is None:
        return f'Не удалось определить номер выпуска: {tag}'
    if current is not None and latest <= current:
        return f'Последняя опубликованная версия: {tag}. Обновление не требуется.'
    if not url:
        return f'Версия {tag}: файл обновления пока недоступен.'
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
    if app.stopping.wait(5): return
    if app.s['auto_update']: update_app(app)
    while not app.stopping.is_set():
        update_data(app)
        app.stopping.wait(1800)


def selftest():
    """Реальные Qt-окна и ресурсы EXE; временные настройки, без доступа к игре."""
    from pathlib import Path
    out=[];ok=False
    folder=Path(sys.executable).parent if FROZEN else Path(__file__).parent
    try:
        import qt_review
        code=qt_review.main(folder/'qt-selftest')
        out.append((folder/'qt-selftest/checks.json').read_text(encoding='utf-8'))
        ok=code==0
        import cv2,numpy,tab_detect
        from PIL import Image
        assert tab_detect.detect(Image.new('RGB',(640,480)),{},[]) is None
        out.append('OpenCV и распознавание Tab: OK')
        if FROZEN:
            from augment_scan import Reader
            from augment_advice import names, popularity
            from PIL import ImageDraw, ImageFont
            probe = Image.new('RGB', (1600, 300), '#101c24')
            pen = ImageDraw.Draw(probe)
            font = ImageFont.truetype(str(Path(sys._MEIPASS)/'qt_ui/fonts/PT_Serif-Web-Bold.ttf'), 26)
            for x, title in zip((450, 800, 1150), ('Проворство', 'Тяжеловес', 'Голиаф')):
                pen.text((x, 120), title, fill='#eedfc7', font=font, anchor='mt')
            detected = Reader().read(probe, 'arena', 1080)
            assert [card['ru'] for _, _, card in detected] == ['Проворство', 'Тяжеловес', 'Голиаф']
            assert names("mayhem") and popularity()["rates"]
            out.append("Распознавание аугментаций RU/EN: OK")
            import edge_tts,webview,sitewin
            from voice import Voice
            with tempfile.TemporaryDirectory(prefix='lolhelper-voice-test-') as directory:
                voice=Voice(directory);wav=voice.synth('Проверка голоса')
                assert wav and os.path.getsize(wav)>44,'Piper не создал звук'
                out.append('Встроенный голос Piper: OK')
            from qt_ui.widgets import Icons
            assert len(Icons().a.get('champ',{}))>=150,'Не упакованы портреты чемпионов'
            assert (Path(HERE)/'qt_ui/fonts/PT_Serif-Web-Regular.ttf').is_file()
            assert (Path(HERE)/'history-details.json').is_file()
            out.append('Шрифты, изображения, архив, Microsoft TTS и WebView: OK')
        assert 'tkinter' not in sys.modules,'Основная программа загрузила Tkinter'
    except Exception:
        out.append(traceback.format_exc());ok=False
    out.append('OK' if ok else 'FAIL')
    (folder/'selftest.txt').write_text('\n'.join(out),encoding='utf-8')
    sys.exit(0 if ok else 1)


def main():
    if '--selftest' in sys.argv: selftest()
    if '--site' in sys.argv:
        try:
            import sitewin; sitewin.run(home(), next((a[7:] for a in sys.argv if a.startswith('--game=')), None))
        except Exception:
            open(os.path.join(home(), 'site_error.txt'), 'w', encoding='utf-8').write(traceback.format_exc())
            import webbrowser; webbrowser.open('https://halches.github.io/Lol-stat/')
        return
    try:
        import qt_app
        app = qt_app.App(load_data(), VERSION, updater)
        threading.Thread(target=background, args=(app,), daemon=True).start()
        app.run()
    except Exception:
        open(os.path.join(home(), 'crash.txt'), 'w', encoding='utf-8').write(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()
