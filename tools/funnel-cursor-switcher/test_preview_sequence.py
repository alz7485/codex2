from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from effect_settings import resolve
from preview_sequence import Sequence

class PreviewSequences(TestCase):
    def config(self):return resolve('ファンネル',{}, {}, 'ファンネル/フィンファンネル.cur')[0]

    def test_center_start_and_single_press_release(self):
        cfg=self.config();original=deepcopy(cfg)
        for kind in ('fire','charge','special'):
            q=Sequence(kind,cfg,'barrier')
            self.assertEqual(q.sample((100,80),(200,160)),((100,80),[]))
            events=[]
            for i in range(1,120):
                q.advance(.04);_,e=q.sample((100,80),(200,160));events.extend(e)
            self.assertEqual([e.kind for e in events],['left','left_up'])
            self.assertEqual(len([e for e in events if e.modifiers==3]),1 if kind=='special' else 0)
        self.assertEqual(cfg,original)

    def test_movement_returns_to_center_and_clock_is_bounded(self):
        q=Sequence('move',self.config(),'barrier');q.advance(10)
        self.assertEqual(q.time,.05)
        q.time=1.;self.assertNotEqual(q.sample((100,80),(200,160))[0],(100,80))
        q.time=2.5;x,y=q.sample((100,80),(200,160))[0]
        self.assertAlmostEqual(x,100);self.assertAlmostEqual(y,80)
        self.assertTrue(q.finished(None))

    def test_special_waits_for_actual_end_including_blank_transit(self):
        q=Sequence('special',self.config(),'barrier')
        engine=SimpleNamespace(volley=SimpleNamespace(active=False))
        q.time=.1;self.assertFalse(q.finished(engine))
        engine.volley.active=True;self.assertFalse(q.finished(engine))
        q.time=10.;self.assertFalse(q.finished(engine))
        engine.volley.active=False;self.assertTrue(q.finished(engine))
