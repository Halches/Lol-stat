"""Настройки версии 1 сохраняются при переходе на Qt."""
import json,tempfile,unittest
from pathlib import Path
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
    def test_phone_token_is_not_exported(self):
        with tempfile.TemporaryDirectory() as home:
            s=Settings(home);s['phone_token']='private';self.assertNotIn('phone_token',s.export('v2.0.0')['settings'])

if __name__=='__main__':unittest.main()
