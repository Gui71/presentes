from pathlib import Path
import tempfile
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from gifts.illustrations import catalog, read_illustration
from gifts.illustrations.service import apply_illustration
from gifts.models import Product, ProductLink, Selection
from gifts.services import ProductConflict, update_product


class IllustrationChoiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user("illustration-choice-manager")
        cls.manager.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="gifts", codename__in=["view_product", "add_product", "change_product"],
        ))
        cls.product = Product.objects.create(
            name="Kit Panelas", created_by=cls.manager, submission_key=uuid.uuid4(),
        )
        ProductLink.objects.create(product=cls.product, url="https://shop.example/opaque", position=0)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.media = Path(directory.name)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client.force_login(self.manager)
        self.action = reverse("apply_illustration", args=[self.product.pk])
        self.preview = reverse("illustration_preview", args=[self.product.pk])

    def files(self):
        return sorted(str(path.relative_to(self.media)) for path in self.media.rglob("*.webp"))

    def state(self):
        self.product.refresh_from_db()
        return (
            self.product.name, self.product.image.name, self.product.illustration_choice,
            self.product.illustration_key, self.product.illustration_digest, self.product.revision,
        )

    def create_data(self, name="Presente especial", choice="towel_set"):
        page = self.client.get(reverse("panel"))
        return {
            "name": name, "illustration_choice": choice,
            "submission_key": page.context["submission_key"],
            "links-TOTAL_FORMS": "1", "links-INITIAL_FORMS": "0",
            "links-0-url": "https://shop.example/opaque",
        }

    def apply(self, choice, replace=True, revision=None):
        self.product.refresh_from_db()
        data = {
            "revision": self.product.revision if revision is None else revision,
            "illustration_choice": choice,
        }
        if replace:
            data["replace_image"] = "1"
        return self.client.post(self.action, data)

    def test_add_only_manager_can_choose_from_catalog_at_creation_without_network_or_duplicates(self):
        creator = get_user_model().objects.create_user("illustration-choice-creator")
        creator.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="gifts", codename__in=["view_product", "add_product"],
        ))
        self.client.force_login(creator)
        page = self.client.get(reverse("panel"))
        field = page.context["product_form"].fields["illustration_choice"]
        self.assertFalse(field.required)
        self.assertEqual({key for key, label in field.choices}, {""} | {item.key for item in catalog()})
        data = self.create_data()
        with patch("socket.create_connection", side_effect=AssertionError("No network")):
            self.assertEqual(self.client.post(reverse("create_product"), data).status_code, 302)
        product = Product.objects.get(submission_key=data["submission_key"])
        self.assertEqual(product.created_by, creator)
        self.assertEqual(product.illustration_choice, "towel_set")
        self.assertEqual(product.illustration_key, "towel_set")
        self.assertTrue(product.has_available_image)
        original_file, original_revision = product.image.name, product.revision
        self.assertEqual(self.client.post(reverse("create_product"), data).status_code, 302)
        product.refresh_from_db()
        self.assertEqual((product.image.name, product.revision), (original_file, original_revision))
        self.assertEqual(len(self.files()), 1)
        self.assertEqual(self.client.post(reverse("apply_illustration", args=[product.pk]), {
            "revision": product.revision, "illustration_choice": "cutlery", "replace_image": "1",
        }).status_code, 403)

    def test_forged_choice_prevents_creation_and_does_not_write_files(self):
        data = self.create_data()
        before = Product.objects.count()
        for choice in ("../../.env", "https://private.example/image.webp", "missing", "cutlery.webp"):
            with self.subTest(choice=choice):
                data["illustration_choice"] = choice
                response = self.client.post(reverse("create_product"), data)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context["product_form"].errors.get("illustration_choice"))
                self.assertEqual(Product.objects.count(), before)
                self.assertEqual(self.files(), [])

    def test_unknown_existing_name_can_preview_catalog_choice_without_any_mutation(self):
        self.product.name = "Presente especial"
        self.product.save(update_fields=["name"])
        original = self.state()
        self.assertContains(self.client.get(reverse("panel")), "Escolher ilustração")
        with patch("socket.create_connection", side_effect=AssertionError("No network")):
            page = self.client.get(self.action, {"illustration_choice": "towel_set"})
            self.assertContains(page, "Usar esta ilustração")
            preview = self.client.get(self.preview, {"illustration_choice": "towel_set"})
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview["Content-Type"], "image/webp")
            self.assertIn("no-store", preview["Cache-Control"])
            expected = next(item for item in catalog() if item.key == "towel_set")
            self.assertEqual(b"".join(preview.streaming_content), read_illustration(expected))
        self.assertEqual(self.state(), original)
        self.assertEqual(self.files(), [])

    def test_unknown_existing_name_receives_the_selected_image_and_card(self):
        self.product.name = "Presente especial"
        self.product.save(update_fields=["name"])
        self.assertEqual(self.apply("towel_set", replace=False).status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.illustration_choice, "towel_set")
        self.assertEqual(self.product.catalog_illustration.key, "towel_set")
        self.assertTrue(self.product.has_available_image)
        self.assertContains(self.client.get(reverse("panel")), reverse("product_image", args=[self.product.pk]))

    def test_fifteen_added_illustrations_are_selectable_and_preview_without_modifying_products(self):
        keys = {
            "oven_mitts", "corkscrew", "bottle_opener", "can_opener", "closet_organizers",
            "vegetable_cutter", "pressure_cooker", "broom_squeegee_dustpan",
            "double_wall_coffee_cups", "vacuum_cleaner", "dish_drying_mat", "toilet_brush",
            "steel_grater", "clothes_hangers", "air_fryer",
        }
        before = self.state()
        count = Product.objects.count()
        page = self.client.get(reverse("panel"))
        choices = dict(page.context["product_form"].fields["illustration_choice"].choices)
        with patch("socket.create_connection", side_effect=AssertionError("No network")):
            for item in catalog():
                if item.key not in keys:
                    continue
                with self.subTest(key=item.key):
                    self.assertEqual(choices[item.key], item.label)
                    response = self.client.get(self.preview, {"illustration_choice": item.key})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(b"".join(response.streaming_content), read_illustration(item))
        self.assertEqual(self.state(), before)
        self.assertEqual(Product.objects.count(), count)
        self.assertEqual(self.files(), [])

    def test_previous_image_and_mode_remain_until_explicit_replacement(self):
        apply_illustration(self.product.pk, 0)
        original = self.state()
        self.client.get(self.action, {"illustration_choice": "towel_set"})
        self.assertEqual(self.state(), original)
        self.assertEqual(self.apply("towel_set", replace=False).status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, original[1])
        self.assertEqual(self.product.illustration_choice, "")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.apply("towel_set").status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.illustration_choice, "towel_set")
        self.assertEqual(self.product.illustration_key, "towel_set")
        self.assertNotEqual(self.product.image.name, original[1])
        self.assertFalse((self.media / original[1]).exists())

    def test_rename_and_forged_edit_choice_preserve_the_manual_image(self):
        self.apply("towel_set")
        original_file = self.state()[1]
        edit = reverse("edit_product", args=[self.product.pk])
        self.assertNotContains(self.client.get(edit), 'name="illustration_choice"')
        response = self.client.post(edit, {
            "name": "Liquidificador", "revision": self.product.revision,
            "illustration_choice": "cutlery", "links-TOTAL_FORMS": "1", "links-INITIAL_FORMS": "1",
            "links-0-url": "https://other.example/opaque",
        })
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Liquidificador")
        self.assertEqual(self.product.illustration_choice, "towel_set")
        self.assertEqual(self.product.image.name, original_file)
        self.assertEqual(self.product.catalog_illustration.key, "towel_set")
        self.assertNotIn("O nome mudou", self.product.image_notice)

    def test_switching_back_to_automatic_uses_name_and_can_reuse_the_same_file(self):
        self.apply("cutlery")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.apply("").status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.illustration_choice, "")
        self.assertEqual(self.product.illustration_key, "cookware_black")
        automatic_file = self.product.image.name
        self.assertEqual(self.apply("cookware_black").status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.illustration_choice, "cookware_black")
        self.assertEqual(self.product.image.name, automatic_file)
        self.assertEqual(self.apply("").status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.illustration_choice, "")
        self.assertEqual(self.product.image.name, automatic_file)
        self.assertEqual(len(self.files()), 1)

    def test_automatic_without_a_match_does_not_erase_an_existing_manual_image(self):
        self.product.name = "Presente especial"
        self.product.save(update_fields=["name"])
        self.apply("towel_set")
        original = self.state()
        self.assertEqual(self.apply("").status_code, 302)
        self.assertEqual(self.state(), original)

    def test_service_rejects_forged_keys_before_writing_and_views_reject_invalid_choices(self):
        apply_illustration(self.product.pk, 0)
        original, files = self.state(), self.files()
        for choice in ("../../.env", "not-in-catalog", "https://shop.example/image"):
            with self.subTest(choice=choice):
                with self.assertRaises(ValueError):
                    apply_illustration(self.product.pk, self.product.revision, True, illustration_choice=choice)
                self.assertEqual(self.client.get(self.action, {"illustration_choice": choice}).status_code, 400)
                self.assertIn(self.client.get(self.preview, {"illustration_choice": choice}).status_code, (400, 404))
                self.assertEqual(self.apply(choice).status_code, 400)
                self.assertEqual(self.state(), original)
                self.assertEqual(self.files(), files)

    def test_selected_product_keeps_identity_links_and_guest_choice_when_image_changes(self):
        choice = Selection.objects.create(
            product=self.product, owner_digest="private-owner", first_name="Ana", surname="Silva",
        )
        self.assertEqual(self.apply("towel_set").status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Kit Panelas")
        self.assertEqual(self.product.links.get().url, "https://shop.example/opaque")
        choice.refresh_from_db()
        self.assertEqual(choice.product_id, self.product.pk)
        self.assertEqual((choice.owner_digest, choice.first_name, choice.surname), ("private-owner", "Ana", "Silva"))
        self.assertEqual(self.product.illustration_choice, "towel_set")
        self.assertTrue(self.product.has_available_image)

    def test_choice_actions_and_preview_require_change_permission_and_csrf(self):
        original = self.state()
        anonymous = Client()
        self.assertEqual(anonymous.get(self.action, {"illustration_choice": "towel_set"}).status_code, 302)
        self.assertEqual(anonymous.get(self.preview, {"illustration_choice": "towel_set"}).status_code, 302)
        for permissions in (["view_product"], ["change_product"]):
            user = get_user_model().objects.create_user("choice-" + permissions[0])
            user.user_permissions.add(*Permission.objects.filter(
                content_type__app_label="gifts", codename__in=permissions,
            ))
            anonymous.force_login(user)
            self.assertEqual(anonymous.get(self.action).status_code, 403)
            self.assertEqual(anonymous.get(self.preview, {"illustration_choice": "towel_set"}).status_code, 403)
            self.assertEqual(anonymous.post(self.action, {
                "revision": 0, "illustration_choice": "towel_set", "replace_image": "1",
            }).status_code, 403)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.manager)
        self.assertEqual(protected.post(self.action, {
            "revision": 0, "illustration_choice": "towel_set", "replace_image": "1",
        }).status_code, 403)
        self.assertEqual(self.state(), original)
        self.assertEqual(self.files(), [])

    def test_storage_failure_rolls_back_choice_origin_revision_and_image(self):
        apply_illustration(self.product.pk, 0)
        original, files = self.state(), self.files()
        with patch.object(self.product.image.storage, "save", side_effect=OSError("private storage detail")):
            response = self.apply("towel_set")
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, "private storage detail", status_code=400)
        self.assertEqual(self.state(), original)
        self.assertEqual(self.files(), files)

    def test_stale_manual_choice_cannot_overwrite_after_product_edit(self):
        apply_illustration(self.product.pk, 0)
        self.product.refresh_from_db()
        stale_revision, original_file = self.product.revision, self.product.image.name
        update_product(self.product.pk, stale_revision, "Liquidificador", ["https://other.example/new"])
        current = self.state()
        with self.assertRaises(ProductConflict):
            apply_illustration(self.product.pk, stale_revision, True, illustration_choice="towel_set")
        self.assertEqual(self.apply("towel_set", revision=stale_revision).status_code, 409)
        self.assertEqual(self.state(), current)
        self.assertEqual(self.files(), [original_file])

    def test_missing_manual_file_is_restored_from_persisted_choice_despite_different_name(self):
        self.apply("towel_set")
        self.product.refresh_from_db()
        old_name = self.product.image.name
        (self.media / old_name).unlink()
        self.assertEqual(apply_illustration(self.product.pk, self.product.revision), "applied")
        self.product.refresh_from_db()
        self.assertEqual(self.product.illustration_choice, "towel_set")
        self.assertEqual(self.product.illustration_key, "towel_set")
        self.assertNotEqual(self.product.image.name, old_name)
        self.assertTrue(self.product.has_available_image)
