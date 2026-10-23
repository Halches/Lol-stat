# Озвучка подсказок. Три движка: Microsoft (онлайн), Silero (локально, отдельный пакет) и Piper (встроен).
# Если выбранный не сработал — Piper, потом голос Windows. Плюс короткий сигнал.
import array, io, json, math, os, queue, re, subprocess, sys, tempfile, threading, time, urllib.request, wave, zipfile

# ключ: (название, движок, параметр движка)
ENGINES = {
    'edge_svetlana': ('Светлана · Microsoft, нужен интернет', 'edge', 'ru-RU-SvetlanaNeural'),
    'edge_dmitry': ('Дмитрий · Microsoft, нужен интернет', 'edge', 'ru-RU-DmitryNeural'),
    'silero_xenia': ('Ксения · Silero', 'silero', 'xenia'),
    'silero_kseniya': ('Ксения-2 · Silero', 'silero', 'kseniya'),
    'silero_baya': ('Байя · Silero', 'silero', 'baya'),
    'silero_aidar': ('Айдар · Silero', 'silero', 'aidar'),
    'silero_eugene': ('Евгений · Silero', 'silero', 'eugene'),
    'dmitri': ('Дмитрий · Piper', 'piper', 'dmitri'), 'denis': ('Денис · Piper', 'piper', 'denis'),
    'ruslan': ('Руслан · Piper', 'piper', 'ruslan'), 'irina': ('Ирина · Piper', 'piper', 'irina'),
}
VOICES = {k: v[0] for k, v in ENGINES.items()}
SILERO_URL = 'https://github.com/Halches/Lol-stat/releases/download/silero/silero_pack.zip'
GH = 'https://github.com/Halches/Lol-stat/releases/download/voices/ru_RU-{v}-medium.onnx'
HF = 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/{v}/medium/ru_RU-{v}-medium.onnx'
NOWIN = 0x08000000
BEEP = object()   # метка сигнала в очереди звука
# Стили сигнала: (название, [(начало с, частота Гц, длительность с, громкость, сдвиг частоты Гц)])
SOUNDS = {
    'bell': ('Колокольчик', [(0, 1046.5, .9, .8), (.11, 1318.5, 1.1, .6)]),
    'soft': ('Мягкий', [(0, 523.3, .7, .9), (.09, 659.3, .9, .6)]),
    'drop': ('Капля', [(0, 1400, .25, .9, -700)]),
    'chime': ('Перезвон', [(0, 784, .8, .6), (.1, 988, .8, .5), (.2, 1175, 1.0, .5)]),
    'tick': ('Короткий щелчок', [(0, 1600, .08, .7)]),
    'classic': ('Старый (двойной писк)', [(0, 880, .15, .9), (.18, 1175, .2, .9)]),
}


def bundle_dir():
    return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))


