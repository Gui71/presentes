import io
from pathlib import Path
import sqlite3
import tempfile
import threading
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from gifts.models import Product, ProductLink, Selection
from gifts.backups import sqlite_snapshot
from gifts.external import recode_image
from .test_external import raster


class ManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('manager')
        cls.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='gifts',codename__in=['view_product','add_product','change_product','delete_product']))
        cls.product = Product.objects.create(name='Panela',created_by=cls.user,submission_key=uuid.uuid4())
        ProductLink.objects.create(product=cls.product,url='https://shop.example/first',position=0)
        ProductLink.objects.create(product=cls.product,url='https://shop.example/second',position=1)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client.force_login(self.user)

    def data(self):
        self.product.refresh_from_db()
        return {'name':'Panela atualizada','revision':self.product.revision,'links-TOTAL_FORMS':'2','links-INITIAL_FORMS':'2','links-0-url':'https://new.example/first','links-1-url':'https://new.example/second'}

    def selection(self):
        return Selection.objects.create(product=self.product,first_name='Ana',surname='Silva',owner_digest='owner')

    def test_public_has_no_login_shortcut_but_direct_login_still_works(self):
        page=Client().get('/')
        self.assertNotContains(page,'Área dos anfitriões')
        self.assertNotContains(page,'href="/login')
        self.assertEqual(Client().get('/login').status_code,301)
        self.assertEqual(Client().get('/login/').status_code,200)

    def test_selected_cards_keep_purchase_links_but_prevent_new_choices(self):
        guest=Client();guest.post(reverse('identify'),{'first_name':'Ana','surname':'Silva'})
        guest.post(reverse('choose_product',args=[self.product.pk]))
        page=guest.get('/')
        for url in ('https://shop.example/first','https://shop.example/second'):
            self.assertContains(page, 'href="'+url+'" target="_blank" rel="noopener noreferrer"')
        self.assertContains(page,'class="product-card selected"')
        self.assertNotContains(page,'data-choose')
        self.assertContains(page,'Cancelar minha escolha')
        other=Client();other.post(reverse('identify'),{'first_name':'Ana','surname':'Silva'})
        other_page=other.get('/')
        self.assertContains(other_page,'https://shop.example/first')
        self.assertContains(other_page,'https://shop.example/second')
        self.assertNotContains(other_page,'data-choose')
        self.assertNotContains(other_page,'Cancelar minha escolha')
        other.post(reverse('choose_product',args=[self.product.pk]))
        self.assertEqual(Selection.objects.filter(product=self.product).count(),1)
        guest.post(reverse('cancel_selection_visitor',args=[self.product.pk]))
        self.assertContains(other.get('/'),'https://shop.example/first')
        self.assertContains(other.get('/'),'https://shop.example/second')
        self.assertContains(other.get('/'),'data-choose')
        self.assertNotContains(other.get('/'),'class="product-card selected"')

    @patch('gifts.external.obtain_product_image')
    def test_edit_prefills_modal_updates_order_and_preserves_creator(self, obtain):
        url=reverse('edit_product',args=[self.product.pk])
        page=self.client.get(url)
        self.assertContains(page,'value="Panela"')
        self.assertContains(page,'https://shop.example/second')
        self.assertEqual(self.client.post(url,self.data()).status_code,302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name,'Panela atualizada')
        self.assertEqual(self.product.created_by,self.user)
        self.assertEqual(list(self.product.links.values_list('url',flat=True)),['https://new.example/first','https://new.example/second'])
        obtain.assert_not_called()

    def test_selected_item_cannot_be_edited_deleted_or_deleted_through_model(self):
        self.selection()
        for route in ['edit_product','delete_product']:
            url=reverse(route,args=[self.product.pk])
            self.assertEqual(self.client.get(url).status_code,409)
            self.assertEqual(self.client.post(url,self.data()).status_code,409)
        self.assertEqual(Selection.objects.count(),1)
        self.product.refresh_from_db();self.assertEqual(self.product.name,'Panela')
        with self.assertRaises(ProtectedError):self.product.delete()

    def test_confirmation_before_edit_write_prevents_stale_edit(self):
        from gifts.services import update_product
        guest=Client();guest.post(reverse('identify'),{'first_name':'Ana','surname':'Silva'})
        def select(*args):
            guest.post(reverse('choose_product',args=[self.product.pk]))
            return update_product(*args)
        with patch('gifts.services.update_product',side_effect=select):
            response=self.client.post(reverse('edit_product',args=[self.product.pk]),self.data())
        self.assertEqual(response.status_code,409)
        self.product.refresh_from_db();self.assertEqual(self.product.name,'Panela')
        self.assertEqual(Selection.objects.count(),1)

    def test_view_add_edit_delete_and_exports_are_separate_permissions(self):
        user=get_user_model().objects.create_user('reader')
        user.user_permissions.add(Permission.objects.get(codename='view_product'))
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('panel')).status_code,200)
        self.assertNotContains(self.client.get(reverse('panel')),'Adicionar novo item')
        for route,args in [('create_product',[]),('edit_product',[self.product.pk]),('delete_product',[self.product.pk]),('retry_product_image',[self.product.pk]),('export_database',[]),('export_selections',[])]:
            self.assertEqual(self.client.post(reverse(route,args=args),{}).status_code,403)
        add_only=get_user_model().objects.create_user('add-only')
        add_only.user_permissions.add(Permission.objects.get(codename='add_product'))
        self.client.force_login(add_only)
        self.assertEqual(self.client.get(reverse('panel')).status_code,403)

    def test_write_endpoints_require_csrf(self):
        self.user.user_permissions.add(*Permission.objects.filter(codename__in=['export_database','export_selections']))
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        for route,args in [('edit_product',[self.product.pk]),('delete_product',[self.product.pk]),('retry_product_image',[self.product.pk]),('export_database',[]),('export_selections',[])]:
            self.assertEqual(client.post(reverse(route,args=args),{}).status_code,403)

    def test_delete_confirmation_and_duplicate_post_do_not_leave_links_or_image(self):
        with tempfile.TemporaryDirectory() as directory,override_settings(MEDIA_ROOT=directory):
            from django.core.files.base import ContentFile
            self.product.image.save('photo.webp',ContentFile(recode_image(raster())))
            photo=Path(self.product.image.path)
            url=reverse('delete_product',args=[self.product.pk])
            self.assertContains(self.client.get(url),'Excluir este presente?')
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.client.post(url,{'revision':self.product.revision}).status_code,302)
            self.assertEqual(self.client.post(url,{'revision':0}).status_code,302)
            self.assertFalse(Product.objects.exists());self.assertFalse(ProductLink.objects.exists());self.assertFalse(photo.exists())

    @patch('gifts.external.obtain_product_image')
    def test_editing_links_keeps_previous_valid_image_without_fetching(self, obtain):
        with tempfile.TemporaryDirectory() as directory,override_settings(MEDIA_ROOT=directory):
            from django.core.files.base import ContentFile
            self.product.image.save('photo.webp',ContentFile(recode_image(raster())))
            old=self.product.image.name
            self.client.post(reverse('edit_product',args=[self.product.pk]),self.data())
            self.product.refresh_from_db();self.assertEqual(self.product.image.name,old)
            obtain.assert_not_called()

    def test_missing_image_can_be_retried_without_affecting_selection(self):
        self.product.name='Kit Panelas';self.product.save()
        self.selection()
        with tempfile.TemporaryDirectory() as directory,override_settings(MEDIA_ROOT=directory):
            self.assertEqual(self.client.post(reverse('retry_product_image',args=[self.product.pk]),{'revision':self.product.revision}).status_code,302)
            self.product.refresh_from_db();self.assertTrue(self.product.image)
            self.assertEqual(Selection.objects.count(),1)

    def test_missing_physical_file_shows_retry_and_gets_replaced(self):
        self.product.name='Kit Panelas';self.product.image='products/missing.webp';self.product.save()
        self.assertContains(self.client.get(reverse('panel')),'Usar ilustração')
        with tempfile.TemporaryDirectory() as directory,override_settings(MEDIA_ROOT=directory):
            self.client.post(reverse('retry_product_image',args=[self.product.pk]),{'revision':self.product.revision})
            self.product.refresh_from_db();self.assertNotEqual(self.product.image.name,'products/missing.webp')
            self.assertTrue(self.product.image.storage.exists(self.product.image.name))

    def test_xlsx_literal_values_homonyms_multiple_choices_and_cancelled_excluded(self):
        root=get_user_model().objects.create_superuser('root')
        self.client.force_login(root)
        products=[self.product]+[Product.objects.create(name=name,created_by=root,submission_key=uuid.uuid4()) for name in ['=HYPERLINK("bad")','Outro','Cancelado']]
        for index,product in enumerate(products):
            Selection.objects.create(product=product,first_name='=Ana',surname='Silva',owner_digest='owner'+str(index))
        Selection.objects.filter(product=products[-1]).delete()
        response=self.client.post(reverse('export_selections'))
        filename=str(Path(response.directory.name)/'conferencia.xlsx')
        body=b''.join(response.streaming_content)
        self.assertIn('no-store',response['Cache-Control']);self.assertIn('attachment;',response['Content-Disposition'])
        response.close();self.assertFalse(Path(filename).exists())
        workbook=load_workbook(io.BytesIO(body))
        rows=list(workbook.active.rows)
        self.assertEqual([cell.value for cell in rows[0]],['Nome e primeiro sobrenome','Presente selecionado'])
        self.assertEqual(len(rows),4)
        for row in rows[1:]:
            self.assertEqual(row[0].value,'=Ana Silva');self.assertEqual(row[0].data_type,'s');self.assertEqual(row[1].data_type,'s')
        workbook.close()

    def test_empty_xlsx_has_only_two_headers(self):
        root=get_user_model().objects.create_superuser('root');self.client.force_login(root)
        response=self.client.post(reverse('export_selections'))
        workbook=load_workbook(io.BytesIO(b''.join(response.streaming_content)))
        self.assertEqual(workbook.active.max_column,2);self.assertEqual(workbook.active.max_row,1)
        workbook.close();response.close()


