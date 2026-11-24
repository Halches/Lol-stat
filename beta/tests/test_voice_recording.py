"""Recording can resume a partial voice without keeping stale or corrupt audio."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from tools import record_voice_pack as recorder


class RecordingTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_failure_keeps_completed_recordings_and_resume_skips_them(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "svetlana").mkdir()
            manifest = {"version": 1, "voices": {}}
            phrases = {"first": "Первая фраза.", "second": "Вторая фраза."}
            calls = []
            failing = [True]

            class Communicate:
                def __init__(self, text, *_args, **_kwargs):
                    self.text = text

                async def save(self, filename):
                    calls.append(self.text)
                    if self.text == phrases["first"] and failing[0]:
                        raise ConnectionError("Fixture provider unavailable")
                    Path(filename).write_bytes(self.text.encode("utf-8") * 100)

            with (patch.dict("sys.modules", {"edge_tts": SimpleNamespace(Communicate=Communicate)}),
                  patch.object(recorder, "PHRASES", phrases),
                  patch.object(recorder.asyncio, "sleep", new=AsyncMock())):
                with self.assertRaisesRegex(RuntimeError, "Incomplete recordings"):
                    await recorder.record_pack(root, ["svetlana"], manifest, 2)
                saved = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
                self.assertIn("second", saved["voices"]["svetlana"])
                self.assertNotIn("first", saved["voices"]["svetlana"])
                self.assertEqual(calls.count(phrases["second"]), 1)
                failing[0] = False
                await recorder.record_pack(root, ["svetlana"], saved, 2)
                self.assertEqual(calls.count(phrases["second"]), 1)
                self.assertTrue(recorder.reusable(root / "svetlana/first.mp3", "first", saved["voices"]["svetlana"]["first"]))

    async def test_changed_text_regenerates_audio_instead_of_relabelling_old_file(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "svetlana").mkdir()
            path = root / "svetlana/line.mp3"
            path.write_bytes(b"old recording" * 100)
            manifest = {"voices": {"svetlana": {"line": {
                "textHash": sha256("Старый текст".encode()).hexdigest(),
                "sha256": sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}}}}
            phrases = {"line": "Новый текст"}

            class Communicate:
                def __init__(self, *_args, **_kwargs):
                    pass

                async def save(self, filename):
                    Path(filename).write_bytes(b"new recording" * 100)

            with (patch.dict("sys.modules", {"edge_tts": SimpleNamespace(Communicate=Communicate)}),
                  patch.object(recorder, "PHRASES", phrases)):
                self.assertFalse(recorder.reusable(path, "line", manifest["voices"]["svetlana"]["line"]))
                await recorder.record_pack(root, ["svetlana"], manifest, 1)
                self.assertEqual(path.read_bytes(), b"new recording" * 100)
                self.assertTrue(recorder.reusable(path, "line", manifest["voices"]["svetlana"]["line"]))
                path.write_bytes(b"bad recording" * 100)  # Same size, different content.
                self.assertFalse(recorder.reusable(path, "line", manifest["voices"]["svetlana"]["line"]))


if __name__ == "__main__":
    unittest.main()
