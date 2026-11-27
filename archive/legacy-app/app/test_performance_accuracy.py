import unittest
from types import SimpleNamespace
import performance_model as model
from settings_validation import clock_seconds


class PerformanceAccuracy(unittest.TestCase):
    def test_totals_are_not_divided_by_guessed_duration(self):
        self.assertEqual(model.benchmark({'cs':210,'g':14000,'k':4,'d':2,'a':8}),{'kda':6})

    def test_verified_rates_and_invalid_values(self):
        self.assertEqual(model.benchmark({'csm':7.1,'gpm':float('nan'),'kda':-1}),{'csm':7.1})
        self.assertEqual(model.benchmark({'csm':True,'gpm':float('inf')}),{})

    def test_live_gold_and_unknown_vision(self):
        me={'cs':70,'k':0,'d':0,'a':0,'ward':0,'igold':5000}
        values=model.live_values(SimpleNamespace(me=me,t=600,allies=[me],gold=1000))
        self.assertEqual(values['csm'],7)
        for key in ('gpm','vsm','kp'):self.assertIsNone(values[key])
        me.update(ward_known=True,ward=0,k=1)
        self.assertEqual(model.live_values(SimpleNamespace(me=me,t=600,allies=[me]))['vsm'],0)

    def test_no_borrowed_champion_norm(self):
        player=SimpleNamespace(on=lambda c,r:[],norm=lambda c,r:self.fail('fallback нормы'))
        self.assertEqual(model.personal(player,'Ahri','MIDDLE'),{})

    def test_manual_clock(self):
        self.assertEqual(clock_seconds(' 20:00 '),1200)
        self.assertEqual(clock_seconds('0:00'),0)
        for value in ('-1:00','2:99','2:60','2:5','nan','1:00:00'):
            with self.assertRaises(ValueError):clock_seconds(value)
        with self.assertRaises(ValueError):clock_seconds('0:00',positive=True)


if __name__=='__main__':unittest.main()
