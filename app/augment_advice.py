"""Static, explainable augment advice for the two League modes."""
import json
import re
from collections import defaultdict
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'augment_data'
STRONG_SYNERGY = 'Сильная синергия'
CLASS_COMPATIBILITY = 'Подходит классу'
WEAK_SYNERGY = 'Слабая синергия'
UNKNOWN_SYNERGY = 'Нет оценки синергии'


def mode_for(game_mode, queue_id):
    if queue_id == 2400:
        return 'mayhem'
    if game_mode == 'CHERRY' or queue_id in (1700, 1710, 1750):
        return 'arena'
    return None


def normalized(name):
    return re.sub(r'[^а-яa-z0-9]', '', name.casefold().replace('ё', 'е'))


@lru_cache(maxsize=2)
def names(mode):
    cards = json.loads((DATA / 'catalog.json').read_text(encoding='utf-8'))['cards']
    candidates = defaultdict(list)
    observed_arena = arena_popularity()['picks'] if mode == 'arena' else {}
    for card in cards:
        if mode == 'arena' and not card['arena'] and card['key'] not in observed_arena:
            continue
        for value in {normalized(card['ru']), normalized(card['en'])} - {''}:
            candidates[value].append(card)
    lookup = {}
    for name, rows in candidates.items():
        if mode == 'mayhem':
            specific = [r for r in rows if not r['arena']]
            rows = specific or rows
        if len(rows) == 1:
            lookup[name] = rows[0]
    return lookup


@lru_cache(maxsize=2048)
def identify(mode, text):
    name = normalized(text)
    catalog = names(mode)
    if name in catalog:
        return catalog[name]
    if len(name) < 7 or len(name) > 48:
        return None
    hits = get_close_matches(name, catalog, n=2, cutoff=.90)
    return catalog[hits[0]] if len(hits) == 1 else None


# The champion classes are from Data Dragon. Narrow mechanics use explicit
# champion lists so a generic Support tag cannot imply a heal or a shield.
AUTO = {'Marksman'}
AP = {'Mage'}
FRONT = {'Tank'}
HEALERS = set('Ivern Janna Karma Lulu Milio Nami Renata Seraphine Sona Soraka Taric Yuumi'.split())
DOT = set('Brand Cassiopeia Lillia Malzahar Mordekaiser Singed Swain Teemo Zyra'.split())
CONTROL = set('Alistar Amumu Leona Maokai Nautilus Ornn Rell Sejuani Skarner Zac'.split())
DASH = set('Ahri Akali Ambessa Diana Ekko Ezreal Fiora Fizz Irelia Kalista Kassadin Katarina Kled Leblanc Lucian Riven Samira Vayne Yasuo Yone'.split())

# Exact mechanics take precedence over generic category information.
RULES = [
    ('Deft TapDancer LightemUp Firebrand DualWield TwiceThrice', AUTO, {'Jax', 'MasterYi', 'Tryndamere', 'Warwick', 'Belveth', 'Trundle'}, 'Эффект раскрывается при частых автоатаках.'),
    ('Archmage WitchfulThinking Eureka BigBrain ADAPt', AP, (), 'Хорошо сочетается со сборкой через силу умений.'),
    ('MagicMissile InfernalConduit JeweledGauntlet', AP, (), 'Подходит для урона от частых попаданий умениями.'),
    ('Goliath HeavyHitter CelestialBody', FRONT, (), 'Сочетается со сборкой через запас здоровья.'),
    ('CriticalHealing AllForYou FirstAidKit', (), HEALERS, 'Усиливает лечение или щиты в комплекте чемпиона.'),
    ('Vulnerability InfernalConduit', (), DOT, 'Сочетается с периодическим уроном чемпиона.'),
    ('SlapAround Cruelty CourageoftheColossus GuiltyPleasure Impassable', (), CONTROL, 'Чемпион регулярно обездвиживает противников.'),
    ('Dashing Earthwake', (), DASH, 'Чемпион может часто использовать рывки или скачки.'),
]
CATEGORIES = {
    'Damage': 'Для урона', 'Resilience': 'Для выживаемости', 'Speed': 'Для мобильности',
    'Ally': 'Для помощи команде', 'Utility': 'Для полезных эффектов',
    'Economy': 'Для экономики', 'Quest': 'Задание', 'Questline': 'Цепочка заданий',
    'StatAnvil': 'Для наковален характеристик',
}


@lru_cache(maxsize=1)
def popularity():
    return json.loads((DATA / 'mayhem_picks.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def arena_popularity():
    return json.loads((DATA / 'arena_picks.json').read_text(encoding='utf-8'))


def explain(card, mode, champion, classes):
    key = card['key'].removeprefix('ARAM_')
    heading, reason = UNKNOWN_SYNERGY, 'Отдельная синергия для чемпиона пока не оценена.'
    for keys, tags, champions, note in RULES:
        if key not in keys.split():
            continue
        if champion in champions:
            heading, reason = STRONG_SYNERGY, note
            break
        if heading == UNKNOWN_SYNERGY and set(tags).intersection(classes):
            heading, reason = CLASS_COMPATIBILITY, note
    if heading == UNKNOWN_SYNERGY:
        labels = [CATEGORIES[tag] for tag in card['tags'] if tag in CATEGORIES]
        if labels:
            reason = ' · '.join(labels[:2])
    if mode == 'mayhem':
        source = popularity()
        pairing = source['champion_pairs'].get(champion, {}).get(card['en'])
        if pairing == 'trap':
            heading, reason = WEAK_SYNERGY, 'ARAM Mayhem отмечает слабое сочетание с этим чемпионом.'
        elif pairing == 'strong':
            if heading == UNKNOWN_SYNERGY:
                reason = 'Сильное сочетание по оценке ARAM Mayhem.'
            heading = STRONG_SYNERGY
    return heading, reason