class DatabaseExportTests(TransactionTestCase):
    def test_snapshot_is_consistent_while_another_connection_writes_in_wal(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.sqlite3';target=Path(directory)/'copy.db'
            with sqlite3.connect(source) as database:
                database.execute('PRAGMA journal_mode=WAL')
                database.execute('CREATE TABLE live_records (id INTEGER PRIMARY KEY,value TEXT)');database.commit()
            stopped=threading.Event();started=threading.Event();failures=[]
            def write():
                try:
                    with sqlite3.connect(source,timeout=5) as database:
                        while not stopped.is_set():
                            database.execute("INSERT INTO live_records(value) VALUES ('concurrent')");database.commit();started.set()
                            stopped.wait(.001)
                except Exception as exc:failures.append(exc);started.set()
            thread=threading.Thread(target=write);thread.start()
            try:
                self.assertTrue(started.wait(5));sqlite_snapshot(source,target)
            finally:stopped.set();thread.join(timeout=5)
            self.assertEqual(failures,[])
            with sqlite3.connect(target) as database:
                self.assertEqual(database.execute('PRAGMA integrity_check').fetchone(),('ok',))
                self.assertGreater(database.execute('SELECT COUNT(*) FROM live_records').fetchone()[0],0)

    def test_authorized_database_export_is_valid_private_and_cleaned(self):
        root=get_user_model().objects.create_superuser('root');self.client.force_login(root)
        response=self.client.post(reverse('export_database'))
        self.assertEqual(response.status_code,200)
        self.assertRegex(response['Content-Disposition'],r'banco-presentes-\d{8}-\d{6}\.db')
        path=Path(response.directory.name)/'snapshot.db'
        with sqlite3.connect(path) as database:
            self.assertEqual(database.execute('PRAGMA integrity_check').fetchone(),('ok',))
            self.assertEqual(database.execute('SELECT username FROM auth_user').fetchone(),('root',))
        self.assertEqual(path.stat().st_mode&0o777,0o600)
        response.close();self.assertFalse(path.exists())

    def test_wal_snapshot_includes_committed_writes_and_survives_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'active.sqlite3';target=Path(directory)/'snapshot.db'
            with sqlite3.connect(source) as writer:
                self.assertEqual(writer.execute('PRAGMA journal_mode=WAL').fetchone(),('wal',))
                writer.execute('CREATE TABLE records (value TEXT)');writer.commit()
                writer.execute('INSERT INTO records VALUES (?)',('durante WAL',));writer.commit()
                self.assertTrue(Path(str(source)+'-wal').exists())
                sqlite_snapshot(source,target)
            source.unlink()
            with sqlite3.connect(target) as restored:
                self.assertEqual(restored.execute('SELECT value FROM records').fetchall(),[('durante WAL',)])
