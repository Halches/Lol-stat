# Разбор игр Halch и DrVoldemar

Статистика и разбор игр League of Legends (EUW) по данным Riot API.
Сайт: https://halches.github.io/Lol-stat/

`tools/` — скрипты сборки: fetch.py (скачать матчи сезона, нужен RIOT_API_KEY в окружении; SEASON_START — unix-время начала) → analyze.py → icons.py → build.py (собирает страницу из template.html).
