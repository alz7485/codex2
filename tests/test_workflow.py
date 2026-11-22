import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import project, workflow, geometry_scene as geo, macro_export, diagnostics
from catalog_studio.piping_samples import add_samples

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.data=project.sample();add_samples(self.data)
        self.gm=next(d for d in self.data['definitions'] if d.get('sample')=='piping-bend' and d['kind']=='GMSET')
        self.pt=project.get(self.data,'definitions',self.gm['paired_ptset_id'])
    def test_shared_preview_changes_group_not_scom_or_other_presets(self):
        values=copy.deepcopy(self.data['scoms'])
        wrong=copy.deepcopy(self.gm);wrong.update(id='wrong',name='/WRONG',parameter_preset_id='')
        self.data['definitions'].append(wrong);before=copy.deepcopy(wrong)
        state={'scale':.01,'values':{'PARAM':{'P4':152}},'expressions':[]}
        workflow.apply_preview(self.data,self.pt,{'DDANGLE':45},state)
        for record in (self.pt,self.gm):
            self.assertEqual(record['model_settings'],{'DDANGLE':45})
            self.assertEqual(record['schematic_dimensions'],state)
        self.assertIsNot(self.pt['schematic_dimensions'],self.gm['schematic_dimensions'])
        self.assertEqual(self.data['scoms'],values);self.assertEqual(wrong,before)
    def test_point_roles_roundtrip_and_macro_metadata_exclusion(self):
        self.pt['elements'][0]['point_role']='分岐';self.gm['elements'][1]['preview_group']='保温'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'project.json';project.save(self.data,path);loaded=project.load(path)
        self.assertEqual(project.get(loaded,'definitions',self.pt['id'])['elements'][0]['point_role'],'分岐')
        text=macro_export.creation_text([self.pt,self.gm])
        self.assertNotIn('point_role',text);self.assertNotIn('preview_group',text)
        self.assertNotIn('分岐',text)
    def test_parameter_text_provenance_words_units_and_unknown_values(self):
        s=next(s for s in self.data['scoms'] if s.get('sample')=='piping-bend')
        rows=workflow.parameter_rows(self.data,s)
        self.assertEqual(rows[2]['value_type'],'word');self.assertEqual(rows[2]['value'],'TUB')
        self.assertEqual(rows[3]['unit'],'mm');self.assertEqual(rows[3]['text'],'RAD')
        text=next(t for t in self.data['texts'] if t.get('parameter_text_source',{}).get('parameters')=='P4')
        text['attrs']['STEXT']='NEW RADIUS';self.assertEqual(workflow.parameter_rows(self.data,s)[3]['text'],'NEW RADIUS')
        text.pop('parameter_text_source');text['name']='/PA4-BEND'
        self.assertEqual(workflow.parameter_rows(self.data,s)[3]['text'],'NEW RADIUS')
        self.data['texts'].append(dict(text,id='duplicate',name='/PARAM4'))
        self.assertEqual(workflow.parameter_rows(self.data,s)[3]['source'],'PARAM定義')
    def test_priority_and_filters_are_non_destructive(self):
        records=[dict(id='other',parameter_preset_id=''),dict(id='match',parameter_preset_id=self.pt['parameter_preset_id'])]
        self.assertEqual(workflow.preferred_presets(self.data,records,self.pt)[0]['id'],'match')
        self.assertEqual(records[0]['id'],'other')
        before=copy.deepcopy(self.data)
        self.gm['elements'][1]['preview_group']='保温'
        scene=geo.build_scene(self.data,self.gm)
        workflow.filter_scene(scene,self.gm,{'中心線'})
        self.assertEqual([m.kind for m in scene.meshes],['LINE'])
        self.assertIn(self.gm['elements'][1]['id'],scene.source_meshes)
        self.gm['elements'][1].pop('preview_group');self.assertEqual(self.data,before)
    def test_diagnostics_target_required_attribute_and_scom_value(self):
        node=self.pt['elements'][0];node['attrs']['PAXI']=''
        s=next(s for s in self.data['scoms'] if s.get('sample')=='piping-bend');s['values'].pop('P4')
        before=copy.deepcopy(self.data);rows=diagnostics.collect(self.data)
        self.assertTrue(any(r['record_id']==self.pt['id'] and r['element_id']==node['id'] and r['field']=='PAXI' for r in rows))
        self.assertTrue(any(r['record_id']==s['id'] and r['field']=='P4' for r in rows));self.assertEqual(self.data,before)

    def test_known_pipe_weld_without_gmset_are_not_unresolved_references(self):
        rows=diagnostics.collect(self.data)
        for scom in self.data['scoms']:
            if scom.get('sample') in ('piping-pipe','piping-weld'):
                self.assertFalse(any(r['record_id']==scom['id'] and r['field']=='gmset_id' for r in rows))
