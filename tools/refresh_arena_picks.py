"""Build the offline Arena pick counts from the public ggez.gg table (CC BY 4.0)."""
from collections import defaultdict
from datetime import date
from html import unescape
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

DATA = Path(__file__).resolve().parents[1] / 'app' / 'augment_data'
SOURCE = 'https://ggez.gg/tierlist/arena/augments'
LICENSE = 'https://creativecommons.org/licenses/by/4.0/'


def parse_snapshot(page, cards, retrieved):
    summary = re.search(r'All regions · Patch (\d+\.\d+) · ([\d,]+) matches · ([\d,]+) player games', page)
    count = re.search(r'(\d+) augments with at least (\d+) games', page)
    denominator = re.search(r'Share is divided by the ([\d,]+) player games', page)
    table = re.search(r'<table\b[^>]*>.*?<tbody>(.*?)</tbody>', page, re.S)
    if not (summary and count and denominator and table):
        raise ValueError('Изменилась таблица частоты выбора Арены')
    patch, matches, player_games = summary.groups()
    matches, player_games = (int(value.replace(',', '')) for value in (matches, player_games))
    if matches <= 0 or player_games != int(denominator[1].replace(',', '')) or player_games < matches:
        raise ValueError('Некорректный размер выборки Арены')

    def key(name):
        return re.sub(r'[^a-z0-9]', '', name.casefold())

    by_name = defaultdict(list)
    for card in cards:
        by_name[key(card['en'])].append(card)
    picks = {}
    rows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', table[1], re.S)
    if len(rows) != int(count[1]):
        raise ValueError('Получена неполная таблица Арены')
    for row in rows:
        title = re.search(r'<b\b[^>]*>([^<]+)</b>', row)
        picked = re.search(r'<td class="c-n num[^"]*">([\d,]+)</td>', row)
        if not (title and picked):
            raise ValueError('Не удалось прочитать название или число выборов')
        n = int(picked[1].replace(',', ''))
        if not int(count[2]) <= n <= player_games:
            raise ValueError('Число выборов за пределами выборки')
        candidates = by_name[key(unescape(title[1]))]
        matches_for_title = [card for card in candidates if card['arena']] or candidates
        if len(matches_for_title) == 1:
            card_key = matches_for_title[0]['key']
            if card_key in picks:
                raise ValueError(f'Повтор в таблице Арены: {card_key}')
            picks[card_key] = n
    if not picks:
        raise ValueError('Таблица Арены не сопоставилась с каталогом')
    return dict(source=SOURCE, license=LICENSE, patch=patch, date=retrieved,
                matches=matches, player_games=player_games, picks=dict(sorted(picks.items())))


if __name__ == '__main__':
    with urlopen(Request(SOURCE, headers={'User-Agent': 'LoLHelper/catalog'}), timeout=25) as response:
        page = response.read(2_000_000).decode('utf-8')
    cards = json.loads((DATA / 'catalog.json').read_text(encoding='utf-8'))['cards']
    snapshot = parse_snapshot(page, cards, date.today().isoformat())
    target = DATA / 'arena_picks.json'
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(target)
    print(f"{snapshot['patch']}: {len(snapshot['picks'])} аугментаций, {snapshot['player_games']} участий")
