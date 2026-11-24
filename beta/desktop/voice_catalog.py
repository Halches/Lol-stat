"""Finite Russian phrases: the game plays recordings, never synthesizes speech."""
from dataclasses import dataclass
from pathlib import Path
import sys


ROLES = {"TOP": "Верх", "JUNGLE": "Лес", "MIDDLE": "Центр", "BOTTOM": "Низ", "UTILITY": "Поддержка"}
LANES = ("TOP", "MIDDLE", "BOTTOM", "UTILITY")


@dataclass(frozen=True)
class Topic:
    key: str
    title: str
    description: str
    phrases: tuple
    roles: tuple = ()  # Empty means one common setting for every role.
    default: bool = True


TOPICS = (
    Topic("jungler", "Вражеский лесник", "Оценка по чемпиону, без определения его местоположения.",
          ("jungler_early", "jungler_farm", "jungler_normal"), LANES),
    Topic("trinket", "Пустой слот тотема", "В начале матча, если у игрока нет тотема.", ("trinket",)),
    Topic("early_ward", "Первый вард", "Отдельная подсказка для линии, леса и поддержки.",
          ("ward_jungle", "ward_support", "ward_lane"), tuple(ROLES)),
    Topic("crab", "Речные крабы", "Перед первым появлением: напоминание проверить приоритет линий.", ("crab",), ("JUNGLE",)),
    Topic("ganks", "Возможные ганки", "Ориентиры первых минут. Маршрут лесника не подтверждён.", ("gank",), LANES),
    Topic("jg_seen", "Лесник участвовал в убийстве", "Только по событию матча; место события не определяется.", ("jg_seen",), LANES),
    Topic("cs_norm", "Фарм ниже цели", "На 5, 10 и 15 минуте. Сравнение с целью, заданной ниже.", ("cs",),
          ("TOP", "JUNGLE", "MIDDLE", "BOTTOM"), False),
    Topic("levels", "Преимущество по уровню", "Второй, третий и шестой уровень относительно оппонента с известной ролью.",
          ("level_2", "level_3", "level_6", "enemy_level_2", "enemy_level_3", "enemy_level_6"), LANES),
    Topic("skills", "Свободное очко умения", "Напоминание при повышении уровня, если очко ещё не потрачено.", ("skills",)),
    Topic("early_deaths", "Две ранние смерти", "Две смерти до четырнадцатой минуты.", ("early_deaths",)),
    Topic("hoard", "Накопленное золото", "От двух тысяч золота после пятой минуты; повтор не чаще двух минут.", ("hoard",)),
    Topic("control", "Контрольные тотемы", "После покупки: проверить запас тотемов, если есть золото и место.", ("control",)),
    Topic("lens", "Выбор линзы", "Предмет поддержки даёт варды, но выбран жёлтый тотем.", ("lens",), ("UTILITY",)),
    Topic("enemy_item", "Предмет оппонента", "Оппонент с известной ролью закончил предмет.", ("enemy_item",), LANES),
    Topic("powerspike", "Собранный предмет", "Игрок закончил предмет. Название предмета не озвучивается.", ("item",)),
    Topic("objectives", "Таймеры объектов", "Дракон, личинки, Герольд и Барон: за минуту и тридцать секунд.",
          tuple(f"{obj}_{lead}" for obj in ("dragon", "elder", "grubs", "herald", "baron") for lead in (60, 30))),
    Topic("tp", "Телепорт к дракону", "Проверить доступность телепорта; его перезарядка не определяется.", ("tp",), ("TOP",)),
    Topic("baron_jungle", "Осторожность перед Бароном", "Перед появлением Барона: не заходить в лес одному.", ("baron_jungle",)),
    Topic("fight_won", "Перевес по недавним убийствам", "Повод оценить объекты; доступность объекта не подтверждается.", ("fight_won",)),
    Topic("inhib", "Восстановление ингибитора", "За минуту до восстановления по событию уничтожения.", ("inhib",)),
    Topic("cannon", "Осадная волна", "Появление волны на базе до четырнадцатой минуты, не её приход на линию.",
          ("cannon",), ("TOP", "MIDDLE", "BOTTOM"), False),
)

PHRASES = {
    "sample": "Голосовой помощник готов. Дракон через тридцать секунд.",
    "jungler_early": "Лесник врагов может ганкнуть рано. Оценка по чемпиону.",
    "jungler_farm": "Лесник врагов часто выбирает фарм, но ранний ганк возможен.",
    "jungler_normal": "У вражеского лесника обычный темп.",
    "trinket": "Купи тотем.",
    "ward_jungle": "Вард у входа в свой лес.",
    "ward_support": "Вард в речной куст.",
    "ward_lane": "Первый вард ставь с учётом волны и миникарты.",
    "crab": "Крабы скоро, проверь приоритет линий.",
    "gank": "Возможен ганк, проверь миникарту и обзор.",
    "jg_seen": "Лесник участвовал в убийстве, проверь миникарту.",
    "cs": "Отстаёшь по фарму от выбранной цели.",
    "level_2": "Второй уровень раньше оппонента, дави.",
    "level_3": "Третий уровень раньше оппонента, дави.",
    "level_6": "Шестой уровень раньше оппонента, дави.",
    "enemy_level_2": "У оппонента второй уровень, отойди.",
    "enemy_level_3": "У оппонента третий уровень, отойди.",
    "enemy_level_6": "У оппонента шестой уровень, отойди.",
    "skills": "Проверь очко умения и порядок сборки.",
    "early_deaths": "Две ранние смерти, играй от варда.",
    "hoard": "Две тысячи золота или больше. Подумай о возвращении на базу.",
    "control": "Проверь запас контрольных тотемов.",
    "lens": "Предмет поддержки даёт варды, проверь выбор линзы.",
    "enemy_item": "Оппонент собрал предмет.",
    "item": "Собран предмет, пик силы.",
    "tp": "Скоро дракон. Проверь доступность телепорта и безопасную цель.",
    "baron_jungle": "Барон скоро, не заходи в лес один.",
    "fight_won": "Есть перевес по недавним убийствам, проверь объекты.",
    "inhib": "Ингибитор восстановится через минуту.",
    "cannon": "Осадная волна скоро появится на базе.",
}
for _obj, _name in (("dragon", "Дракон"), ("elder", "Древний дракон"), ("grubs", "Личинки"),
                    ("herald", "Герольд"), ("baron", "Барон")):
    PHRASES[f"{_obj}_60"] = f"{_name} через минуту."
    PHRASES[f"{_obj}_30"] = f"{_name} через тридцать секунд."

VOICES = {
    "svetlana": {"name": "Светлана · женский", "engine": "edge", "speaker": "ru-RU-SvetlanaNeural", "extension": "mp3"},
    "ava": {"name": "Ава · женский", "engine": "edge", "speaker": "en-US-AvaMultilingualNeural", "extension": "mp3"},
    "emma": {"name": "Эмма · женский", "engine": "edge", "speaker": "en-US-EmmaMultilingualNeural", "extension": "mp3"},
    "andrew": {"name": "Эндрю · мужской", "engine": "edge", "speaker": "en-US-AndrewMultilingualNeural", "extension": "mp3"},
    "brian": {"name": "Брайан · мужской", "engine": "edge", "speaker": "en-US-BrianMultilingualNeural", "extension": "mp3"},
}


def asset_root():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "voice-pack"
    return Path(__file__).resolve().parent / "assets" / "voice-pack"


def setting_key(topic, role=""):
    return f"assistant/topics/{role or 'common'}/{topic}"
