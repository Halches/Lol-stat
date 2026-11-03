import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('refresh_catalog_gameplay',Path(__file__).resolve().parents[1]/'tools/refresh_catalog_gameplay.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
RAW='''return {
  ["Ahri"] = {
    ["id"] = 103,
    ["resource"] = "Mana",
    ["rangetype"] = "Ranged",
    ["date"] = "2011-12-14",
    ["external_positions"] = {"Middle"},
  },
}'''


class CatalogRefresh(unittest.TestCase):
    def test_only_verified_fields_change_and_lore_date_survives(self):
        old={'source':{'snapshot_date':'2026-03-04'},'champions':{'Ahri':{'gender':'FEMALE','species':['Vesani']}}}
        result=module.refresh(old,{'103':'Ahri'},RAW,'2026-11-03')
        self.assertEqual(result['champions']['Ahri']['positions'],['MIDDLE'])
        self.assertEqual(result['champions']['Ahri']['gender'],'FEMALE')
        self.assertEqual(result['source']['snapshot_date'],'2026-03-04')
        self.assertEqual(old['champions']['Ahri'],{'gender':'FEMALE','species':['Vesani']})

    def test_incomplete_or_executable_value_is_rejected(self):
        for text in (RAW.replace('"Mana"','danger()'),RAW.replace('103','104')):
            with self.assertRaises(ValueError):module.refresh({'source':{},'champions':{}},{'103':'Ahri'},text,'2026-11-03')
