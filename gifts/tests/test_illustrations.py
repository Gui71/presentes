import io
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
import uuid
from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.management import call_command, CommandError
from django.db import IntegrityError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from gifts.illustrations import catalog, match_illustration, read_illustration
from gifts.illustrations.service import apply_illustration
from gifts.models import Product, ProductLink, Selection
from gifts.services import ProductConflict, update_product
from gifts.external import recode_image
from .test_external import raster


class CatalogTests(SimpleTestCase):
    def test_invalid_or_oversized_local_asset_is_rejected_even_with_manifest_entry(self):
        original = match_illustration("Faqueiro")
        cases = [b'<svg onload="bad()"/>', b"x" * (1024 * 1024 + 1), raster()]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.webp"
            for data in cases:
                path.write_bytes(data)
                candidate = replace(original, digest=sha256(data).hexdigest())
                with patch.object(type(candidate), "path", new_callable=PropertyMock, return_value=path):
                    with self.assertRaises((OSError, ValueError)):
                        read_illustration(candidate)

    def test_generated_assets_are_valid_bounded_webp_with_verified_integrity(self):
        self.assertGreaterEqual(len(catalog()), 40)
        for item in catalog():
            with self.subTest(item=item.key):
                data = read_illustration(item)
                with Image.open(io.BytesIO(data)) as image:
                    self.assertEqual(image.format, "WEBP")
                    self.assertLessEqual(max(image.size), 1000)
                    self.assertFalse(image.info.get("exif"))

    def test_names_from_the_requested_list_include_accents_punctuation_and_sets(self):
        cases = {
            "Kit Panelas - pretas - Tramontina": "cookware_black",
            "Frigideira - Sem ser toda metálica/inox - Tramontina": "frying_pan",
            "Leiteira - Sem ser toda metálica/inox Tramontina": "milk_pan",
            "Panela de pipoca (pipoqueira) - Tramontina": "popcorn_pan",
            "Talheres - Prata ou preto (Brinox, tramontina)": "cutlery",
            "Pratos - Branco/Transparente/Preto": "dinnerware_set",
            "Copos - Diversos": "drinking_glasses",
            "Kit utensílios de cozinhas (colheres e etc)": "kitchen_utensils",
            "Pirex Redondo com tampa": "round_casserole",
            "Pirex retangular": "rectangular_casserole",
            "Forma de bolo": "cake_pan", "Forma de pizza": "pizza_pan",
            "Saleiro": "salt_cellar", "Açucareiro": "sugar_bowl",
            "Tábua de carne": "cutting_board", "5 panos de chão": "floor_cloths",
            "4 panos de prato": "dish_towels", "Prendedor de roupas": "clothespins",
            "Balde (2)": "buckets", "Pá de lixo - Cor cinza": "dustpan",
            "Rodinho de pia": "sink_squeegee", "Cesto de Roupas - Preto/Cinza/branco": "laundry_basket",
            "Bacias": "wash_basins", "Kit Potes de plástico": "plastic_containers",
            "Kit Potes herméticos para macarrão/arroz/etc": "pantry_containers",
            "Kit potes de vidro (borossilicato)": "glass_containers",
            "Pote grande para pipoca (plástico)": "popcorn_bowl",
            "Porta detergente": "detergent_holder", "Kit facas Tramontina": "knife_set",
            "Jarra de suco (vidro ou plástico)": "pitcher", "Jarras para água (vidro)": "pitcher",
            "Tesoura de cozinha": "kitchen_scissors", "Escorredor de Macarrão (Inox)": "colander",
            "Porta temperos": "spice_rack", "Potes de sobremesa (diversos)": "dessert_bowls",
            "Porta sabonete banheiro": "soap_dish", "Lixeira para banheiro": "waste_bin",
            "Lixeira cozinha": "waste_bin", "Jogo Roupa de cama": "bedding_set",
            "Kit Toalha": "towel_set", "Kit tapetes banheiro": "bath_mats",
            "Batedeira": "stand_mixer", "Cafeteira": "coffee_maker",
            "Liquidificador": "blender", "Mini processador": "mini_processor",
            "Sanduicheira": "sandwich_maker", "Ferro de passar": "clothes_iron",
            "Mini máquina de waffle pequena": "waffle_maker",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                candidate = match_illustration(name)
                self.assertIsNotNone(candidate)
                self.assertEqual(candidate.key, expected)

    def test_unknown_ambiguous_parts_and_unrelated_variants_do_not_get_random_illustrations(self):
        for name in ["Presente", "B07WGQ64QR", "Kit panelas e liquidificador", "Porta talheres",
                     "Copo para liquidificador", "Toalhas de mesa", "Jogo de toalhas de mesa",
                     "Cafeteira italiana", "Chaleira", "Panela de pressão", "Porta-talher",
                     "Porta de talheres", "Porta de talher", "Talher", "Toalhas de praia",
                     "Toalhas de piscina", "Toalhas de boca", "Toalhas de papel", "Toalhas de cozinha",
                     "Toalhas de prato", "Porta-toalhas", "Suporte para toalhas", "Varal de toalhas",
                     "jogo de talher e toalhas"]:
            with self.subTest(name=name):
                self.assertIsNone(match_illustration(name))

    def test_common_singular_set_names_and_bare_plural_towels_are_recognized(self):
        cases = {
            "jogo de talher": "cutlery", "JOGO DE TALHER - Tramontina": "cutlery",
            "Jogo talher": "cutlery", "Kit de talher": "cutlery", "Kit talher": "cutlery",
            "Conjunto de talher": "cutlery", "toalhas": "towel_set", "Toalhas de banho": "towel_set",
            "Kit de toalha": "towel_set", "Jogo de toalha": "towel_set",
            "Jogo toalha": "towel_set", "Conjunto de toalha": "towel_set",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(match_illustration(name).key, expected)

    def test_check_command_can_diagnose_names_without_accessing_the_database(self):
        for name, key in [("jogo de talher", "cutlery"), ("toalhas", "towel_set")]:
            with self.subTest(name=name):
                output = io.StringIO()
                call_command("check_illustrations", name=name, stdout=output)
                self.assertIn(f"{len(catalog())} ilustrações locais válidas", output.getvalue())
                self.assertIn(f"({key})", output.getvalue())
        for name in ("Presente", "jogo de talher e toalhas", ""):
            with self.subTest(name=name):
                with self.assertRaisesMessage(CommandError, "Nome sem correspondência única"):
                    call_command("check_illustrations", name=name, stdout=io.StringIO())


class IllustrationWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user("catalog-manager")
        cls.manager.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="gifts", codename__in=["view_product", "add_product", "change_product", "delete_product"],
        ))
        cls.product = Product.objects.create(name="Kit Panelas", created_by=cls.manager, submission_key=uuid.uuid4())
        ProductLink.objects.create(product=cls.product, url="https://shop.example/opaque-code", position=0)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_context = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_context.enable()
        self.addCleanup(self.settings_context.disable)
        self.client.force_login(self.manager)
        self.action = reverse("apply_illustration", args=[self.product.pk])

    def previous_image(self):
        self.product.image.save("old.webp", ContentFile(recode_image(raster())))
        return self.product.image.name

    def create(self, name, url="https://amzn.to/opaque-code?tracking=private"):
        page = self.client.get(reverse("panel"))
        return self.client.post(reverse("create_product"), {
            "name": name, "submission_key": page.context["submission_key"],
            "links-TOTAL_FORMS": "1", "links-INITIAL_FORMS": "0", "links-0-url": url,
        })

    def test_create_uses_only_name_and_never_connects_to_shops_or_generation_apis(self):
        with patch("socket.create_connection", side_effect=AssertionError("No network")):
            self.assertEqual(self.create("Faqueiro").status_code, 302)
            product = Product.objects.get(name="Faqueiro")
            self.assertEqual(product.illustration_key, "cutlery")
            self.assertTrue(product.has_available_image)
            self.assertEqual(product.links.get().url, "https://amzn.to/opaque-code?tracking=private")

    def test_unknown_name_keeps_placeholder_even_when_url_looks_like_another_product(self):
        self.assertEqual(self.create("Presente", "https://shop.example/liquidificador").status_code, 302)
        product = Product.objects.get(name="Presente")
        self.assertFalse(product.image)
        self.assertIn("Sem ilustração compatível", product.image_notice)

    def test_reported_names_create_cards_with_working_images(self):
        for name, key in [("jogo de talher", "cutlery"), ("toalhas", "towel_set")]:
            with self.subTest(name=name):
                self.assertEqual(self.create(name).status_code, 302)
                product = Product.objects.get(name=name)
                self.assertEqual(product.illustration_key, key)
                self.assertTrue(product.has_available_image)
                self.assertEqual(product.image_notice, "Ilustração do catálogo aplicada.")
                image_url = reverse("product_image", args=[product.pk])
                self.assertContains(self.client.get(reverse("panel")), image_url)
                response = self.client.get(image_url)
                self.assertEqual(response["Content-Type"], "image/webp")
                self.assertTrue(b"".join(response.streaming_content).startswith(b"RIFF"))

    def test_existing_missing_images_can_be_previewed_and_applied_for_reported_names(self):
        for name, key in [("jogo de talher", "cutlery"), ("toalhas", "towel_set")]:
            with self.subTest(name=name):
                product = Product.objects.create(name=name, created_by=self.manager, submission_key=uuid.uuid4())
                action = reverse("apply_illustration", args=[product.pk])
                self.assertContains(self.client.get(reverse("panel")), f'href="{action}"')
                self.assertEqual(product.image_notice, "Ilustração disponível no catálogo.")
                self.assertContains(self.client.get(action), "Usar esta ilustração")
                product.refresh_from_db()
                self.assertFalse(product.image)
                self.assertEqual(self.client.post(action, {"revision": product.revision}).status_code, 302)
                product.refresh_from_db()
                self.assertEqual(product.illustration_key, key)
                self.assertTrue(product.has_available_image)

    def test_asset_unavailable_does_not_prevent_product_creation(self):
        with patch("gifts.illustrations.service.read_illustration", side_effect=OSError("private path")):
            response = self.create("Faqueiro")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.get(name="Faqueiro").image)
        self.assertNotIn("private path", response.content.decode())

    def test_existing_image_needs_explicit_replacement_and_get_only_previews(self):
        old_name = self.previous_image()
        response = self.client.get(self.action)
        self.assertContains(response, "Usar esta ilustração")
        self.assertEqual(Product.objects.get(pk=self.product.pk).image.name, old_name)
        self.assertEqual(self.client.post(self.action, {"revision": 0}).status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, old_name)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.action, {"revision": self.product.revision, "replace_image": "1"})
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.illustration_key, "cookware_black")
        self.assertNotEqual(self.product.image.name, old_name)
        self.assertFalse((Path(self.directory.name) / old_name).exists())

    def test_reuse_duplicate_and_fresh_request_do_not_create_extra_files(self):
        self.assertEqual(apply_illustration(self.product.pk, 0), "applied")
        self.product.refresh_from_db()
        original_name = self.product.image.name
        self.assertEqual(apply_illustration(self.product.pk, self.product.revision, True), "unchanged")
        with self.assertRaises(ProductConflict):
            apply_illustration(self.product.pk, 0, True)
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, original_name)
        self.assertEqual(len(list(Path(self.directory.name).rglob("*.webp"))), 1)

    def test_changed_name_during_preparation_rejects_old_result_without_orphan(self):
        def rename(candidate):
            data = read_illustration(candidate)
            update_product(self.product.pk, 0, "Liquidificador", ["https://shop.example/new"])
            return data
        with patch("gifts.illustrations.service.read_illustration", side_effect=rename):
            with self.assertRaises(ProductConflict):
                apply_illustration(self.product.pk, 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Liquidificador")
        self.assertFalse(self.product.image)
        self.assertEqual(list(Path(self.directory.name).rglob("*.webp")), [])

    def test_deletion_during_preparation_does_not_recreate_item_or_leave_file(self):
        def remove(candidate):
            data = read_illustration(candidate)
            Product.objects.get(pk=self.product.pk).delete()
            return data
        with patch("gifts.illustrations.service.read_illustration", side_effect=remove):
            with self.assertRaises(ProductConflict):
                apply_illustration(self.product.pk, 0)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        self.assertEqual(list(Path(self.directory.name).rglob("*.webp")), [])

    def test_storage_failure_keeps_old_image_and_does_not_expose_error_details(self):
        old_name = self.previous_image()
        with patch.object(self.product.image.storage, "save", side_effect=OSError("private filesystem detail")):
            response = self.client.post(self.action, {"revision": 0, "replace_image": "1"})
        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, old_name)
        self.assertEqual(self.product.revision, 0)
        self.assertNotContains(response, "private filesystem detail", status_code=400)

    def test_selected_item_can_receive_illustration_without_changing_its_choice(self):
        choice = Selection.objects.create(product=self.product, first_name="Ana", surname="Silva", owner_digest="private")
        self.client.post(self.action, {"revision": 0})
        self.product.refresh_from_db()
        self.assertTrue(self.product.has_available_image)
        self.assertEqual(Selection.objects.get(pk=choice.pk).product, self.product)
        self.assertEqual(self.product.name, "Kit Panelas")

    def test_later_reads_and_edits_preserve_stored_image_without_reprocessing(self):
        apply_illustration(self.product.pk, 0)
        self.product.refresh_from_db()
        original_name = self.product.image.name
        with patch("gifts.illustrations.service.read_illustration", side_effect=AssertionError("No reprocessing")):
            guest = Client()
            guest.post(reverse("identify"), {"first_name": "Ana", "surname": "Silva"})
            self.assertContains(guest.get("/"), "Imagem ilustrativa gerada por IA.")
            response = guest.get(reverse("product_image", args=[self.product.pk]))
            self.assertTrue(b"".join(response.streaming_content).startswith(b"RIFF"))
            update_product(self.product.pk, self.product.revision, "Liquidificador", ["https://other.example/new"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, original_name)
        self.assertIn("O nome mudou", self.product.image_notice)

    def test_permissions_csrf_and_preview_privacy(self):
        preview = reverse("illustration_preview", args=[self.product.pk])
        public = Client()
        for url in (self.action, preview):
            self.assertEqual(public.get(url).status_code, 302)
        reader = get_user_model().objects.create_user("catalog-reader")
        reader.user_permissions.add(Permission.objects.get(codename="view_product"))
        public.force_login(reader)
        for url in (self.action, preview):
            self.assertEqual(public.get(url).status_code, 403)
        self.assertEqual(public.post(self.action, {"revision": 0}).status_code, 403)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.manager)
        self.assertEqual(protected.post(self.action, {"revision": 0}).status_code, 403)
        response = self.client.get(preview)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"RIFF"))

    def test_browser_cannot_choose_a_file_or_provider_endpoint(self):
        self.client.post(self.action, {"revision": 0, "key": "../../.env", "endpoint": "http://127.0.0.1"})
        self.product.refresh_from_db()
        self.assertEqual(self.product.illustration_key, "cookware_black")

    def test_database_failure_after_file_creation_cleans_the_new_file(self):
        with patch.object(Product, "save", side_effect=IntegrityError("Rejected write")):
            with self.assertRaises(IntegrityError):
                apply_illustration(self.product.pk, 0)
        self.product.refresh_from_db()
        self.assertFalse(self.product.image)
        self.assertEqual(list(Path(self.directory.name).rglob("*.webp")), [])
