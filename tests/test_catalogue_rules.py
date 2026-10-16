import copy
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from catalog_studio import expressions as expr, element_schema as schema, catalogue, project, booklet
from catalog_studio.integrated import IntegratedStudio


class ExpressionTests(unittest.TestCase):
    def test_aliases_prefix_and_infix_are_equivalent(self):
        contexts={'PARAM':{'P2':12},'IPARAM':{'P1':3},'DES PARAM':{'P2':5},'APARAM':{'P3':8}}
        for text in ('PARAM 2','para[2]','(ATTRIB PARA[2])','P2'):
            self.assertEqual(expr.evaluate(text,contexts),12)
        self.assertEqual(expr.evaluate('SUM PARAM 2 IPARAM 1',contexts),15)
        self.assertEqual(expr.evaluate('0.5 TIMES PARAM 2',contexts),6)
        self.assertEqual(expr.evaluate('0.5 ＊ APARA[3]',contexts),4)
        self.assertEqual(expr.evaluate('ATTRIB DESP[2]',contexts),5)
        self.assertEqual(expr.evaluate('DES PARAM[2]',contexts),5)
        normalized=expr.normalized('SUM PARAM 2 IPARAM 1')
        self.assertEqual(expr.evaluate(normalized,contexts),15)
    def test_degrees_component_attribute_and_roles(self):
        params=[{'id':'P2','role':'長さ'}]
        self.assertAlmostEqual(expr.evaluate('長さ * TAN(ANGL / 2)',{'PARAM':{'P2':20}}, {'ANGL':90},params),20)
        with self.assertRaisesRegex(ValueError,'ANGL'):expr.evaluate('TAN(ANGL)',{'PARAM':{'P2':30}})
        with self.assertRaises(ValueError):expr.evaluate('TAN(90)')
    def test_words_distinct_namespaces_and_no_fallback(self):
        contexts={'PARAM':{'P1':'BW'},'OPARAM':{'P1':17},'DES OPARAM':{'P1':19}}
        self.assertEqual(expr.evaluate('PARAM 1',contexts),'BW')
        self.assertEqual(expr.evaluate('OPARAM 1',contexts),17)
        self.assertEqual(expr.evaluate('DES OPARAM 1',contexts),19)
        with self.assertRaisesRegex(ValueError,'APARAM'):expr.evaluate('APARAM 1',contexts)
        with self.assertRaises(ValueError):expr.evaluate('PARAM 1 + 2',contexts)
    def test_unsafe_malformed_and_excessive_input(self):
        for text in ('__import__("os")','P1.__class__','TAN(1,2)','PARAM 0','PARAM[1','1/0','1e999','[1]','1 ** 2','('+ '(' * 45+'1'+')'*46):
            with self.subTest(text=text),self.assertRaises(ValueError):expr.evaluate(text)


