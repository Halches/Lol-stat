"""Настройки версии 1 сохраняются при переходе на Qt."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app_config import Settings,DEFAULTS

class QtSettingsTests(unittest.TestCase):
    def test_original_backup_and_unknown_keys_survive(self):
        with tempfile.TemporaryDirectory() as home:
            path=Path(home)/'settings.json'
            original=json.dumps({'design3':True,'theme':'lol','champion_pools':{'halch':{'TOP':['Sett']}},'widget_pins':{'perf':True},'future_setting':{'value':7}},ensure_ascii=False).encode()
            path.write_bytes(original);s=Settings(home)
            self.assertEqual(path.with_name('settings.json.pre-v2').read_bytes(),original)
            self.assertEqual(s['future_setting'],{'value':7});self.assertTrue(s['widget_pins']['perf'])
            s['theme']='lol_day';s.save();second=Settings(home)
            self.assertEqual(second['theme'],'lol_day');self.assertEqual(path.with_name('settings.json.pre-v2').read_bytes(),original)
    def test_defaults_are_not_shared_between_instances(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            first,second=Settings(a),Settings(b);first['perf']['metrics']['csm']=False
            self.assertTrue(second['perf']['metrics']['csm']);self.assertTrue(DEFAULTS['perf']['metrics']['csm'])
    def test_old_auto_import_migration(self):
        with tempfile.TemporaryDirectory() as home:
            (Path(home)/'settings.json').write_text('{"auto_import":true}')
            s=Settings(home);self.assertEqual(s['auto_parts'],{'runes':True,'items':True,'spells':False})
    def test_retired_settings_are_discarded_on_upgrade_and_restore(self):
        retired = {'phone': True, 'phone_port': 8888, 'phone_token': 'old-token'}
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / 'settings.json'
            path.write_text(json.dumps({**retired, 'scale': 120}))
            settings = Settings(home)
            self.assertTrue(retired.keys().isdisjoint(settings))
            self.assertEqual(settings['scale'], 120)
            settings.load_backup({'app': 'LoL Helper', 'settings': {**retired, 'scale': 130}})
            self.assertEqual(settings['scale'], 130)
            self.assertTrue(retired.keys().isdisjoint(settings.export()['settings']))
            self.assertTrue(retired.keys().isdisjoint(json.loads(path.read_text())))

    def test_invalid_backup_preserves_live_settings_and_disk(self):
        with tempfile.TemporaryDirectory() as home:
            s = Settings(home)
            s.save()
            path = Path(s.path)
            before = path.read_bytes()
            for broken in ({'scale':'large'}, {'scale':None}, {'scale':171},
                           {'perf':{'metrics':None}}, {'tab_rect':[0, 0, 0, 1]}):
                with self.subTest(broken=broken), self.assertRaises(ValueError):
                    s.load_backup({'app':'LoL Helper','settings':{'dashboard':False,**broken}})
                self.assertTrue(s['dashboard'])
                self.assertEqual(path.read_bytes(), before)
            with patch.object(s,'_write',side_effect=OSError),self.assertRaises(OSError):
                s.load_backup({'app':'LoL Helper','settings':{'dashboard':False}})
            self.assertTrue(s['dashboard'])
            self.assertEqual(path.read_bytes(), before)

    def test_startup_recovers_invalid_fields_and_keeps_valid_neighbors(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home)/'settings.json'
            path.write_text('{"scale":null,"perf":{"metrics":null,"layout":"horizontal"},"auto_import":false,"auto_parts":{"runes":true}}')
            s = Settings(home)
            self.assertEqual(s['scale'],100)
            self.assertEqual(s['perf'],{**DEFAULTS['perf'],'layout':'horizontal'})
            self.assertFalse(s['auto_import'])
            self.assertTrue(s['auto_parts']['runes'])
            s.load_backup({'app':'LoL Helper','settings':{'perf':{'metrics':{'kda':False}}}})
            self.assertEqual(s['perf']['layout'],'horizontal')
            self.assertFalse(s['perf']['metrics']['kda'])

if __name__=='__main__':unittest.main()
