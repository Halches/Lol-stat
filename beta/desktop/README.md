# Windows-бета LoL Helper

Команды запуска из каталога `beta` в PowerShell.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install PySide6-Essentials==6.12.0
.\.venv\Scripts\python desktop/qt.py
```

Откройте клиент League of Legends EUW, чтобы загрузить профиль и историю. Адрес сервиса разборов задаётся во вкладке «Настройки».

Проверка логики и запуска окна.

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -p test_desktop.py
.\.venv\Scripts\python desktop/qt.py --smoke
```

Для сборки отдельного EXE используйте спецификацию Qt из этой директории.

```powershell
.\.venv\Scripts\python -m pip install pyinstaller
New-Item -ItemType Directory -Path .state -Force | Out-Null
.\.venv\Scripts\python desktop/worker.py --catalog .state/catalog.json
.\.venv\Scripts\python -m PyInstaller --noconfirm --workpath .state/qt-build --distpath out desktop/qt.spec
```
