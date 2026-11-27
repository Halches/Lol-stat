from pathlib import Path
import json
import sys

desktop = Path(SPECPATH)
beta = desktop.parent
sys.path.insert(0, str(beta))
from desktop.voice_audio import VoicePack

# Ship a consistent snapshot of complete voice sets, never partial recordings
# or temporary files left by an interrupted preparation run.
voice_pack = VoicePack(desktop / "assets/voice-pack")
voice_stage = beta / ".state/packaged-voice-manifest"
voice_stage.mkdir(parents=True, exist_ok=True)
voice_manifest = voice_stage / "manifest.json"
voice_manifest.write_text(json.dumps({"version": 1, "voices": {
    key: voice_pack.manifest["voices"][key] for key in voice_pack.voices
}}, ensure_ascii=False, indent=2), encoding="utf-8")
voice_datas = [(str(voice_manifest), "voice-pack")]
for voice in voice_pack.voices:
    for phrase in voice_pack.manifest["voices"][voice]:
        clip = voice_pack.clip(voice, phrase)
        if clip is not None:
            voice_datas.append((str(clip), f"voice-pack/{voice}"))
a = Analysis(
    [str(desktop / "qt.py")],
    pathex=[str(beta)],
    datas=[(str(beta / ".state/catalog.json"), "."), (str(beta / "web/loadout.json"), "."),
           (str(desktop / "assets/lolhelper-logo.png"), "."),
           (str(desktop / "assets/roles"), "roles"), (str(desktop / "assets/ranks"), "ranks"),
           (str(desktop / "assets/overlay-preview"), "overlay-preview"),
           (str(desktop / "assets/overlay-themes"), "overlay-themes"),
           *voice_datas],
)
# Qt links to Windows ICU. A third-party ICU on the build machine's PATH
# can otherwise be collected and shadow the system DLL.
def is_icu_binary(entry):
    name = Path(entry[0]).name.lower()
    return name.startswith(("icuuc", "icuin", "icudt")) and name.endswith(".dll")


a.binaries = [
    entry for entry in a.binaries if not is_icu_binary(entry)
]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="LoLHelperBeta-Qt", console=False, upx=False,
          icon=str(desktop / "assets/lolhelper-logo.ico"))
