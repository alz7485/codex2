import copy
import tempfile
import unittest
from pathlib import Path
from catalog_studio import parameter_catalog as catalog, project, presets, expressions, catalogue, booklet, element_library, element_schema as schema


class ParameterCatalogTests(unittest.TestCase):
    def setUp(self):
        self.data=project.sample();self.profile=presets.add(self.data,'配管の規則')
        for p,english in zip(self.profile['parameters'],('Connection Bore','Outside Diameter','Face-to-Face Length','Large Bore','Small Bore')):p['english_name']=english
        self.cate=self.data['cates'][0]
    def working(self):return copy.deepcopy(self.profile)
    def preview(self,working=None,**kwargs):return catalog.text_preview(self.data,working or self.profile,self.cate['id'],**kwargs)

    def test_meaning_and_english_edits_preserve_formula_aliases_and_scom_values(self):
        for d in self.data['definitions']:presets.bind(self.data,d,self.profile['id'])
        before=copy.deepcopy(self.data['definitions']);values=copy.deepcopy(self.data['scoms'])
        working=self.working();working['parameters'][0].update(meaning='接続口径（呼び径）',english_name='Nominal Connection Bore')
        catalog.save_preset(self.data,self.profile['id'],working)
        self.assertEqual(self.data['definitions'],before);self.assertEqual(self.data['scoms'],values)
        self.assertEqual(self.profile['parameters'][0]['role'],'大径側外径')
        self.assertEqual(presets.expression_names(self.data,{'parameter_preset_id':self.profile['id']},'PARAM 1'),'接続口径（呼び径）')
        self.assertEqual(expressions.evaluate('大径側外径 / 2',{'PARAM':{'P1':40}},parameters=self.profile['parameters']),20)

    def test_new_presets_are_empty_and_duplicates_keep_names_metadata_and_independence(self):
        empty=presets.add(self.data,'新規',empty=True);self.assertEqual(empty['parameters'],[])
        self.profile.update(period='2026',component='バルブ',description='規則の説明')
        duplicate=presets.add(self.data,'複製',self.profile['id'])
        self.assertEqual(duplicate['component'],'バルブ')
        duplicate['parameters'][0]['english_name']='Changed'
        self.assertEqual(self.profile['parameters'][0]['english_name'],'Connection Bore')

    def test_used_number_removal_and_value_type_changes_reject_atomically(self):
        presets.bind(self.data,self.data['scoms'][0],self.profile['id'])
        before=copy.deepcopy(self.data)
        for operation in ('remove','type','alias'):
            working=self.working()
            if operation=='remove':working['parameters'].pop(0)
            elif operation=='type':working['parameters'][0]['value_type']='word'
            else:working['parameters'][0]['role']='NEW_ALIAS'
            with self.assertRaises(ValueError):catalog.save_preset(self.data,self.profile['id'],working)
            self.assertEqual(self.data,before)

    def test_preview_uses_numeric_order_and_exact_english_names_without_mutation(self):
        self.profile['parameters']=[self.profile['parameters'][2],self.profile['parameters'][0],self.profile['parameters'][1]]
        before=copy.deepcopy(self.data);rows=self.preview()
        self.assertEqual([r['pid'] for r in rows],['P1','P2','P3'])
        self.assertEqual(rows[0]['name'],self.cate['name']+'/PARAM1')
        self.assertEqual(rows[0]['STEXT'],'Connection Bore');self.assertEqual(self.data,before)
        self.assertTrue(all(r['action']=='新規' for r in rows))

    def test_missing_english_or_wrong_parent_name_collision_never_partially_writes(self):
        working=self.working();working['parameters'][1]['english_name']=''
        before=copy.deepcopy(self.data)
        with self.assertRaisesRegex(ValueError,'P2'):catalog.write_texts(self.data,working,self.cate['id'])
        self.assertEqual(self.data,before)
        other=copy.deepcopy(self.cate);other.update(id='other-cate',name='/OTHER');self.data['cates'].append(other)
        catalogue.add_record(self.data,'texts','TEXT',self.cate['name']+'/PARAM3',other['id']);before=copy.deepcopy(self.data)
        with self.assertRaisesRegex(ValueError,'別 CATE'):catalog.write_texts(self.data,self.profile,self.cate['id'])
        self.assertEqual(self.data,before)

    def test_generate_and_update_keep_ids_other_attributes_and_history(self):
        generated=catalog.write_texts(self.data,self.profile,self.cate['id']);first=generated[0];ident=first['id']
        first['attrs']['USER_NOTE']='keep';self.profile['parameters'][0]['english_name']='Connection Bore Revised'
        rows=self.preview();self.assertEqual(rows[0]['old'],'Connection Bore');self.assertEqual(rows[0]['action'],'更新')
        self.assertEqual(first['attrs']['STEXT'],'Connection Bore')
        result=catalog.write_texts(self.data,self.profile,self.cate['id'],expected=rows)
        self.assertEqual(result[0]['id'],ident);self.assertEqual(first['attrs']['USER_NOTE'],'keep')
        self.assertEqual(first['attrs']['STEXT'],'Connection Bore Revised');self.assertEqual(first['stext_history'],['Connection Bore'])
        self.assertEqual(len(self.data['texts']),5)

    def test_stale_preview_detects_manual_changes_before_update(self):
        first=catalog.write_texts(self.data,self.profile,self.cate['id'])[0];rows=self.preview()
        first['attrs']['STEXT']='Manual edit';before=copy.deepcopy(self.data)
        with self.assertRaisesRegex(ValueError,'プレビュー'):catalog.write_texts(self.data,self.profile,self.cate['id'],expected=rows)
        self.assertEqual(self.data,before)

    def test_combined_text_has_explicit_separator_and_preserves_meaning_mapping(self):
        self.profile['parameters']=self.profile['parameters'][:3]
        rows=self.preview(combined=True,name='/PARAMETER-TEXT',separator=', ')
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['STEXT'],'Connection Bore, Outside Diameter, Face-to-Face Length')
        result=catalog.write_texts(self.data,self.profile,self.cate['id'],combined=True,name='/PARAMETER-TEXT',separator=', ')
        self.assertEqual(result[0]['parameter_text_source']['parameters'],'P1, P2, P3')
        self.assertEqual(result[0]['type'],'TEXT');self.assertNotIn('STEX',result[0]['attrs'])

    def test_bad_naming_patterns_and_conflicting_text_types_are_explicit(self):
        for pattern in ('{cate}/{unknown}','{cate.__class__}/{number}','{cate}/{number:1000000}','{cate}/PARAM','{cate'):
            with self.subTest(pattern=pattern),self.assertRaises(ValueError):self.preview(pattern=pattern)
        catalogue.add_record(self.data,'texts','SDTE',self.cate['name']+'/PARAM1',self.cate['id'])
        with self.assertRaisesRegex(ValueError,'別の種類'):self.preview()

    def test_new_fields_and_cate_text_are_frozen_in_books_and_survive_roundtrip(self):
        for record in self.data['definitions']+self.data['scoms']:presets.bind(self.data,record,self.profile['id'])
        self.profile['parameters'][0]['meaning']='接続口径';generated=catalog.write_texts(self.data,self.profile,self.cate['id'])
        book=booklet.snapshot(self.data);frozen=copy.deepcopy(book);self.assertEqual(len(book['texts']),5)
        self.profile['parameters'][0]['english_name']='Later';generated[0]['attrs']['STEXT']='Later'
        self.assertEqual(book,frozen);self.data['books'].append(book)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.json';project.save(self.data,path);self.assertEqual(project.load(path),self.data)
            try:from pypdf import PdfReader
            except ImportError:return
            pdf=Path(folder)/'catalog.pdf';booklet.generate_pdf(book,pdf)
            content='\n'.join(p.extract_text() for p in PdfReader(pdf).pages)
            self.assertIn('Connection Bore',content);self.assertNotIn('Later',content)

    def test_invalid_meaning_or_english_metadata_is_rejected_before_changes(self):
        before=copy.deepcopy(self.data)
        for key,value in (('meaning',3),('english_name',False),('english_name','a'*2001)):
            working=self.working();working['parameters'][0][key]=value
            with self.assertRaises(ValueError):catalog.save_preset(self.data,self.profile['id'],working)
            self.assertEqual(self.data,before)

    def test_reference_guard_covers_saved_element_groups_and_axis_parameter_angles(self):
        pt={'id':'pt','name':'/TEST','kind':'PTSET','elements':[],'parameter_preset_id':self.profile['id']}
        node=schema.add_element(pt,'PTAXI');node['attrs'].update(PAXI='X(PARAM 1)Y',PDIS='IPARAM 2',PBOR='0',PCON="'BW'")
        self.data['definitions'].append(pt);saved=element_library.register(self.data,pt,'点の規則');self.data['definitions'].remove(pt)
        self.assertTrue(catalog.in_use(self.data,self.profile['id'],'P1'))
        self.assertFalse(catalog.in_use(self.data,self.profile['id'],'P2'))
        saved['elements'][0]['attrs']['PAXI']='P1';self.assertFalse(catalog.in_use(self.data,self.profile['id'],'P1'))
