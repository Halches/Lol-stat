"""Деревья и слоты из Riot Data Dragon 16.23.1, data/en_US/runesReforged.json."""

SLOTS = {
    8100: (
        (8112, 8128, 9923),
        (8126, 8139, 8143),
        (8137, 8140, 8141),
        (8135, 8105, 8106),
    ),
    8300: (
        (8351, 8360, 8369),
        (8306, 8304, 8321),
        (8313, 8352, 8345),
        (8347, 8410, 8316),
    ),
    8000: (
        (8005, 8008, 8021, 8010),
        (9101, 9111, 8009),
        (9104, 9105, 9103),
        (8014, 8017, 8299),
    ),
    8400: (
        (8437, 8439, 8465),
        (8446, 8463, 8401),
        (8429, 8444, 8473),
        (8451, 8453, 8242),
    ),
    8200: (
        (8214, 8229, 8230, 8992),
        (8224, 8226, 8275),
        (8210, 8234, 8233),
        (8237, 8232, 8236),
    ),
}
TREE = {perk: tree for tree, slots in SLOTS.items() for slot in slots for perk in slot}


def valid_page(primary, secondary, perks, shards):
    if primary not in SLOTS or secondary not in SLOTS or primary == secondary:
        return False
    if len(perks) != 6 or len(shards) != 3:
        return False
    if not all(perk in slot for perk, slot in zip(perks[:4], SLOTS[primary])):
        return False
    secondary_rows = [slot for slot in SLOTS[secondary][1:] if any(p in slot for p in perks[4:])]
    shard_rows = ((5008, 5005, 5007), (5008, 5010, 5001), (5011, 5013, 5001))
    return len(secondary_rows) == 2 and all(p in row for p, row in zip(shards, shard_rows))
