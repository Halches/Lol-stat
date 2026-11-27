"""Comment semantics: negative is red, neutral is yellow, no prefixes or duplicate streaks."""
import unittest
import player_comments
import ui

class PlayerCommentsTests(unittest.TestCase):
    def history(self, **overrides):
        h = dict(n=10,w=6,streak=0,on=0,on_w=0,kda=2.8,tags=[],good=[],bad=[],tilt=[])
        h.update(overrides);return h

    def test_negative_metrics_are_red_and_neutral_champion_fact_is_yellow(self):
        rows=player_comments.comments(self.history(bad=['мало обзора (0.3/мин)','слабый фарм (4.1 CS/мин)'],tags=['не играл на нём недавно']))
        self.assertEqual({key:tone for key,_,tone in rows}, {'N2':'neutral','R8':'bad','R6':'bad'})
        _,tags=ui.hist_tags(self.history(bad=['мало обзора (0.3/мин)']))
        self.assertEqual(tags,[('Мало обзора (0.3/мин)','r')])

    def test_streak_is_not_repeated_and_no_strength_or_mood_prefix_is_inserted(self):
        h=self.history(streak=-4,tilt=['4 поражения подряд','смертей всё больше: 8 за игру против 4 раньше'])
        rows=player_comments.comments(h)
        self.assertEqual([key for key,_,_ in rows],['R1','R3'])
        self.assertTrue(all(tone=='bad' for _,_,tone in rows))
        self.assertFalse(any(prefix in text for _,text,_ in rows for prefix in ('Силен:','Силён:','Слаб:','Тильт:')))

    def test_missing_history_is_neutral_and_does_not_invent_a_trait(self):
        self.assertEqual(player_comments.comments(None),[('N3','История игрока недоступна','neutral')])

    def test_preview_keeps_all_available_colours_and_catalog_ids_are_unique(self):
        h=self.history(streak=4,good=['в форме, 4 победы подряд','редко умирает (3.1 за игру)','KDA 4.5'],bad=['мало урона (300/мин)'],tags=['играет почти только на нём'])
        rows=player_comments.preview(h)
        self.assertEqual({tone for _,_,tone in rows},{'good','neutral','bad'})
        self.assertEqual(len(rows),4)
        self.assertEqual(len({key for key,_,_ in player_comments.CATALOG}),24)
        self.assertTrue(all(key in {k for k,_,_ in player_comments.CATALOG} for key,_,_ in player_comments.comments(h)))

    def test_full_and_preview_comments_form_contiguous_colour_groups(self):
        h=self.history(streak=-4,good=['редко умирает (3.1 за игру)','KDA 4.5'],
                       bad=['мало урона (300/мин)'],tags=['не играл на нём недавно'],
                       tilt=['4 поражения подряд'])
        order={'good':0,'neutral':1,'bad':2}
        for rows in (player_comments.comments(h), player_comments.preview(h)):
            colours=[order[tone] for _,_,tone in rows]
            self.assertEqual(colours, sorted(colours))
            self.assertEqual({tone for _,_,tone in rows},{'good','neutral','bad'})
        self.assertEqual(len(player_comments.preview(h)),4)

if __name__=='__main__':unittest.main()
