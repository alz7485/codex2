import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from catalog_studio import pairing,project,presets,element_schema as schema,element_library
from catalog_studio.integrated import IntegratedStudio


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.data=project.sample();self.data['definitions']=[];self.data['scoms']=[]
        self.pt=self.add('p','/VALVE-PTSET','PTSET');self.gm=self.add('g','/VALVE-GMSET','GMSET')
    def add(self,ident,name,kind):
        d={'id':ident,'name':name,'kind':kind,'revision':'01','elements':[]};self.data['definitions'].append(d);return d
    def test_name_candidates_are_exact_and_do_not_mutate_old_projects(self):
        for pt,gm in (('/VALVE-PTSET','/VALVE-GMSET'),('/PTSET_VALVE','/GMSET_VALVE'),('/valve.points','/VALVE.GEOMETRY'),('/AREA/VALVE-PT','/AREA/VALVE-GM')):
            self.pt['name']=pt;self.gm['name']=gm;before=copy.deepcopy(self.data)
            self.assertIs(pairing.resolve(self.data,self.gm)['pointset'],self.pt);self.assertEqual(self.data,before)
        self.gm['name']='/VALVE-A-GMSET';self.assertIsNone(pairing.resolve(self.data,self.gm)['pointset'])
    def test_future_name_rules_and_manual_choices_roundtrip(self):
        self.data[pairing.RULES_KEY]=[{'ptset':'/LIB/points/{name}','gmset':'/LIB/geom/{name}'}]
        self.pt['name']='/LIB/points/VALVE';self.gm['name']='/LIB/geom/VALVE'
        self.assertIs(pairing.resolve(self.data,self.gm)['pointset'],self.pt)
        pairing.assign(self.data,self.gm,self.pt['id']);self.gm['name']='/RENAMED';self.pt['name']='/OTHER-NAME'
        self.assertIs(pairing.resolve(self.data,self.gm)['pointset'],self.pt);self.assertEqual(pairing.resolve(self.data,self.gm)['source'],'manual')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pairs.json';project.save(self.data,path);self.assertEqual(project.load(path),self.data)
        self.assertNotIn(pairing.PAIR_KEY,self.gm.get('attrs',{}))
    def test_ambiguous_and_unset_choices_never_pick_an_arbitrary_pointset(self):
        self.add('p2','/valve-ptset','PTSET');self.assertEqual(pairing.resolve(self.data,self.gm)['source'],'ambiguous')
        self.assertIsNone(pairing.resolve(self.data,self.gm)['pointset'])
        pairing.assign(self.data,self.gm,'p');self.assertIs(pairing.resolve(self.data,self.gm)['pointset'],self.pt)
        pairing.assign(self.data,self.gm,'');self.assertEqual(pairing.resolve(self.data,self.gm)['source'],'unset')
        pairing.assign(self.data,self.gm,None);self.assertEqual(pairing.resolve(self.data,self.gm)['source'],'ambiguous')
        self.gm[pairing.PAIR_KEY]='missing';self.assertEqual(pairing.resolve(self.data,self.gm)['source'],'missing')
        self.assertTrue(any('PTSET が見つかりません' in issue for issue in project.issues(self.data)))
    def test_known_scom_and_scoped_draft_are_respected(self):
        other=self.add('p2','/OTHER-PTSET','PTSET');s=copy.deepcopy(project.sample()['scoms'][0]);s.update(ptset_id=other['id'],gmset_id=self.gm['id']);self.data['scoms']=[s]
        self.assertIs(pairing.resolve(self.data,self.gm)['pointset'],other);self.assertEqual(pairing.resolve(self.data,self.gm)['source'],'scom')
        self.data['scoms']=[];self.data['creation_draft']={'gmset_id':'unrelated','ptset_id':other['id']}
        self.assertIs(pairing.resolve(self.data,self.gm)['pointset'],self.pt)
        self.data['creation_draft']['gmset_id']=self.gm['id'];self.assertIs(pairing.resolve(self.data,self.gm)['pointset'],other)
        pairing.assign(self.data,self.gm,self.pt['id']);self.assertIs(pairing.resolve(self.data,self.gm)['pointset'],self.pt)
    def test_invalid_metadata_and_assignments_are_rejected(self):
        before=copy.deepcopy(self.data)
        for ident in ('missing',self.gm['id'],0):
            with self.assertRaises(ValueError):pairing.assign(self.data,self.gm,ident)
            self.assertEqual(self.data,before)
        self.gm[pairing.PAIR_KEY]=3
        with self.assertRaises(ValueError):project.validate(self.data)
        self.gm.pop(pairing.PAIR_KEY)
        self.data[pairing.RULES_KEY]=[{'ptset':'{name}{name}','gmset':'{name}-GM'}]
        with self.assertRaises(ValueError):project.validate(self.data)
    def test_reorder_updates_paired_geometry_before_any_scom_exists(self):
        for number in (10,20):schema.add_element(self.pt,'PTAXI')['attrs']['NUMB']=str(number)
        line=schema.add_element(self.gm,'LINE');line['attrs']['PTS']='P10 T20 P0'
        self.assertEqual(self.data['scoms'],[]);element_library.reorder(self.data,self.pt,self.pt['elements'][0]['id'],1)
        self.assertEqual(line['attrs']['PTS'],'P2 T1 P0');self.assertEqual([e['attrs']['NUMB'] for e in self.pt['elements']],['1','2'])
    def test_scom_with_another_pointset_prevents_ambiguous_remapping(self):
        other=self.add('p2','/OTHER-PTSET','PTSET')
        for number in (10,20):schema.add_element(other,'PTAXI')['attrs']['NUMB']=str(number)
        line=schema.add_element(self.gm,'LINE');line['attrs']['PTS']='P10 T20'
        pairing.assign(self.data,self.gm,other['id']);s=copy.deepcopy(project.sample()['scoms'][0]);s.update(ptset_id=self.pt['id'],gmset_id=self.gm['id']);self.data['scoms']=[s];before=copy.deepcopy(self.data)
        with self.assertRaises(ValueError):element_library.reorder(self.data,other,other['elements'][0]['id'],1)
        self.assertEqual(self.data,before)


class PairingGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest('GUI display unavailable: '+str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.switch('gmset');self.app.update();self.editor=self.app.geometry_editor
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
        self.assertEqual(self.errors,[])
    def select(self,name):
        e=self.app.geometry_editor;e.ptset_choice.set(name);e.ptset_choice.event_generate('<<ComboboxSelected>>');self.app.update()
    def test_initial_name_candidate_is_selected_without_changing_records(self):
        e=self.editor;gm=e.definition();pt=pairing.resolve(e.data,gm)['pointset'];before=copy.deepcopy(e.data)
        self.assertEqual(pt['id'],'ui-ptset');self.assertEqual(e.ptset_choice.get(),pt['name']);self.assertIn('名前',e.pairing_note['text'])
        e.refresh();self.app.update();self.assertEqual(e.data,before);self.assertNotIn(pairing.PAIR_KEY,gm)
    def test_manual_pair_survives_rename_navigation_and_save_without_scom_changes(self):
        e=self.editor;gm=e.definition();pt=next(d for d in e.data['definitions'] if d['id']=='pt-reducer');original=copy.deepcopy(e.data['scoms'])
        self.select(pt['name']);self.assertEqual(gm[pairing.PAIR_KEY],pt['id']);e.def_name.set('/CHANGED-GEOMETRY');e.commit_name();self.app.update()
        self.assertEqual(e.ptset_choice.get(),pt['name']);self.app.switch('ptset');self.app.update();self.app.definition_id=gm['id'];self.app.switch('gmset');self.app.update()
        self.assertEqual(self.app.geometry_editor.ptset_choice.get(),pt['name'])
        with tempfile.TemporaryDirectory() as folder:
            self.app.path=str(Path(folder)/'paired.json');self.assertTrue(self.app.save_project());loaded=project.load(self.app.path)
            self.assertEqual(project.get(loaded,'definitions',gm['id'])[pairing.PAIR_KEY],pt['id'])
        self.assertEqual(e.data['scoms'],original)
    def test_unset_auto_and_missing_references_keep_selection_explicit(self):
        e=self.editor;gm=e.definition();automatic=e.ptset_choice.get();self.select('未設定');self.assertEqual(gm[pairing.PAIR_KEY],'');self.assertEqual(e.ptset_choice.get(),'未設定')
        self.select('対応から自動選択');self.assertNotIn(pairing.PAIR_KEY,gm);self.assertEqual(e.ptset_choice.get(),automatic)
        gm[pairing.PAIR_KEY]='missing';e.refresh();self.app.update();self.assertIn('missing',e.ptset_choice.get());self.assertIn('見つかりません',e.pairing_note['text'])
        self.assertTrue(all(d['kind']=='PTSET' for d in e.data['definitions'] if d['id'] in e.ptset_options.values()))
    def test_scom_registration_uses_the_selected_pair_not_an_unrelated_draft(self):
        e=self.editor;gm=e.definition();pt=next(d for d in e.data['definitions'] if d['id']=='pt-reducer');self.select(pt['name'])
        e.data['creation_draft']={'gmset_id':'another','ptset_id':'ui-ptset'};before=copy.deepcopy(e.data['scoms'])
        self.app.switch('catalog');self.app.update()
        with patch.object(self.app,'scom_form') as form:self.app.add_scom()
        self.assertEqual(form.call_args.kwargs['seed']['ptset_id'],pt['id']);self.assertEqual(form.call_args.kwargs['seed']['gmset_id'],gm['id'])
        with patch.object(self.app,'scom_form') as form:self.app.component_from_gmset(gm['id'])
        self.assertEqual(form.call_args.kwargs['seed']['ptset_id'],pt['id']);self.assertEqual(e.data['scoms'],before)
    def test_parameter_mismatch_is_visible_and_does_not_reassign_rules(self):
        e=self.editor;gm=e.definition();pt=next(d for d in e.data['definitions'] if d['id']=='ui-ptset');profile=presets.add(e.data,'ポイント側の規則');presets.bind(e.data,pt,profile['id']);self.select(pt['name'])
        self.assertIn('PARAM プリセットが異なります',e.pairing_note['text']);self.assertEqual(presets.selected_id(e.data,gm),'')
        with patch.object(self.app,'scom_form') as form,patch('catalog_studio.integrated.messagebox.showinfo') as info:self.app.add_scom()
        form.assert_not_called();self.assertTrue(info.called);self.assertEqual(presets.selected_id(e.data,pt),profile['id'])
