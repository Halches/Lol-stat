# Озвучка подсказок: нейросетевые голоса Piper (локально), запасной вариант — голос Windows, плюс короткий сигнал.
import array, io, math, os, queue, subprocess, sys, tempfile, threading, urllib.request, wave

VOICES = {'dmitri': 'Дмитрий', 'denis': 'Денис', 'ruslan': 'Руслан', 'irina': 'Ирина'}
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

    # ---- синтез и воспроизведение
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
                wav = self.synth(text)
                if wav: self._play(wav)
                else: self._sapi(text)
            except Exception:
                try: self._sapi(text)
                except Exception: pass
