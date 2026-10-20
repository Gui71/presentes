from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
import uuid


class PreserveDataMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_product_selection_links_and_grants_only_legacy_view(self):
        executor=MigrationExecutor(connection)
        executor.migrate([('gifts','0002_selection')])
        try:
            old=executor.loader.project_state([('gifts','0002_selection')]).apps
            User=old.get_model('auth','User');Permission=old.get_model('auth','Permission')
            user=User.objects.create(username='legacy-manager')
            add=Permission.objects.get(codename='add_product',content_type__app_label='gifts')
            user.user_permissions.add(add)
            Product=old.get_model('gifts','Product');Link=old.get_model('gifts','ProductLink');Selection=old.get_model('gifts','Selection')
            product=Product.objects.create(name='Preservar',created_by=user,submission_key=uuid.uuid4(),image='products/keep.webp')
            Link.objects.create(product=product,url='https://shop.example/keep',position=0)
            choice=Selection.objects.create(product=product,owner_digest='keep-owner',first_name='Ana',surname='Silva')
            executor=MigrationExecutor(connection);executor.migrate([('gifts','0004_preserve_existing_panel_access')])
            from gifts.models import Product as CurrentProduct, Selection as CurrentSelection
            from django.contrib.auth import get_user_model
            current=CurrentProduct.objects.get(pk=product.pk)
            self.assertEqual(current.name,'Preservar');self.assertEqual(current.image.name,'products/keep.webp');self.assertEqual(current.revision,0)
            self.assertEqual(current.links.get().url,'https://shop.example/keep')
            self.assertEqual(CurrentSelection.objects.get(pk=choice.pk).owner_digest,'keep-owner')
            manager=get_user_model().objects.get(pk=user.pk)
            self.assertTrue(manager.has_perm('gifts.view_product'))
            for permission in ['change_product','delete_product','export_database','export_selections']:
                self.assertFalse(manager.has_perm('gifts.'+permission))
        finally:
            executor=MigrationExecutor(connection);executor.migrate(executor.loader.graph.leaf_nodes())
