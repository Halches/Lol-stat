"""Одна конфигурация упаковки для проверочного EXE и выпуска."""
import argparse,os,re,subprocess,sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--name',default='LoLHelper');args=parser.parse_args()
    if os.name!='nt':parser.error('Windows EXE собирается на Windows')
    root=Path(__file__).resolve().parent.parent;os.chdir(root)
    version=(root/'app/release-version.txt').read_text().strip()
    if not re.fullmatch(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)',version):raise ValueError('Неверный номер выпуска')
    (root/'app/version.txt').write_text(version,encoding='ascii')
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--noconsole','--name',args.name,'--paths','app','--exclude-module','tkinter','--exclude-module','PyQt5','--exclude-module','PyQt6']
    for module in ('edge_tts','webview','clr_loader','pythonnet'):command+=['--collect-all',module]
    command+=['--collect-data','certifi','--hidden-import','clr','--hidden-import','sitewin','--hidden-import','qt_review']
    for source,target in [('app/data.json','.'),('app/history-details.json','.'),('app/champion_catalog.json','.'),('app/assets.json','.'),('app/version.txt','.'),('app/fonts','fonts'),('app/ui_assets','ui_assets'),('app/qt_ui/painted','qt_ui/painted'),('app/qt_ui/fonts','qt_ui/fonts'),('app/icon.png','.'),('piper','piper'),('voices','voices')]:
        if not Path(source).exists():raise FileNotFoundError(source)
        command+=['--add-data',source+';'+target]
    command+=['--icon','app/icon.ico','app/lolhelper.py'];subprocess.run(command,check=True)

if __name__=='__main__':main()
