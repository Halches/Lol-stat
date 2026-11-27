# Разбор игр Halch и DrVoldemar

Статистика и разбор игр League of Legends (EUW) по данным Riot API.
Сайт: https://halches.github.io/Lol-stat/

## Автообновление

Workflow `.github/workflows/update.yml` раз в 30 минут спрашивает Riot API, появились ли новые игры.
Если нет, сразу завершается. Если есть, докачивает только их, пересобирает `index.html` и пушит.

Нужен секрет репозитория `RIOT_API_KEY` (Settings → Secrets and variables → Actions).
Дев-ключ живёт сутки, для постоянной работы нужен Personal API Key.
Без секрета workflow просто пропускает запуск. Запустить вручную: Actions → «Обновление игр» → Run workflow.

## Скрипты (`tools/`)

- `fetch.py` — скачивает матчи. С `INCREMENTAL=1` берёт последние 20 игр каждого и качает только те, которых нет в `seen.json`; без него — весь сезон с `SEASON_START`.
- `analyze.py` — считает статистику и добавляет новые игры в `games.json`.
- `icons.py` — иконки и названия из Data Dragon (докачивает только новые в `icons.json`).
- `build.py` — собирает страницу из `template.html`.

## Обновление версии в Claude (с тренером)

Если заданы секреты `CLAUDE_FIRE_URL` и `CLAUDE_FIRE_TOKEN`, после каждой публикации новых игр workflow запускает
задачу Claude «Обновить сайт LoL в Claude», которая перекладывает свежий `index.html` в артефакт.
URL и токен берутся на claude.ai/code/routines → задача → Edit → Trigger → API.

## Windows-приложение LoL Helper v3

Единственная действующая версия приложения находится в `beta/`. Точка входа —
`beta/desktop/qt.py`; общие модули ядра и каталог данных — в `beta/`.
Инструкции по запуску, локальному API и проверкам: [beta/desktop/README.md](beta/desktop/README.md).

Выпуск `LoLHelper.exe` собирает `.github/workflows/app.yml`. Номер версии задаётся
в `beta/desktop/app_version.py`, заметки — в `beta/RELEASE_NOTES.txt`.
Изменения в Git сами по себе не обновляют установленный EXE: нужен опубликованный
GitHub Release с `LoLHelper.exe` и `SHA256SUMS.txt`.

Сайт обновляется отдельно. `tools/make_data.py` собирает `beta/data.json` из данных
сайта; выпуск приложения включает проверенный снимок каталога на момент сборки.

Исходники v1/v2 и их старые workflow сохранены в [архиве](archive/legacy-app/README.md).
Они не участвуют в сборке или проверках v3.