class Voice:
    def __init__(self, home):
        self.home = home                      # %APPDATA%/LoLHelper
        self.voice, self.volume, self.rate = 'dmitri', 80, 1.0
        self.master, self.beep_volume = 100, 70   # общая громкость и громкость сигнала, %
        self.sound = 'bell'
        self.q = queue.Queue()
        self.muted = False
        threading.Thread(target=self._loop, daemon=True).start()

    # ---- где лежат файлы
    def piper(self):
        for d in (os.path.join(bundle_dir(), 'piper'), os.path.join(self.home, 'piper')):
            exe = os.path.join(d, 'piper.exe' if os.name == 'nt' else 'piper')
            if os.path.exists(exe): return exe
        return None

    def model(self, v):
        for d in (os.path.join(bundle_dir(), 'voices'), os.path.join(self.home, 'voices')):
            p = os.path.join(d, f'ru_RU-{v}-medium.onnx')
            if os.path.exists(p) and os.path.exists(p + '.json'): return p
        return None

    def download(self, v, progress=None):
        """Скачать голос в %APPDATA%: сначала с GitHub (открывается без VPN), потом с huggingface."""
        d = os.path.join(self.home, 'voices'); os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f'ru_RU-{v}-medium.onnx')
        errors = []
        for base in (GH, HF):
            try:
                for url, out, min_size in ((base.format(v=v) + '.json', dst + '.json', 1000), (base.format(v=v), dst, 10 << 20)):
                    tmp = out + '.part'
                    req = urllib.request.Request(url, headers={'User-Agent': 'LoLHelper'})
                    with urllib.request.urlopen(req, timeout=30) as r, open(tmp, 'wb') as f:
                        total, got = int(r.headers.get('Content-Length') or 0), 0
                        while True:
                            b = r.read(1 << 18)
                            if not b: break
                            f.write(b); got += len(b)
                            if progress and total and min_size > 1000: progress(got / total)
                    if got < min_size or (total and got != total): raise IOError(f'скачано {got} байт')
                    os.replace(tmp, out)
                return dst
            except Exception as e:
                errors.append(f"{'GitHub' if base is GH else 'huggingface'}: {e}")
        raise IOError('; '.join(errors))

    def ready(self, v):
        """Голос можно использовать без скачивания."""
        eng = ENGINES.get(v, ('', 'piper', v))[1]
        if eng == 'edge': return True
        if eng == 'silero': return self.silero_ok()
        return bool(self.model(v))

    def fetch(self, v, progress=None):
        """Скачать то, что нужно голосу: модель Piper или пакет Silero."""
        eng, arg = ENGINES[v][1:]
        if eng == 'silero': return self.download_silero(progress)
        if eng == 'piper': return self.download(arg, progress)

    # ---- Silero: отдельный пакет (встроенный Python + torch + модель) в %APPDATA%/LoLHelper/silero
    def silero_dir(self): return os.path.join(self.home, 'silero')

    def silero_ok(self):
        d = self.silero_dir()
        return all(os.path.exists(os.path.join(d, f)) for f in ('python/python.exe', 'silero_srv.py', 'v5_ru.pt'))

    def download_silero(self, progress=None):
        tmp = os.path.join(self.home, 'silero_pack.zip.part')
        req = urllib.request.Request(SILERO_URL, headers={'User-Agent': 'LoLHelper'})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
            total, got = int(r.headers.get('Content-Length') or 0), 0
            while True:
                b = r.read(1 << 20)
                if not b: break
                f.write(b); got += len(b)
                if progress and total: progress(got / total * .9)
        if total and got != total: raise IOError(f'скачано {got} из {total} байт')
        if progress: progress(.95)
        d = self.silero_dir()
        with zipfile.ZipFile(tmp) as z: z.extractall(d)
        os.remove(tmp)
        if not self.silero_ok(): raise IOError('пакет распакован не полностью')
        if progress: progress(1.0)

    def _silero_proc(self):
        p = getattr(self, '_srv', None)
        if p and p.poll() is None: return p
        d = self.silero_dir()
        p = subprocess.Popen([os.path.join(d, 'python', 'python.exe'), os.path.join(d, 'silero_srv.py')], cwd=d,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                             creationflags=NOWIN if os.name == 'nt' else 0)
        line = p.stdout.readline().strip()     # модель грузится несколько секунд один раз
        if line != 'ready': p.kill(); raise IOError('Silero не запустился')
        self._srv = p
        return p

    def warm(self):
        """Заранее поднять движок выбранного голоса, чтобы первая подсказка не опоздала."""
        if ENGINES.get(self.voice, ('', ''))[1] == 'silero' and self.silero_ok():
            threading.Thread(target=lambda: self._silero_lock_call(self._silero_proc), daemon=True).start()

    def _silero_lock_call(self, fn, *a):
        self.__dict__.setdefault('_slock', threading.Lock())
        with self._slock:
            try: return fn(*a)
            except Exception: return None

    def synth_silero(self, text, speaker):
        out = os.path.join(tempfile.gettempdir(), 'lolhelper_say.wav')
        def go():
            p = self._silero_proc()
            p.stdin.write(json.dumps({'text': speakable(text), 'speaker': speaker, 'out': out}, ensure_ascii=False) + '\n'); p.stdin.flush()
            return out if p.stdout.readline().startswith('ok') else None
        return self._silero_lock_call(go)

    # ---- Microsoft (edge-tts): онлайн, mp3
    def synth_edge(self, text, voice):
        if time.time() < getattr(self, '_edge_off', 0): return None   # недавно не отвечал — не ждём зря
        try:
            import asyncio, edge_tts
            out = os.path.join(tempfile.gettempdir(), 'lolhelper_say.mp3')
            rate = f'{round((self.rate - 1) * 100):+d}%'
            async def go():
                await asyncio.wait_for(edge_tts.Communicate(text, voice, rate=rate).save(out), 8)
            asyncio.run(go())
            return out if os.path.getsize(out) > 1000 else None
        except Exception:
            self._edge_off = time.time() + 300
            return None

    def _play_mp3(self, path):
        if os.name != 'nt': return
        import ctypes
        mci = ctypes.windll.winmm.mciSendStringW
        mci('close lhsay', None, 0, 0)
        if mci(f'open "{path}" type mpegvideo alias lhsay', None, 0, 0): return
        mci(f'setaudio lhsay volume to {int(self.volume * self.master / 10)}', None, 0, 0)
        mci('play lhsay wait', None, 0, 0)
        mci('close lhsay', None, 0, 0)

    # ---- синтез и воспроизведение
    def speak(self, text):
        """Озвучить выбранным голосом; при сбое — Piper, потом голос Windows."""
        eng, arg = ENGINES.get(self.voice, ('', 'piper', self.voice))[1:]
        if eng == 'edge':
            mp3 = self.synth_edge(text, arg)
            if mp3: return self._play_mp3(mp3)
        elif eng == 'silero' and self.silero_ok():
            wav = self.synth_silero(text, arg)
            if wav: return self._play(wav)
        wav = self.synth(text)
        if wav: self._play(wav)
        else: self._sapi(text)

    def synth(self, text):
        exe, m = self.piper(), self.model(self.voice) or self.model('dmitri')
        if not exe or not m: return None
        out = os.path.join(tempfile.gettempdir(), 'lolhelper_say.wav')
        r = subprocess.run([exe, '--model', m, '--output_file', out, '--length_scale', f'{1 / max(.5, self.rate):.2f}'],
                           input=text.encode('utf-8'), capture_output=True, timeout=20, creationflags=NOWIN if os.name == 'nt' else 0)
        return out if r.returncode == 0 and os.path.exists(out) else None

    def _scaled(self, path):
        """Громкость: умножаем отсчёты wav (winsound сам громкость не умеет)."""
        with wave.open(path, 'rb') as w:
            p = w.getparams(); fr = w.readframes(p.nframes)
        if p.sampwidth != 2: return open(path, 'rb').read()
        a = array.array('h', fr); k = self.volume * self.master / 10000
        a = array.array('h', (max(-32768, min(32767, int(x * k))) for x in a))
        b = io.BytesIO()
        with wave.open(b, 'wb') as w:
            w.setparams(p); w.writeframes(a.tobytes())
        return b.getvalue()

    def _play(self, path):
        if os.name != 'nt': return
        import winsound
        winsound.PlaySound(self._scaled(path), winsound.SND_MEMORY)

    def _sapi(self, text):
        if os.name != 'nt': return
        t = text.replace("'", "''")
        ps = ("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
              f"$s.Volume={int(self.volume * self.master / 100)}; $s.Speak('{t}')")
        subprocess.run(['powershell', '-NoProfile', '-Command', ps], timeout=30, creationflags=NOWIN)

    def beep_wav(self):
        """Сигнал выбранного стиля (self.sound), громкость = общая × сигнал."""
        rate, k = 44100, 0.5 * self.beep_volume * self.master / 10000
        notes = SOUNDS.get(self.sound, SOUNDS['bell'])[1]
        n_total = int(rate * max(t + d for t, f, d, *_ in notes))
        buf = [0.0] * n_total
        for t0, f, dur, *rest in notes:
            amp = rest[0] if rest else 1.0
            sweep = rest[1] if len(rest) > 1 else 0
            start, n = int(rate * t0), int(rate * dur)
            ph = 0.0
            for i in range(n):
                x = i / rate
                env = min(1.0, i / (rate * .006)) * math.exp(-x * 5.5 / dur)   # мягкая атака и затухание как у колокольчика
                fr = f + sweep * x / dur
                ph += 2 * math.pi * fr / rate
                v = math.sin(ph) + .25 * math.sin(2 * ph) + .08 * math.sin(3 * ph)
                if start + i < n_total: buf[start + i] += amp * env * v / 1.33
        a = array.array('h', (int(max(-1, min(1, x * k)) * 32767) for x in buf))
        b = io.BytesIO()
        with wave.open(b, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(a.tobytes())
        return b.getvalue()

    def beep(self, force=False):
        if force or not self.muted: self.q.put(BEEP)

    def say(self, text, force=False):
        if text and (force or not self.muted): self.q.put(text)

    def _loop(self):
        while True:
            text = self.q.get()
            while self.q.qsize() > 2: text = self.q.get()   # не копить очередь: старые подсказки уже не нужны
            if text is BEEP:
                if os.name == 'nt':
                    import winsound
                    try: winsound.PlaySound(self.beep_wav(), winsound.SND_MEMORY)
                    except Exception: pass
                continue
            try:
                self.speak(text)
            except Exception:
                try: self._sapi(text)
                except Exception: pass


# ---- числа словами (Silero пропускает цифры)
_U = 'ноль один два три четыре пять шесть семь восемь девять'.split()
_UF = ['ноль', 'одна', 'две'] + _U[3:]
_T = 'десять одиннадцать двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать восемнадцать девятнадцать'.split()
_D = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
_H = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 'шестьсот', 'семьсот', 'восемьсот', 'девятьсот']


