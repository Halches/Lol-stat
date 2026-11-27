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
  python build.py && python make_data.py
}

publish() {
  local message="$1"
  shift
  (
    cd .. || exit 1
    git add "$@" || exit 1
    git diff --cached --quiet && exit 0
    git commit -q -m "$message" || exit 1
    for i in 1 2 3; do
      git pull --rebase --autostash -q origin main && git push -q && exit 0
      sleep 5
    done
    exit 1
  )
}

[ "${TEST_FIRE:-false}" = "true" ] && fire
while :; do
  out=$(mktemp)
  GITHUB_OUTPUT=$out python fetch.py || { rm -f "$out"; exit 1; }
  GITHUB_OUTPUT=$out python arena.py || echo "::warning::Не удалось собрать игры Арены"
  new=$(sed -n 's/^new=//p' "$out" | tail -1); ar=$(sed -n 's/^arena=//p' "$out" | tail -1); rm -f "$out"
  echo "$(date -u +%H:%M) новых игр: ${new:-?}, Арена: ${ar:-?}"
  new=$(( ${new:-0} + ${ar:-0} ))
  if [ "$new" != "0" ]; then
    # версию в Claude обновляем только по просьбе в чате, автоматически не запускаем
    rebuild && python fetch.py --acknowledge || exit 1
    publish "Новые игры: $new" index.html data tools/{games,icons,seen,pending_matches,ranks,mastery,lp_history,lola,arena}.json beta/data.json || exit 1
    gh api -X POST "repos/$GITHUB_REPOSITORY/pages/builds" > /dev/null || true
  elif ! git diff --quiet -- seen.json pending_matches.json || ! git ls-files --error-unmatch pending_matches.json >/dev/null 2>&1; then
    publish "Обновить очередь загрузки матчей" tools/{seen,pending_matches}.json || exit 1
  fi
  [ $(( $(date +%s) + 600 )) -lt "$END" ] || break
  sleep 600
done
