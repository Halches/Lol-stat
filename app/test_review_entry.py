"""Упакованный проверочный запуск: отдельный профиль, без рекурсивного EXE."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('review_entry',Path(__file__).parent/'dev/windows_review.py')
entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)


class Root:
    def __init__(self):self.callbacks=[];self.closed=False
    def title(self,text):pass
    def protocol(self,key,callback):self.close=callback
    def after(self,ms,callback):self.callbacks.append(callback)
    def update_idletasks(self):pass
    def destroy(self):self.closed=True


class ReviewEntry(unittest.TestCase):
    def run_entry(self,smoke):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);(home/'settings.json').write_text('working profile')
            (home/'fonts').mkdir();(home/'champion_catalog.json').write_text('{}')
            instances=[]
            class App:
                def __init__(self,*args):
                    self.root=Root();self.ov={'test':SimpleNamespace(demo=Mock())}
                    self.icons=SimpleNamespace(a={'champ':dict.fromkeys(range(173))});instances.append(self)
                def report_text(self):return 'diagnostic report'
                def run(self):
                    for callback in self.root.callbacks or [self.root.close]:callback()
            ui=SimpleNamespace(app_home=lambda:str(home),App=App,Voice=SimpleNamespace(warm=Mock()))
            helper=SimpleNamespace(home=lambda:str(home),load_data=lambda:{},HERE=str(home))
            argv=['review.exe']+(['--smoke-test'] if smoke else [])
            with patch.dict('sys.modules',{'ui':ui,'lolhelper':helper}),patch.object(entry,'os',SimpleNamespace(name='nt')),patch.object(entry.sys,'frozen',True,create=True),patch.object(entry.sys,'argv',argv),patch.object(entry.platform,'platform',return_value='Windows test adapter'),patch.object(entry.subprocess,'run') as run:
                entry.main();run.assert_not_called()
            self.assertEqual((home/'settings.json').read_text(),'working profile')
            review=home/'development-review'
            self.assertEqual(helper.home(),str(review))
            text=(review/'review-report.txt').read_text()
            self.assertIn('SMOKE OK' if smoke else 'diagnostic report',text)
            self.assertTrue(instances[0].root.closed)

    def test_frozen_smoke_does_not_spawn_itself(self):self.run_entry(True)
    def test_frozen_interactive_uses_separate_profile(self):self.run_entry(False)
