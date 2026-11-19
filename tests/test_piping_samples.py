import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import project, presets, catalog_macro
from catalog_studio.piping_samples import add_samples
from catalog_studio.piping_presets import PARAMETERS

class PipingSamplesTests(unittest.TestCase):
    def test_samples_text_labels_references_and_roundtrip(self):
        data=project.sample();self.assertEqual(add_samples(data),3)
        for component,items in PARAMETERS.items():
            marker='piping-'+component.lower()
            cate=next(c for c in data['cates'] if c.get('sample')==marker)
            scom=next(s for s in data['scoms'] if s.get('sample')==marker)
            pt=project.get(data,'definitions',scom['ptset_id'])
            self.assertEqual(pt['name'],'/PT-SAMPLE-'+component)
            gm=project.get(data,'definitions',scom['gmset_id'])
            if component=='BEND':self.assertEqual(gm['paired_ptset_id'],pt['id'])
            else:self.assertIsNone(gm)
            texts=[t for t in data['texts'] if t['parent_id']==cate['id'] and t['type']=='TEXT']
            profile=presets.get(data,scom['parameter_preset_id'])
            self.assertEqual([t['attrs']['STEXT'] for t in texts],[i[1] for i in items])
            self.assertEqual([p['english_name'] for p in profile['parameters']],[t['attrs']['STEXT'] for t in texts])
            self.assertEqual([t['parameter_text_source']['parameters'] for t in texts],['P'+str(i) for i in range(1,len(items)+1)])
            self.assertIn('NEW CATE',catalog_macro.creation_text(data,cate['id']))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data.json';project.save(data,path);self.assertEqual(project.load(path),data)

    def test_idempotence_collision_and_user_edits(self):
        data=project.sample();data['definitions'].append(dict(id='collision',name='/PT-SAMPLE-PIPE',kind='PTSET',revision='01',elements=[]))
        add_samples(data)
        pt=next(d for d in data['definitions'] if d.get('sample')=='piping-pipe')
        self.assertEqual(pt['name'],'/PT-SAMPLE-PIPE-2');pt['name']='/MY-EDIT'
        before=copy.deepcopy(data);self.assertEqual(add_samples(data),0);self.assertEqual(data,before)
