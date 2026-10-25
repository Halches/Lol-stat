#!/usr/bin/env bash
# Проверка новых игр по кругу: каждые 10 минут, пока не выйдет время (по умолчанию 330 минут).
# GitHub запускает расписание раз в несколько часов, поэтому один запуск сам крутится почти до лимита,
# а следующий плановый ждёт в очереди и подхватывает сразу после. Запуск: из папки tools.
set -u
LOOP_MIN=${LOOP_MIN:-330}
END=$(( $(date +%s) + LOOP_MIN * 60 ))

fire() {   # обновить версию сайта в Claude (рутина «Обновить сайт LoL в Claude»)
  if [ -z "${FIRE_URL:-}" ] || [ -z "${FIRE_TOKEN:-}" ]; then echo "::notice::CLAUDE_FIRE_URL/CLAUDE_FIRE_TOKEN не заданы"; return; fi
  curl -sS -X POST "$FIRE_URL" -H "Authorization: Bearer $FIRE_TOKEN" \
    -H "anthropic-beta: experimental-cc-routine-2026-04-01" -H "anthropic-version: 2023-06-01" \
    -H "Content-Type: application/json" -d '{}' -o fire.json -w "HTTP %{http_code}\n" || echo "::warning::Не удалось запустить обновление в Claude"
  head -c 300 fire.json | sed 's/"[a-z_]*token[a-z_]*":"[^"]*"/"token":"***"/g'; echo
}

rebuild() {
  mkdir -p dd
  V=$(curl -s https://ddragon.leagueoflegends.com/api/versions.json | python -c "import json,sys;print(json.load(sys.stdin)[0])")
  echo "$V" > dd/ver
  for f in champion item summoner; do curl -s -o dd/$f.json https://ddragon.leagueoflegends.com/cdn/$V/data/ru_RU/$f.json; done
  curl -s -o dd/runes.json https://ddragon.leagueoflegends.com/cdn/$V/data/ru_RU/runesReforged.json
  python analyze.py && python icons.py || return 1
  # средние Изумруд+ с lolalytics: обновлять раз в 3 дня
  python -c "import json,time,sys;t=json.load(open('lola.json')).get('_t','2000-01-01');sys.exit(0 if time.time()-time.mktime(time.strptime(t,'%Y-%m-%d'))>3*86400 else 1)" && python lola.py || true
  python build.py && python ../app/make_data.py
}

publish() {
  (cd .. &&
   git add index.html data tools/games.json tools/icons.json tools/seen.json tools/ranks.json tools/lp_history.json tools/lola.json app/data.json &&
   { git commit -q -m "Новые игры: $1" || exit 0; } &&
   for i in 1 2 3; do git pull --rebase --autostash -q origin main && git push -q && exit 0; sleep 5; done; exit 1) || return 1
  gh api -X POST "repos/$GITHUB_REPOSITORY/pages/builds" > /dev/null || true
}

[ "${TEST_FIRE:-false}" = "true" ] && fire
while :; do
  out=$(mktemp)
  GITHUB_OUTPUT=$out python fetch.py
  new=$(sed -n 's/^new=//p' "$out" | tail -1); rm -f "$out"
  echo "$(date -u +%H:%M) новых игр: ${new:-?}"
  if [ -n "$new" ] && [ "$new" != "0" ]; then
    # версию в Claude обновляем только по просьбе в чате, автоматически не запускаем
    rebuild && publish "$new" || echo "::error::Не удалось пересобрать или опубликовать $new игр"
  fi
  [ $(( $(date +%s) + 600 )) -lt "$END" ] || break
  sleep 600
done
