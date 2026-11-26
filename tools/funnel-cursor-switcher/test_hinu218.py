from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import json,sys
from PIL import Image
from effect_engine import ClickEvent
from effect_settings import Settings,resolve
from hinu_runtime import HiNuDisplay,rebase_projected

ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'hinu122'))
from hinu218 import host_render
from hinu218.special_trial215 import sample,HI_END,HWS_END
from hinu218.pulse_trial190 import RootTrack

class Capture:
    def __init__(self,kind):self.kind=kind;self.shot_layers=[];self.screen_origin=(0,0)
    def normal(self,c,t,xy,size,bounds,fixed,context):
        self.last=c.update(t,xy,context=context,fixed=fixed)
        self.members=c.update_fleet(t,xy,.65,bounds,context=context)
        return Image.new('RGBA',(1,1),'white')
    def special(self,t,size):
        self.ids=tuple(u.id for u in sample(t,self.kind,size[0]/size[1]) if u.visible)
        return Image.new('RGBA',(1,1),'white') if self.ids else Image.new('RGBA',(1,1))
    def close(self):pass

class HiNu218Host(TestCase):
    def make(self,name):
        path=ROOT/'カーソル/ファンネル'/(name+'.cur')
        cfg=resolve('ファンネル',{}, {'volley':{'enabled':True},'followers':{'enabled':True,'count':3,'size_percent':120}},'ファンネル/'+path.name)[0]
        with patch.object(host_render,'Renderer',Capture):return HiNuDisplay(path,cfg)

    def test_each_special_finishes_and_handles_hws_pass_ids(self):
        for name,end in (('Hi-νガンダム',HI_END),('Hi-νガンダムHWS',HWS_END)):
            d=self.make(name);pos=(-300,200);bounds=(-1000,0,0,700)
            d.step(pos,0,[],bounds)
            ids=set();empty=False
            for i in range(1,180):
                t=i*.05;ev=[ClickEvent('left',pos,t,3)] if i==2 else []
                picture=d.step(pos,t,ev,bounds)
                if d.volley.active:
                    ids.update(d.renderer.ids)
                    empty |= not bool(d.renderer.ids)
                elif t>end+.2:
                    self.assertFalse(d.renderer.last.fire.stage!='idle')
                    self.assertEqual(len(d.renderer.members),3)
                    self.assertTrue(d.wait_release)
                    break
            self.assertTrue(empty)
            self.assertEqual(ids,set(range(8 if 'HWS' in name else 6)))
            d.step(pos,t+.05,[ClickEvent('left_up',pos,t+.05)],bounds)
            self.assertFalse(d.wait_release)
            self.assertAlmostEqual(d.volley.aspect,10/7,places=2)
            d.close()

    def test_root_cache_rebases_without_changing_depth(self):
        d=self.make('Hi-νガンダム');c=d.control
        c.root_tracks[0].items={'shot':(.2,(10,20),.3,(30,40),.4)}
        rebase_projected(c,(7,-5))
        self.assertEqual(c.root_tracks[0].items['shot'],(.2,(17,15),.3,(37,35),.4))
        d.close()

    def test_baked_idle_sheet_matches_native_cursor_registration(self):
        for name in ('Hi-νガンダム','Hi-νガンダムHWS'):
            with Image.open(ROOT/'カーソル/ファンネル'/(name+'.png')) as im:native=im.convert('RGBA')
            with Image.open(ROOT/'飛行アニメ/ファンネル'/(name+'.待機回転.png')) as im:pose=im.crop((0,0,144,144)).resize((48,48),Image.Resampling.LANCZOS)
            rest=Image.new('RGBA',(48,48));rest.paste(native,(8,8))
            def core(im):return im.getchannel('A').point(lambda x:255 if x>=144 else 0).getbbox()
            self.assertLessEqual(max(abs(a-b) for a,b in zip(core(rest),core(pose))),1)

    def test_settings_preserve_unknown_fields_and_reset_known_overrides(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'effects.json';key='ファンネル/Hi-νガンダム.cur'
            data={'schema_version':1,'future_top':{'x':7},'presets':{},'cursors':{key:{'preset':'標準','future_binding':9,
                  'overrides':{'followers':{'count':3,'future_field':123},'future_group':{'value':True}}}}}
            p.write_text(json.dumps(data));s=Settings(p);s.cursors[key]['overrides']={};s.write()
            new=json.loads(p.read_text())
            self.assertEqual(new['future_top'],{'x':7})
            self.assertEqual(new['cursors'][key]['future_binding'],9)
            self.assertEqual(new['cursors'][key]['overrides'],{'followers':{'future_field':123},'future_group':{'value':True}})
