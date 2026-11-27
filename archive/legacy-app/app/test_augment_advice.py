import unittest
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw, ImageFont
from augment_advice import DATA, explain, identify, mode_for
from augment_champion_stats import ARENA, MAYHEM, ChampionPicks, parse_champion_picks
from augment_scan import Line, Reader, region, selection
from qt_ui.augment_overlay import AugmentOverlay


class AugmentTests(unittest.TestCase):
    def test_mode_is_specific(self):
        self.assertEqual(mode_for('ARAM', 2400), 'mayhem')
        self.assertEqual(mode_for('CHERRY', None), 'arena')
        self.assertEqual(mode_for('', 1750), 'arena')
        for mode, queue in [('ARAM', 450), ('ARAM', None), ('TFT', 1100), ('CLASSIC', 420)]:
            self.assertIsNone(mode_for(mode, queue))

    def test_rules_and_curated_advice_are_mode_scoped(self):
        card = identify('arena', 'Проворство')
        self.assertEqual(explain(card, 'arena', 'Jinx', ['Marksman'])[0], 'Подходит классу')
        self.assertEqual(explain(card, 'arena', 'Jax', ['Fighter'])[0], 'Сильная синергия')
        self.assertEqual(explain(card, 'arena', 'Rammus', ['Tank'])[0], 'Нет оценки синергии')
        card = identify('mayhem', 'Marksmage')
        self.assertEqual(explain(card, 'mayhem', 'Shyvana', ['Fighter'])[0], 'Слабая синергия')
        self.assertIsNone(identify('arena', 'Spiritual Purification'))

    def test_arena_champion_pick_is_read_without_outcomes(self):
        url = ARENA + 'Jinx/arena'
        page = (f'<link rel="canonical" href="{url}">All regions · Patch 26.23 '
                'augments:[{games:10,top3Rate:95,pickShare:13.5,name:"Firebrand"}],')
        stats = parse_champion_picks(page, 'arena', url)
        self.assertEqual(stats.label(identify('arena', 'Firebrand')), 'Берут: 13,5% · 26.23')
        self.assertEqual(stats.label(identify('arena', 'Deft')), 'Берут: —')
        with self.assertRaises(ValueError):
            parse_champion_picks(page, 'arena', ARENA + 'Shyvana/arena')

    def test_mayhem_only_reads_augments_from_champion_section(self):
        url = MAYHEM + 'shyvana/'
        page = (f'<link rel="canonical" href="{url}">Patch: 26.22'
                '<section id="best-augments"><a href="/augments/goliath/">'
                '<div title="Goliath">Goliath</div>Appearance rate: <span>8.39%</span>'
                '</a></section>Win Rate: <span>85%</span>')
        stats = parse_champion_picks(page, 'mayhem', url)
        self.assertEqual(stats.label(identify('mayhem', 'Goliath')), 'Берут: 8,39% · 26.22')
        self.assertEqual(stats.label(identify('mayhem', 'Marksmage')), 'Берут: —')

    def test_champion_picks_cache_keeps_heroes_and_modes_separate(self):
        overlay = object.__new__(AugmentOverlay)
        overlay.champion_picks = {('arena', 'Jinx'): (600, ChampionPicks('26.23', {'firebrand': 13.5}))}
        overlay.picks_pending = False
        overlay.app = SimpleNamespace(background=Mock())
        overlay.load_picks('arena', 'Jinx', 50)
        overlay.app.background.assert_not_called()
        overlay.load_picks('mayhem', 'Jinx', 50)
        _, remember = overlay.app.background.call_args.args
        remember(ChampionPicks('26.22', {'firebrand': 7}), None)
        self.assertEqual(overlay.champion_picks[('arena', 'Jinx')][1].rates['firebrand'], 13.5)
        self.assertEqual(overlay.champion_picks[('mayhem', 'Jinx')][1].rates['firebrand'], 7)
        self.assertNotIn(('arena', 'Shyvana'), overlay.champion_picks)

    def test_unknown_or_unaligned_selection_is_hidden(self):
        lines = [Line(name, x, 50, 22) for x, name in
                 [(325, 'Deft'), (675, 'Heavy Hitter'), (1025, 'Goliath')]]
        self.assertEqual(len(selection(lines, 'arena', 675, 1080)), 3)
        self.assertFalse(selection(lines[:2], 'arena', 675, 1080))
        self.assertFalse(selection(lines[:2] + [Line('Goliath', 1025, 190, 22)], 'arena', 675, 1080))
        self.assertIsNone(identify('mayhem', 'Неизвестная карточка'))
        self.assertFalse(selection(lines[:2] + [Line('Deft', 1025, 50, 22)], 'arena', 675, 1080))

    def test_focus_change_discards_previous_job(self):
        app = SimpleNamespace(last_game=SimpleNamespace(t=90), augment_status=None)
        overlay = object.__new__(AugmentOverlay)
        overlay.app, overlay.context = app, ('arena', 'Jinx', 19, (0,0,1920,1080))
        overlay.epoch = overlay.scan_epoch = 1
        overlay.last_time, overlay.next_scan = 89, 0
        overlay.hide, overlay.show = Mock(), Mock()
        overlay.active_context = lambda: None
        overlay.pending = Future()
        overlay.pending.set_result(('obsolete',))
        overlay.tick()
        overlay.show.assert_not_called()
        overlay.hide.assert_called_once()
        self.assertIsNone(overlay.pending)

    @unittest.skipUnless((DATA/'tessdata/rus.traineddata').exists(), 'Модели OCR подготавливаются при сборке')
    def test_real_ocr_reroll_scale_and_empty_frame(self):
        reader = Reader()
        font_file = Path(__file__).parent/'qt_ui/fonts/PT_Serif-Web-Bold.ttf'
        for height, labels, mode in [
            (720, ('Deft', 'Heavy Hitter', 'Goliath'), 'arena'),
            (1080, ('Проворство', 'Тяжеловес', 'Голиаф'), 'mayhem'),
            (1080, ('Разминка', 'Тяжеловес', 'Голиаф'), 'mayhem'),
            (1440, ('Deft', 'Vulnerability', 'Heavy Hitter', 'Goliath'), 'arena')]:
            width = round(height*16/9)
            frame = Image.new('RGB', (width,height), '#15242c')
            draw = ImageDraw.Draw(frame)
            font = ImageFont.truetype(str(font_file), round(height*.025))
            for i, name in enumerate(labels):
                x = width/2 + (i-(len(labels)-1)/2)*height*.31
                draw.text((x,height*.40), name, font=font, fill='#eedfc7', anchor='mt')
            result = reader.read(frame.crop(region((0,0,width,height))), mode, height)
            self.assertEqual([c['key'] for _,_,c in result], [identify(mode,n)['key'] for n in labels])
        self.assertFalse(reader.read(Image.new('RGB',(960,240),'gray'), 'mayhem', 1080))


if __name__ == '__main__':
    unittest.main()