def _under1000(n, fem=False):
    w = [_H[n // 100]] if n >= 100 else []
    n %= 100
    if 10 <= n < 20: w.append(_T[n - 10])
    else:
        if n >= 20: w.append(_D[n // 10])
        if n % 10: w.append((_UF if fem else _U)[n % 10])
    return w


def num_words(n):
    if n == 0: return 'ноль'
    w = []
    for div, forms, fem in ((10 ** 6, ('миллион', 'миллиона', 'миллионов'), False), (1000, ('тысяча', 'тысячи', 'тысяч'), True)):
        k, n = divmod(n, div)
        if k:
            if not (k == 1 and fem): w += _under1000(k, fem)   # «тысяча», а не «одна тысяча»
            last = k % 100
            w.append(forms[2] if 10 <= last < 20 or last % 10 in (0, 5, 6, 7, 8, 9) else forms[0] if last % 10 == 1 else forms[1])
    w += _under1000(n)
    return ' '.join(x for x in w if x)


def speakable(text):
    """Текст для движков, которые не читают цифры: 2:50 -> «две пятьдесят», 3–4 -> «три до четырёх», +300 -> «плюс триста»."""
    t = re.sub(r'(\d+):(\d\d)', lambda m: f"{m.group(1)} {m.group(2).lstrip('0') or 'ноль'}", text)
    t = re.sub(r'(\d)\s*[–-]\s*(\d)', r'\1, \2', t)
    t = re.sub(r'(?<!\w)\+(?=\d)', 'плюс ', t)
    t = re.sub(r'(?<!\w)[−-](?=\d)', 'минус ', t)
    t = re.sub(r'(\d+)[.,](\d+)', lambda m: f'{m.group(1)} и {m.group(2)}', t)
    t = t.replace('%', ' процентов')
    for en, ru in (('KDA', 'кей ди эй'), ('CS', 'си эс'), ('LP', 'эл пи')): t = re.sub(rf'\b{en}\b', ru, t)
    return re.sub(r'\d+', lambda m: num_words(int(m.group())), t)
