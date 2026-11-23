from pathlib import Path

desktop = Path(SPECPATH)
beta = desktop.parent
a = Analysis(
    [str(desktop / "qt.py")],
    pathex=[str(beta.parent / "app"), str(beta)],
    datas=[(str(beta / ".state/catalog.json"), "."), (str(beta / "web/loadout.json"), "."),
           (str(desktop / "assets/lolhelper-logo.png"), "."),
           (str(desktop / "assets/roles"), "roles"), (str(desktop / "assets/ranks"), "ranks"),
           (str(desktop / "assets/overlay-preview"), "overlay-preview"),
           (str(desktop / "assets/overlay-themes"), "overlay-themes")],
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
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="LoLHelperBeta-Qt", console=False, upx=False)
