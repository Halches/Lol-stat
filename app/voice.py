# Озвучка подсказок: нейросетевые голоса Piper (локально), запасной вариант — голос Windows, плюс короткий сигнал.
import array, io, math, os, queue, subprocess, sys, tempfile, threading, urllib.request, wave

VOICES = {'dmitri': 'Дмитрий', 'denis': 'Денис', 'ruslan': 'Руслан', 'irina': 'Ирина'}
HF = 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/{v}/medium/ru_RU-{v}-medium.onnx'
NOWIN = 0x08000000
BEEP = object()   # метка сигнала в очереди звука


def bundle_dir():
    return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))


class Voice:
    def __init__(self, home):
        self.home = home                      # %APPDATA%/LoLHelper
        self.voice, self.volume, self.rate = 'dmitri', 80, 1.0
        self.master, self.beep_volume = 100, 70   # общая громкость и громкость сигнала, %
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
        """Скачать голос с huggingface в %APPDATA%. Возвращает путь или бросает ошибку."""
        d = os.path.join(self.home, 'voices'); os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f'ru_RU-{v}-medium.onnx')
        for url, out in ((HF.format(v=v) + '.json', dst + '.json'), (HF.format(v=v), dst)):
            tmp = out + '.part'
            with urllib.request.urlopen(url, timeout=30) as r, open(tmp, 'wb') as f:
                total, got = int(r.headers.get('Content-Length') or 0), 0
                while True:
                    b = r.read(1 << 16)
                    if not b: break
                    f.write(b); got += len(b)
                    if progress and total: progress(got / total)
            os.replace(tmp, out)
        return dst

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
        """Двойной сигнал 880 и 1175 Гц с плавными краями, громкость = общая × сигнал."""
        rate, k = 22050, 0.6 * self.beep_volume * self.master / 10000
        a = array.array('h')
        for f, ms in ((880, 120), (0, 30), (1175, 160)):
            n = rate * ms // 1000
            for i in range(n):
                env = min(1, i / 200, (n - i) / 200)
                a.append(int(32767 * k * env * math.sin(2 * math.pi * f * i / rate)) if f else 0)
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
