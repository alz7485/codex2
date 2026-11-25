"""Host boundary checks for Trial160: input edges, blank transit and clean return."""
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
import sys
from PIL import Image
from effect_engine import ClickEvent
from effect_settings import resolve
from shiranui_runtime import ShiranuiDisplay

ROOT=Path(__file__).parent
PATH=ROOT/'カーソル/ドラグーン/アカツキ（シラヌイ）.cur'

class Capture:
    def draw(self,states,size,origin=(0,0),field=None):
        self.states=states;self.origin=origin;self.field=field
        return Image.new('RGBA',(1,1),(255,255,255,255) if states or field is not None else (0,0,0,0))
    def close(self):pass

class ShiranuiHost(TestCase):
    def make(self):
        cfg=resolve('ドラグーン',{}, {'dragoon':{'enabled':True},'followers':{'enabled':True,'count':3,'size_percent':120}}, 'ドラグーン/アカツキ（シラヌイ）.cur')[0]
        original=sys.modules.get('shiranui_render')
        sys.modules['shiranui_render']=SimpleNamespace(Renderer=Capture)
        try:return ShiranuiDisplay(PATH,cfg)
        finally:
            if original is None:sys.modules.pop('shiranui_render',None)
            else:sys.modules['shiranui_render']=original

    def test_click_edges_idle_and_settings(self):
        d=self.make();box=(-1000,0,0,700);pos=(-400,200)
        d.step(pos,0,[],box)
        d.step(pos,.04,[ClickEvent('left',pos,.01),ClickEvent('left_up',pos,.02)],box)
        self.assertIsNotNone(d.renderer.states[0][1].shot)
        for i in range(3,180):d.step(pos,i*.02,[],box)
        self.assertEqual(len(d.renderer.states),4)
        self.assertGreater(abs(d.runtime.fleet.idle.angle),.1)
        self.assertLess(d.renderer.origin[0],0)
        d.config['followers'].update(count=0,size_percent=50,fire_enabled=False)
        d.step(pos,3.6,[],box)
        self.assertEqual(len(d.renderer.states),1)
        d.cancel_fire()
        for i in range(181,186):d.step(pos,i*.02,[ClickEvent('left',pos,i*.02)],box)
        self.assertFalse(d.renderer.states[0][1].charging)

    def test_special_blank_transit_clean_return_and_context_reset(self):
        d=self.make();box=(0,0,800,600);pos=(200,200)
        d.step(pos,0,[],box)
        empty=False;field=False;returned=False
        for i in range(1,360):
            t=i*.02;events=[]
            if i==10:events=[ClickEvent('left',pos,t,3)]
            if i==15:events=[ClickEvent('left_up',pos,t)]
            if i==150:events=[ClickEvent('left',pos,t)]
            im=d.step(pos,t,events,box)
            if d.runtime.effect.active and not d.renderer.states:
                empty=True;self.assertIsNone(im.getbbox())
            if d.renderer.field is not None:
                field=True;self.assertEqual(d.renderer.field.nodes.shape,(7,3))
            if i>330:
                returned=True
                self.assertIsNone(d.renderer.states[0][1].shot)
                self.assertFalse(d.renderer.states[0][1].charging)
        self.assertTrue(empty and field and returned)
        self.assertEqual(len(d.runtime.fleet.units),3)
        d.step(pos,7.2,[ClickEvent('left_up',pos,7.2)],box)
        d.step(pos,7.22,[ClickEvent('left',pos,7.22,3)],box)
        self.assertTrue(d.runtime.effect.active)
        d.step(pos,7.24,[],(-800,0,0,600),2)
        self.assertFalse(d.runtime.effect.active)
