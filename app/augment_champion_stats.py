"""Read only published champion-specific pick frequencies for the two augment modes."""

from dataclasses import dataclass
from html import unescape
import json
import re
from urllib.request import Request, urlopen

from augment_advice import normalized

ARENA = 'https://ggez.gg/champion/'
MAYHEM = 'https://arammayhem.com/build/'


@dataclass(frozen=True)
class ChampionPicks:
    patch: str
    rates: dict[str, float]

    def label(self, card):
        rate = self.rates.get(normalized(card['en']))
        if rate is None:
            return 'Берут: —'
        percent = f'{rate:.2f}'.rstrip('0').rstrip('.').replace('.', ',')
        return f'Берут: {percent}% · {self.patch}'


def _arena(page):
    patch = re.search(r'All regions · Patch (\d+\.\d+)', page)
    augments = re.search(r'\baugments:\[(.*?)\]\s*,', page, re.S)
    if not patch or not augments:
        raise ValueError('Таблица аугментаций чемпиона в Арене недоступна')

    # SvelteKit embeds the data shown on the public Augments tab in the HTML.
    # Read the pickShare field only. Placement and outcome fields are ignored.
    return patch[1], [
        (json.loads(name), float(rate))
        for rate, name in re.findall(
            r'\bpickShare:([\d.]+),name:("(?:[^"\\]|\\.)*")', augments[1])
    ]


def _mayhem(page):
    patch = re.search(r'\bPatch:\s*(\d+\.\d+)', page)
    section = re.search(r'<section\b[^>]*\bid="best-augments"[^>]*>(.*?)</section>', page, re.S)
    if not patch or not section:
        raise ValueError('Таблица аугментаций чемпиона в Хаосе недоступна')

    rows = re.findall(r'<a\b[^>]*href="/augments/[^"]+"[^>]*>(.*?)</a>', section[1], re.S)
    picks = []
    for row in rows:
        title = re.search(r'<div\b[^>]*\btitle="([^"]+)"', row)
        rate = re.search(r'Appearance rate:\s*<span\b[^>]*>\s*([\d.]+)%', row)
        if title and rate:
            picks.append((unescape(title[1]), float(rate[1])))
    return patch[1], picks


def parse_champion_picks(page, mode, canonical_url):
    canonical = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', page)
    if not canonical or canonical[1] != canonical_url:
        raise ValueError('Страница статистики не соответствует запрошенному чемпиону')
    patch, rows = _arena(page) if mode == 'arena' else _mayhem(page)

    rates = {}
    ambiguous = set()
    for name, rate in rows:
        key = normalized(name)
        if key in rates and rates[key] != rate:
            ambiguous.add(key)
        if key and 0 <= rate <= 100:
            rates[key] = rate
    for key in ambiguous:
        rates.pop(key)
    if not rates:
        raise ValueError('Для чемпиона нет частот выбора аугментаций')
    return ChampionPicks(patch, rates)


def fetch_champion_picks(mode, champion):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,31}', champion):
        raise ValueError('Некорректный ключ чемпиона')
    if mode == 'arena':
        url = ARENA + champion + '/arena'
    else:
        url = MAYHEM + champion.lower() + '/'
    with urlopen(Request(url, headers={'User-Agent': 'LoLHelper/augment-stats'}), timeout=6) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError('Таблица статистики слишком большая')
    return parse_champion_picks(data.decode('utf-8'), mode, url)
