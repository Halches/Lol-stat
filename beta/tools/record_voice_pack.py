"""Prepare immutable Russian recordings. This tool is never run by the app.

Run from beta: python tools/record_voice_pack.py --voices svetlana
"""
import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop.voice_catalog import PHRASES, VOICES, asset_root


def validate(path):
    if path.stat().st_size < 1000:
        raise ValueError(f"Empty recording: {path}")
    # Edge's word boundary metadata is not required at runtime.
    return None


def entry(path, phrase):
    validate(path)
    return {"textHash": sha256(PHRASES[phrase].encode("utf-8")).hexdigest(),
            "bytes": path.stat().st_size, "sha256": sha256(path.read_bytes()).hexdigest()}


def reusable(path, phrase, cached):
    try:
        return (cached.get("textHash") == sha256(PHRASES[phrase].encode("utf-8")).hexdigest()
                and path.stat().st_size == cached.get("bytes") and path.stat().st_size >= 1000
                and sha256(path.read_bytes()).hexdigest() == cached.get("sha256"))
    except OSError:
        return False


def save_manifest(root, manifest):
    temporary = root / "manifest.json.part"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(root / "manifest.json")


async def record_phrase(root, voice, phrase, manifest, limit, attempts=5):
    import edge_tts
    path = root / voice / f"{phrase}.mp3"
    cached = manifest["voices"].setdefault(voice, {}).get(phrase, {})
    if reusable(path, phrase, cached):
        return
    async with limit:
        temporary = path.with_suffix(".part.mp3")
        for attempt in range(attempts):
            try:
                await asyncio.wait_for(edge_tts.Communicate(PHRASES[phrase], VOICES[voice]["speaker"], rate="+0%").save(str(temporary)), 25)
                validate(temporary)
                temporary.replace(path)
                manifest["voices"][voice][phrase] = entry(path, phrase)
                # There is no await during the atomic save; tasks cannot race here.
                save_manifest(root, manifest)
                print(f"{voice}: {phrase}", flush=True)
                return
            except Exception as error:
                temporary.unlink(missing_ok=True)
                if attempt == attempts - 1:
                    raise RuntimeError(f"{voice}/{phrase}: {type(error).__name__}: {error}") from error
                print(f"Retry {voice}/{phrase}: {type(error).__name__}", flush=True)
                await asyncio.sleep(3 * (attempt + 1))


async def record_pack(root, voices, manifest, jobs, voice_jobs=1, attempts=5):
    limit = asyncio.Semaphore(jobs)
    voice_limits = {voice: asyncio.Semaphore(voice_jobs) for voice in voices}

    async def one(voice, phrase):
        # Interleave voices; avoid concurrent requests to the same voice backend.
        async with voice_limits[voice]:
            return await record_phrase(root, voice, phrase, manifest, limit, attempts)

    results = await asyncio.gather(*(one(voice, phrase) for phrase in PHRASES for voice in voices),
                                   return_exceptions=True)
    failures = [str(result) for result in results if isinstance(result, BaseException)]
    for voice in voices:
        ready = sum(reusable(root / voice / f"{phrase}.mp3", phrase, manifest["voices"][voice].get(phrase, {}))
                    for phrase in PHRASES)
        print(f"Ready: {voice}, {ready}/{len(PHRASES)} phrases", flush=True)
    if failures:
        raise RuntimeError("Incomplete recordings (run again to resume):\n" + "\n".join(failures))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--voices", nargs="+", choices=VOICES, default=list(VOICES))
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--per-voice-jobs", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--attempts", type=int, choices=range(1, 6), default=5)
    args = parser.parse_args()
    root = asset_root()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"version": 1, "voices": {}}
    manifest["voices"] = {key: value for key, value in manifest["voices"].items() if key in VOICES}
    for voice in args.voices:
        (root / voice).mkdir(exist_ok=True)
    save_manifest(root, manifest)
    asyncio.run(record_pack(root, args.voices, manifest, args.jobs, args.per_voice_jobs, args.attempts))


if __name__ == "__main__":
    main()