class RulesTests(unittest.TestCase):
    def setUp(self):self.data=project.sample()
    def definition(self,kind='GMSET'):
        d={'id':'new-'+kind,'kind':kind,'name':'/TEST-'+kind,'revision':'01','attrs':{},'elements':[]};self.data['definitions'].append(d);return d
    def problems(self,d,scom=None):return '\n'.join(catalogue.definition_issues(d,self.data['parameters'],scom))
    def test_point_number_reservation_duplicates_and_parent_attrs(self):
        d=self.definition('PTSET');first=schema.add_element(d,'PTAXI');second=schema.add_element(d,'PTPOS')
        first['attrs']['NUMB']='0';self.assertIn('P0',self.problems(d))
        first['attrs']['NUMB']=second['attrs']['NUMB'];self.assertIn('重複',self.problems(d))
        self.assertEqual(schema.PARENT_FIELDS['PTSET'],('DESC','GTYP','SKEY','PURP'))
    def test_negative_applies_combinations_not_item_attributes(self):
        d=self.definition('NGMSET');e=schema.add_element(d,'NSCY')
        self.assertEqual(schema.fields('NSCY','negative'),('NAPP',))
        self.assertEqual(e['attrs']['NAPP'],'1')
        for value in range(8):e['attrs']['NAPP']=str(value);self.assertNotIn('NAPP',self.problems(d))
        e['attrs']['NAPP']='8';self.assertIn('NAPP',self.problems(d))
        e['attrs']['PJOI']='/original';schema.change_type(e,'NLCY');self.assertEqual(e['attrs']['PJOI'],'/original')
    def test_per_primitive_meanings_and_alternative_radii(self):
        self.assertNotEqual(schema.meaning('SCON','PDIS'),schema.meaning('SCYL','PDIS'))
        self.assertIn('幅',schema.meaning('SRTO','PDIA'))
        self.assertIn('代替',schema.meaning('LSNO','PTRA'))
        d=self.definition();e=schema.add_element(d,'LSNO');e['attrs'].update(PTDM='PARAM 1',PTRA='PARAM 2')
        self.assertIn('両方',self.problems(d))
    def test_loops_vertices_roundtrip_rename_and_saved_edition_independence(self):
        d=self.definition();e=schema.add_element(d,'SEXT');loop=schema.add_child(e)
        for index in range(3):
            v=schema.add_child(loop);v['attrs'].update(PX='大径側外径 / 2',PY=str(index),PRAD='0')
        self.assertNotIn('PRAD',schema.fields('SEXT'))
        self.assertEqual(len(list(schema.walk(d['elements']))),5)
        self.assertNotIn('輪郭',self.problems(d))
        self.data['scoms'][0]['gmset_id']=d['id']
        book=booklet.snapshot(self.data,scom_ids=[self.data['scoms'][0]['id']],spec_ids=[])
        frozen=copy.deepcopy(book)
        project.rename_parameter(self.data,'P1','径')
        self.assertEqual(loop['children'][0]['attrs']['PX'],'径 / 2');self.assertEqual(book,frozen)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'data.json';project.save(self.data,path);self.assertEqual(project.load(path),self.data)
    def test_structure_limits_neutral_axis_and_angle_ranges(self):
        d=self.definition('GMSSET')
        for index in range(21):schema.add_element(d,'SREC')['attrs']['OBST']='1'
        self.assertNotIn('20',self.problems(d))
        p=self.definition('PTSSET');line=schema.add_element(p,'PLINE')
        self.assertNotIn('NAREF',self.problems(p));self.assertEqual(schema.neutral_axis(p)[1],'origin');p['attrs']['NAREF']=line['id'];self.assertNotIn('NAREF',self.problems(p))
        ann=schema.add_element(d,'SANN');ann['attrs']['PANG']='181';self.assertIn('180',self.problems(d))
        rev=schema.add_element(self.definition(),'SREV');rev['attrs']['PANGLE']='361'
        self.assertIn('360',self.problems(self.data['definitions'][-1]))
    def test_line_order_level_and_draw_flags(self):
        d=self.definition();e=schema.add_element(d,'LINE');e['attrs'].update(PTS='P1 T2 P3',LEVEL='2 8',CLFLA='TRUE')
        self.assertEqual(self.problems(d),'')
        e['attrs'].update(PTS=' '.join('P'+str(i) for i in range(7)),LEVEL='8 2',TUFLA='yes')
        problems=self.problems(d)
        for key in ('PTS','LEVEL','TUFLA'):self.assertIn(key,problems)
    def test_word_values_and_explicit_contexts_storage(self):
        self.data['parameters'].append({'id':'P6','role':'接続形式','unit':'','value_type':'word'})
        for scom in self.data['scoms']:scom['values']['P6']='BW'
        scom=self.data['scoms'][0];scom['expression_contexts']={'IPARAM':{'P1':5}};scom['component_attrs']={'ANGL':45}
        project.validate(self.data);self.assertEqual(expr.evaluate('PARAM 6',expr.contexts_for(scom)),'BW')
        bad=copy.deepcopy(self.data);bad['scoms'][0]['values']['P6']=3
        with self.assertRaises(ValueError):project.validate(bad)
        self.assertEqual(project.parse_value({'id':'P6','value_type':'word'},'001'),'001')
    def test_text_refs_tables_frozen_and_missing_text_rejected(self):
        cate=self.data['cates'][0]['id']
        text=catalogue.add_record(self.data,'texts','SDTE','/OWN-TEXT',cate);text['attrs'].update(RTEX='テスト部品',SKEY='TEST')
        material=catalogue.add_record(self.data,'texts','SMTE','/OWN-MATERIAL',cate);material['attrs']['XTEX']='テスト材質'
        entry=self.data['specs'][0]['entries'][0];entry.update(sdte_id=text['id'],smte_id=material['id'])
        table=catalogue.add_record(self.data,'tables','CCTA','/OWN-CONNECTIONS')
        pair=catalogue.add_record(self.data,'tables','COCO','/OWN-PAIR',table['id']);pair['attrs']['CTYPE']='BW BW'
        book=booklet.snapshot(self.data);frozen=copy.deepcopy(book)
        text['attrs']['RTEX']='変更';pair['attrs']['CTYPE']='BW XX';self.assertEqual(book,frozen)
        self.data['books'].append(book);project.validate(self.data)
        entry['sdte_id']='missing';self.assertIn('SDTE','\n'.join(project.issues(self.data)))
        with self.assertRaises(ValueError):booklet.snapshot(self.data)
    def test_role_rename_preserves_direction_and_description_literals(self):
        self.data['parameters'].append({'id':'P6','role':'X','unit':'mm'})
        d=self.definition('PTSET');e=schema.add_element(d,'PTMIX');e['attrs'].update(PAXI='X',PX='X / 2',DESC='X')
        project.rename_parameter(self.data,'P6','幅')
        self.assertEqual(e['attrs']['PAXI'],'X');self.assertEqual(e['attrs']['DESC'],'X');self.assertEqual(e['attrs']['PX'],'幅 / 2')

    def test_reference_roles_are_separate_and_frozen(self):
        self.data['reference_roles']={'IPARAM':{'P1':'断熱材厚さ'},'OPARAM':{'P1':'所有元の幅'}}
        project.validate(self.data);book=booklet.snapshot(self.data)
        self.data['reference_roles']['IPARAM']['P1']='変更後'
        self.assertEqual(book['reference_roles']['IPARAM']['P1'],'断熱材厚さ')
        self.data['reference_roles']['PARAM']={'P1':'別名'}
        with self.assertRaises(ValueError):project.validate(self.data)

    def test_nested_duplicate_ids_and_bad_storage_rejected(self):
        d=self.definition();e=schema.add_element(d,'SEXT');loop=schema.add_child(e);loop['id']=e['id']
        with self.assertRaises(ValueError):project.validate(self.data)
    def test_new_pdf_includes_texts_nested_vertices_and_tables(self):
        try:from pypdf import PdfReader
        except ImportError:self.skipTest('pypdf is not installed')
        d=self.definition();e=schema.add_element(d,'SEXT');loop=schema.add_child(e)
        for i in range(3):schema.add_child(loop)['attrs'].update(PX=str(i),PY='0',PRAD='0')
        self.data['scoms'][0]['gmset_id']=d['id']
        text=catalogue.add_record(self.data,'texts','SMTE','/PDF-MATERIAL',self.data['cates'][0]['id']);text['attrs']['XTEX']='PDF 材質テスト'
        self.data['specs'][0]['entries'][0]['smte_id']=text['id']
        bolt=catalogue.add_record(self.data,'tables','BLTP','/PDF-BOLT');bolt['attrs']['BTHK']='60'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'book.pdf';booklet.generate_pdf(booklet.snapshot(self.data),path)
            content='\n'.join(page.extract_text() for page in PdfReader(path).pages)
            for word in ('SLOO','SVER','/PDF-MATERIAL','PDF 材質テスト','BTHK','ボルト長さ'):self.assertIn(word,content)


class NewGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.app=IntegratedStudio()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.errors=[];self.app.report_callback_exception=lambda k,v,t:self.errors.append(str(v));self.app.update()
    def tearDown(self):
        if hasattr(self,'app'):self.app.destroy()
    def test_nested_vertices_order_copy_and_parent_fields(self):
        app=self.app;app.switch('gmset');editor=app.geometry_editor
        index=list(schema.GM_TYPES).index('SEXT');editor.library.selection_clear(0,'end');editor.library.selection_set(index);editor.add_element();app.update()
        root=editor.element();editor.add_child();app.update();loop=editor.element()
        editor.add_child();app.update();first=editor.element();first['attrs']['PX']='11'
        editor.element_id=loop['id'];editor.refresh();editor.add_child();app.update();second=editor.element()
        editor.move_element(-1);app.update();self.assertEqual(loop['children'][0]['id'],second['id'])
        editor.duplicate_element();app.update();self.assertEqual(len(loop['children']),3)
        self.assertTrue(editor.elements.exists(first['id']));self.assertEqual(self.errors,[])
        app.switch('ptset');editor=app.geometry_editor
        def accept(title,fields,apply):apply({k:('TEST' if k=='SKEY' else str(initial)) for k,_,initial,_ in fields})
        with patch.object(app,'form',side_effect=accept):editor.edit_parent()
        self.assertEqual(editor.definition()['attrs']['SKEY'],'TEST')
    def test_word_scom_paste_and_spec_text_edit(self):
        app=self.app;app.data['parameters'].append({'id':'P6','role':'接続形式','unit':'','value_type':'word'})
        candidate=app.parse_scom_paste('/WORD\t65x40\t76\t48\t100\t65\t40\tBW');self.assertEqual(candidate['scoms'][-1]['values']['P6'],'BW')
        text=catalogue.add_record(app.data,'texts','SDTE','/GUI-TEXT',app.cate_id)
        app.switch('specs');app.update();entry=app.spec_entry()
        def accept(title,fields,apply):apply({k:('/GUI-TEXT' if k=='sdte_id' else str(initial)) for k,_,initial,_ in fields})
        with patch.object(app,'form',side_effect=accept):app.entry_form(entry)
        self.assertEqual(entry['sdte_id'],text['id']);self.assertEqual(self.errors,[])
    def test_companion_pages_and_cate_delete_dependency(self):
        app=self.app;empty=project.add_cate(app.data);text=catalogue.add_record(app.data,'texts','SMTE','/DEPENDENT',empty['id'])
        app.switch('texts');app.update();editor=app.companion_editor
        self.assertTrue(editor.table.exists(text['id']))
        self.assertLess(editor.winfo_y(),app.content.winfo_height())
        app.cate_id=empty['id']
        with patch('catalog_studio.integrated.messagebox.showinfo'),patch('catalog_studio.integrated.messagebox.askyesno') as confirm:app.delete_cate();confirm.assert_not_called()
        self.assertIsNotNone(project.get(app.data,'cates',empty['id']));self.assertEqual(self.errors,[])

    def test_expression_eval_and_original_preserved_after_normalization(self):
        app=self.app;editor=app.geometry_editor;editor.field='PDIS';editor.busy=True;editor.load_field();editor.busy=False
        editor.expression.set('0.5 TIMES PARAM 3');app.update();self.assertIn('44.5',editor.validation_note.cget('text'))
        editor.normalize_expression();self.assertEqual(editor.element()['expression_sources']['PDIS'],'0.5 TIMES PARAM 3')
        self.assertEqual(expr.evaluate(editor.expression.get(),{'PARAM':{'P3':10}}),5);self.assertEqual(self.errors,[])
