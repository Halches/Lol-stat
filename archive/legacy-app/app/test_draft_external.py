import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import draft_external as model
import ui


class DraftExternal(unittest.TestCase):
    def test_same_champion_and_role_are_required(self):
        row={'champion':'Ahri','role':'MIDDLE','variant':{'perks':[8112]},'patch':'16.21'}
        self.assertEqual(model.selected('offmeta','Ahri','MIDDLE',row)['pick'],row['variant'])
        self.assertIsNone(model.selected('offmeta','Ahri','TOP',row))
        self.assertIsNone(model.selected('offmeta','Lux','MIDDLE',row))
        self.assertIsNone(model.selected('offmeta','Ahri','MIDDLE',dict(row,variant=None)))

    def test_player_selection_keeps_exact_record(self):
        row={'id':'42','champion':'Ahri','role':'MIDDLE','variant':{'core':[6655]},'patch':'16.21'}
        players={'champion':'Ahri','role':'MIDDLE','groups':{'OTP':[row]}}
        self.assertEqual(model.selected('player:42','Ahri','MIDDLE',players=players)['pick'],row['variant'])
        self.assertIsNone(model.selected('player:43','Ahri','MIDDLE',players=players))

    def test_app_export_uses_external_record_without_general_fallback(self):
        app=SimpleNamespace(draft={'me':'Ahri'},draft_role=lambda cs:('MIDDLE',''),s={'draft_build_context':'offmeta'},offmeta_build=lambda c,r:None,lola_build=Mock())
        self.assertIsNone(ui.App.selected_draft_build(app))
        app.lola_build.assert_not_called()


if __name__=='__main__':unittest.main()
