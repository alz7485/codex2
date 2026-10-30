import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from catalog_studio import project,presets,element_schema as schema
from catalog_studio.integrated import IntegratedStudio,PAGES


class CreationFlowTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update()
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def empty(self):
        for key in ('cates','definitions','scoms','specs','books'):self.app.data[key]=[]
        self.app.reset_selection();self.app.switch('ptset');self.app.update()
    def confirm(self,title,fields,apply):
        values={key:str(initial) for key,label,initial,options in fields}
        if title.startswith('新しい PTSET'):values['name']='/FLOW-PT'
        elif title.startswith('新しい GMSET'):values['name']='/FLOW-GM'
        elif title=='SCOM の値を登録':
            values.update(name='/FLOW-SCOM',size='テスト部品')
            for p in range(1,6):
                if 'P'+str(p) in values:values['P'+str(p)]=str(p*10)
            if 'P6' in values:values['P6']='BW'
            if 'new_cate_name' in values:values['new_cate_name']='/FLOW-CATE'
        elif title=='SPEC 情報':values['name']='/FLOW-SPEC'
        elif title=='SPEC の登録行':values.update(type='TEST',bore1='40',bore2='50')
        apply(values);self.app.mark();self.app.render_page()
    def make_sets(self):
        with patch.object(self.app,'form',side_effect=self.confirm):self.app.geometry_editor.add_definition()
        self.app.update();pt=self.app.geometry_editor.definition();schema.add_element(pt,'PTAXI');self.app.geometry_editor.refresh()
        with patch.object(self.app,'form',side_effect=self.confirm):self.app.geometry_editor.create_part()
        self.app.update();gm=self.app.geometry_editor.definition();schema.add_element(gm,'SCYL')['attrs'].update(PAXI='X',PDIA='PARAM 1',PHEI='PARAM 3',PDIS='0')
        self.app.geometry_editor.refresh();return pt,gm
    def test_order_and_empty_project_all_four_stages(self):
        self.assertEqual([key for key,label in PAGES[:5]],['ptset','gmset','catalog','sdte_cmpt','specs'])
        self.empty();self.assertIsNone(self.app.geometry_editor.definition())
        pt,gm=self.make_sets();self.assertEqual(self.app.page,'gmset');self.assertEqual(self.app.data['scoms'],[])
        self.assertEqual(self.app.data['creation_draft'],{'ptset_id':pt['id'],'gmset_id':gm['id']})
        with patch.object(self.app,'form',side_effect=self.confirm):self.app.geometry_editor.create_part()
        self.app.update();self.assertEqual(self.app.page,'catalog')
        scom=project.get(self.app.data,'scoms',self.app.scom_id)
        self.assertEqual((scom['ptset_id'],scom['gmset_id']),(pt['id'],gm['id']))
        self.assertEqual(self.app.data['cates'][0]['name'],'/FLOW-CATE');self.assertEqual(self.app.data['specs'],[])
        with patch.object(self.app,'form',side_effect=self.confirm):self.app.component_to_spec();self.app.update()
        self.assertEqual(self.app.page,'specs');entry=self.app.spec()['entries'][0]
        self.assertEqual(entry['scom_id'],scom['id']);self.assertEqual(entry['type'],'TEST')
        self.assertEqual(self.app.data['creation_draft']['spec_id'],self.app.spec()['id'])
        project.validate(self.app.data);self.assertEqual(self.errors,[])
    def test_ptset_preset_is_carried_even_when_default_changes(self):
        self.empty();profile=presets.add(self.app.data,'部品用');profile['parameters'].append({'id':'P6','role':'接続形式','unit':'','value_type':'word'})
        self.app.data['active_parameter_preset_id']=profile['id']
        with patch.object(self.app,'form',side_effect=self.confirm):self.app.geometry_editor.add_definition()
        self.app.update();pt=self.app.geometry_editor.definition();schema.add_element(pt,'PTAXI')
        self.app.data['active_parameter_preset_id']=''
        with patch.object(self.app,'form',side_effect=self.confirm):self.app.geometry_editor.create_part()
        self.app.update();gm=self.app.geometry_editor.definition();self.assertEqual(presets.selected_id(self.app.data,gm),profile['id'])
        with patch.object(self.app,'form',side_effect=self.confirm):self.app.geometry_editor.create_part()
        scom=project.get(self.app.data,'scoms',self.app.scom_id)
        self.assertEqual(presets.selected_id(self.app.data,scom),profile['id']);self.assertEqual(scom['values']['P6'],'BW')
        self.assertEqual(scom['ptset_id'],pt['id']);self.assertEqual(self.app.data['active_parameter_preset_id'],'')
        project.validate(self.app.data);self.assertEqual(self.errors,[])
    def test_cancel_has_no_hidden_records_and_bad_values_do_not_create_cate(self):
        self.empty();pt,gm=self.make_sets();before=copy.deepcopy(self.app.data)
        with patch.object(self.app,'form',return_value=None):self.app.geometry_editor.create_part()
        self.assertEqual(self.app.data,before)
        def bad(title,fields,apply):
            values={key:str(initial) for key,label,initial,options in fields};values.update(name='/INVALID',P1='invalid')
            apply(values)
        with patch.object(self.app,'form',side_effect=bad),self.assertRaises(ValueError):self.app.component_from_gmset(gm['id'])
        self.assertEqual(self.app.data,before)
        with patch.object(self.app,'form',return_value=None):self.app.component_from_ptset(pt['id'])
        self.assertEqual(self.app.data,before);self.assertEqual(self.errors,[])
    def test_saved_draft_resumes_the_selected_sets(self):
        self.empty();pt,gm=self.make_sets()
        extra={'id':'other-gm','name':'/OTHER','kind':'GMSET','revision':'01','elements':[]}
        self.app.data['definitions'].insert(0,extra)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'data.json';project.save(self.app.data,path);self.app.data=project.load(path)
        self.app.reset_selection();self.app.definition_id=pt['id'];self.app.switch('gmset');self.app.update()
        self.assertEqual(self.app.geometry_editor.definition_id,gm['id']);self.assertEqual(self.errors,[])
    def test_mismatching_presets_stop_scom_creation(self):
        self.empty();pt,gm=self.make_sets();profile=presets.add(self.app.data,'別の規則');presets.bind(self.app.data,gm,profile['id'])
        before=copy.deepcopy(self.app.data)
        with patch('catalog_studio.integrated.messagebox.showinfo') as notice,patch.object(self.app,'form') as form:
            self.app.component_from_gmset(gm['id']);notice.assert_called_once();form.assert_not_called()
        self.assertEqual(self.app.data,before)
    def test_standalone_gmset_asks_for_ptset_and_spec_uses_selected_scom(self):
        app=self.app;app.switch('gmset');gm=app.geometry_editor.definition();app.data.pop('creation_draft',None);gm['paired_ptset_id']=''
        pt=next(d for d in app.data['definitions'] if d['kind']=='PTSET')
        def choose(title,fields,apply):
            values={key:str(initial) for key,label,initial,options in fields}
            if 'pt' in values:values['pt']=pt['name']
            apply(values);app.mark();app.render_page()
        with patch.object(app,'form',side_effect=choose):
            app.component_from_gmset(gm['id'])
            # Cancel the deferred SCOM form; the actual choice is persisted.
            with patch.object(app,'scom_form') as scom_form:app.update();self.assertEqual(scom_form.call_args.kwargs['seed']['ptset_id'],pt['id'])
        target=app.data['scoms'][1];app.scom_id=target['id']
        with patch.object(app,'form') as form:app.component_to_spec()
        fields=form.call_args.args[1];self.assertEqual(next(initial for key,label,initial,options in fields if key=='scom'),target['name'])
        self.assertEqual(self.errors,[])
