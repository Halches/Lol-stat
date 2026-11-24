"""Bounded, cancellable playback of local files; no synthesis in the game."""
from collections import deque
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import threading
import time
import uuid

from .voice_catalog import PHRASES, VOICES, asset_root


class VoicePack:
    def __init__(self, root=None):
        self.root = Path(root) if root else asset_root()
        try:
            self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.manifest = {}
        if not isinstance(self.manifest, dict) or not isinstance(self.manifest.get("voices", {}), dict):
            self.manifest = {}
        self.voices = {}
        for key, metadata in VOICES.items():
            if all(self.clip(key, phrase) is not None for phrase in PHRASES):
                self.voices[key] = metadata

    def clip(self, voice, phrase):
        if voice not in VOICES or phrase not in PHRASES:
            return None
        recordings = self.manifest.get("voices", {}).get(voice, {})
        if not isinstance(recordings, dict):
            return None
        entry = recordings.get(phrase, {})
        if not isinstance(entry, dict):
            return None
        if entry.get("textHash") != sha256(PHRASES[phrase].encode("utf-8")).hexdigest():
            return None
        path = self.root / voice / f"{phrase}.{VOICES[voice]['extension']}"
        try:
            if path.stat().st_size == entry.get("bytes") and path.stat().st_size > 100:
                return path
        except OSError:
            pass
        return None


class WindowsAudio:
    def __init__(self):
        import ctypes
        self.ctypes = ctypes
        self.mci = ctypes.windll.winmm.mciSendStringW
        self.alias = "lhvoice" + uuid.uuid4().hex

    def command(self, text):
        result = self.ctypes.create_unicode_buffer(128)
        error = self.mci(text, result, len(result), 0)
        if error:
            raise OSError(f"Windows audio: {error}")
        return result.value

    def play(self, path, volume, cancelled):
        try:
            self.command(f'open "{path}" type mpegvideo alias {self.alias}')
            self.command(f"setaudio {self.alias} volume to {round(max(0, min(100, volume)) * 10)}")
            if cancelled.wait(0):
                return
            self.command(f"play {self.alias}")
            deadline = time.monotonic() + 25
            while not cancelled.wait(.04):
                if self.command(f"status {self.alias} mode") != "playing":
                    return
                if time.monotonic() > deadline:
                    raise TimeoutError("Запись не завершилась вовремя")
        finally:
            self.mci(f"close {self.alias}", None, 0, 0)


@dataclass(frozen=True)
class PendingClip:
    path: Path
    phrase: str
    volume: int
    expires: float
    priority: int
    generation: int


class ClipPlayer:
    def __init__(self, backend_factory=WindowsAudio, on_error=None, on_play=None):
        self.factory = backend_factory
        self.on_error, self.on_play = on_error, on_play
        self.pending = deque()
        self.condition = threading.Condition()
        self.cancelled = threading.Event()
        self.closed = False
        self.generation = 0
        self.current_phrase = None
        self.thread = threading.Thread(target=self._run, name="voice-recordings", daemon=True)
        self.thread.start()

    def submit(self, path, phrase, volume, *, priority=0, ttl=5):
        with self.condition:
            if self.closed or volume <= 0:
                return
            if any(job.phrase == phrase for job in self.pending):
                return
            self.pending.append(PendingClip(Path(path), phrase, volume, time.monotonic() + ttl, priority, self.generation))
            # Keep the two most useful pending messages, never an unbounded backlog.
            self.pending = deque(sorted(self.pending, key=lambda job: job.priority, reverse=True)[:2])
            self.condition.notify()

    def stop(self):
        with self.condition:
            self.generation += 1
            self.pending.clear()
            self.cancelled.set()
            self.condition.notify()

    def retain(self, phrases):
        with self.condition:
            self.pending = deque(job for job in self.pending if job.phrase in phrases)
            if self.current_phrase is not None and self.current_phrase not in phrases:
                self.cancelled.set()

    def close(self):
        with self.condition:
            self.closed = True
        self.stop()
        self.thread.join(timeout=1)

    def _run(self):
        backend = None
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.pending or self.closed)
                if self.closed:
                    return
                job = self.pending.popleft()
                if job.generation != self.generation or time.monotonic() > job.expires:
                    continue
                self.cancelled = cancel = threading.Event()
                self.current_phrase = job.phrase
            try:
                if backend is None:
                    backend = self.factory()
                if not cancel.is_set():
                    if self.on_play:
                        self.on_play(job.phrase)
                    backend.play(job.path, job.volume, cancel)
            except Exception as error:
                if self.on_error:
                    self.on_error(str(error))
            finally:
                with self.condition:
                    self.current_phrase = None
