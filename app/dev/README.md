# Проверка окон без игры

Скрипты запускают настоящий `ui.App` с подставными данными клиента и делают скриншоты (Linux, Xvfb, ImageMagick `import`).

```bash
mkdir -p /tmp/simhome/.fonts && cp app/fonts/*.ttf /tmp/simhome/.fonts/ && HOME=/tmp/simhome fc-cache -f
cd app/dev
HOME=/tmp/simhome APPDATA=/tmp/simhome SIM_OUT=/tmp xvfb-run -a -s "-screen 0 1920x1080x24" python3.12 sim_dash.py draft   # драфт: n_draft_dash.png, n_hints.png, n_review.png, n_edit.png
HOME=/tmp/simhome APPDATA=/tmp/simhome SIM_OUT=/tmp xvfb-run -a -s "-screen 0 1920x1080x24" python3.12 sim_dash.py game    # игра: n_dash.png, n_tab*.png
HOME=/tmp/simhome APPDATA=/tmp/simhome SIM_OUT=/tmp xvfb-run -a -s "-screen 0 1920x1080x24" python3.12 sim_main.py 0       # главное окно, вкладка 0
```

Шрифты копируются в `~/.fonts`, потому что на Linux Tk не видит шрифты из папки программы (на Windows их подключает `load_fonts`).

## Рейтинг инвентаря и ручка Tab

`SIM_OUT=/tmp xvfb-run -a -s "-screen 0 1920x1080x24" python3 app/dev/sim_overlays.py`

Запускать из корня репозитория. Не требует игры, Riot API и сетевых запросов.
Проверяет перенос/размер через отдельную ручку, сохранение и её скрытие; сохраняет
скриншоты светлой и тёмной тем. На Windows дополнительно проверить: клики по самой
таблице при Tab+Alt проходят в игру, ручка не забирает фокус, работают DPI 100/125/150%.
