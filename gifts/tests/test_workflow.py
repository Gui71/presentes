import tempfile
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model, SESSION_KEY
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from gifts.models import Product, ProductLink


class WorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user("manager", password="a-strong-test-password")
        cls.manager.user_permissions.add(*Permission.objects.filter(codename__in=["add_product", "view_product"], content_type__app_label="gifts"))
        cls.staff = get_user_model().objects.create_user("staff", password="a-strong-test-password", is_staff=True)
        cls.product = Product.objects.create(name="Cafeteira especial", created_by=cls.manager, submission_key=uuid.uuid4())
        ProductLink.objects.create(product=cls.product, url="https://www.magazineluiza.com.br/cafeteira", position=0)

    def identify(self, client=None):
        return (client or self.client).post(reverse("identify"), {"first_name": "João", "surname": "D'Ávila"})

    def test_identification_does_not_load_or_expose_catalog(self):
        with self.assertNumQueries(0):
            response = self.client.get(reverse("catalog"))
        self.assertNotContains(response, self.product.name)
        self.assertNotContains(response, "magazineluiza.com.br/cafeteira")
        self.assertContains(response, "Primeiro sobrenome")
        self.assertEqual(response.context["products"], [])
        self.assertTrue(response["Cache-Control"].find("no-store") >= 0)

    def test_identification_validates_and_survives_refresh_without_publishing_name(self):
        response = self.client.post(reverse("identify"), {"first_name": " ", "surname": ""})
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, self.product.name, status_code=400)
        self.assertRedirects(self.identify(), reverse("catalog"))
        for _ in range(2):
            response = self.client.get(reverse("catalog"))
            self.assertContains(response, self.product.name)
            self.assertNotContains(response, "id=\"visitor-modal\"")
            self.assertNotContains(response, "D&#x27;Ávila")

    def test_visitor_name_and_staff_flag_never_grant_management(self):
        self.identify()
        self.assertEqual(self.client.get(reverse("panel")).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("panel")).status_code, 403)
        self.assertEqual(self.client.post(reverse("create_product"), {}).status_code, 403)

    def test_manager_can_use_panel_without_staff_or_admin_access(self):
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(reverse("panel")), "Adicionar novo item")
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.assertEqual(self.client.get(reverse("panel"))["Cache-Control"].find("no-store") >= 0, True)

    def test_inactive_manager_is_denied(self):
        self.client.force_login(self.manager)
        self.manager.is_active = False
        self.manager.save()
        self.assertEqual(self.client.get(reverse("panel")).status_code, 302)

    def test_login_and_logout_are_browser_sessions_and_post_only(self):
        response = self.client.post(reverse("login"), {"username": "manager", "password": "a-strong-test-password", "next": "https://evil.example/"})
        self.assertRedirects(response, reverse("panel"))
        cookie = self.client.cookies["sessionid"]
        self.assertEqual(cookie["max-age"], "")
        self.assertEqual(cookie["expires"], "")
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        old_session = self.client.session.session_key
        self.assertEqual(self.client.post(reverse("logout")).status_code, 302)
        from django.contrib.sessions.models import Session
        self.assertFalse(Session.objects.filter(session_key=old_session).exists())

    def test_restored_cookie_is_still_a_valid_session(self):
        self.client.force_login(self.manager)
        restored = Client()
        restored.cookies["sessionid"] = self.client.cookies["sessionid"].value
        self.assertContains(restored.get(reverse("panel")), "Adicionar novo item")

    def test_unprivileged_login_rejected(self):
        response = self.client.post(reverse("login"), {"username": "staff", "password": "a-strong-test-password"})
        self.assertContains(response, "não tem acesso ao painel")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_admin_login_also_uses_browser_cookie(self):
        admin = get_user_model().objects.create_superuser("root", password="another-strong-test-password")
        response = self.client.post("/admin/login/?next=/admin/", {"username": admin.username, "password": "another-strong-test-password", "next": "/admin/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.cookies["sessionid"]["max-age"], "")
        self.assertEqual(self.client.cookies["sessionid"]["expires"], "")
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_real_csrf_on_identification_product_creation_and_logout(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("identify"), {"first_name": "João", "surname": "Silva"}).status_code, 403)
        client.get(reverse("catalog"))
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(reverse("identify"), {"first_name": "João", "surname": "Silva", "csrfmiddlewaretoken": token}).status_code, 302)
        client.force_login(self.manager)
        self.assertEqual(client.post(reverse("create_product"), {}).status_code, 403)
        self.assertEqual(client.post(reverse("logout"), {}).status_code, 403)
        client.get(reverse("panel"))
        self.assertEqual(client.post(reverse("logout"), {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}).status_code, 302)

    def test_real_csrf_on_both_logins(self):
        root = get_user_model().objects.create_superuser("csrf-root", password="a-strong-test-password")
        for path, username in ((reverse("login"), "manager"), ("/admin/login/", root.username)):
            with self.subTest(path=path):
                client = Client(enforce_csrf_checks=True)
                data = {"username": username, "password": "a-strong-test-password"}
                self.assertEqual(client.post(path, data).status_code, 403)
                client.get(path)
                data["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
                self.assertEqual(client.post(path, data).status_code, 302)
                self.assertIn(SESSION_KEY, client.session)

    def test_image_endpoint_requires_identification_or_management(self):
        response = self.client.get(reverse("product_image", args=[self.product.pk]))
        self.assertEqual(response.status_code, 404)

    def product_data(self):
        self.client.force_login(self.manager)
        page = self.client.get(reverse("panel"))
        return {"name": "Panela", "submission_key": page.context["submission_key"],
                "links-TOTAL_FORMS": "2", "links-INITIAL_FORMS": "0", "links-MIN_NUM_FORMS": "1", "links-MAX_NUM_FORMS": "10",
                "links-0-url": "https://www.mercadolivre.com.br/panela", "links-1-url": "https://www.magazineluiza.com.br/panela"}

    @patch("gifts.external.obtain_product_image")
    def test_multiple_links_preserve_order_and_duplicate_submission_is_idempotent(self, obtain):
        data = self.product_data()
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            for _ in range(2):
                self.assertRedirects(self.client.post(reverse("create_product"), data), reverse("panel"))
            product = Product.objects.get(name="Panela")
            self.assertEqual(list(product.links.values_list("url", flat=True)), [data["links-0-url"], data["links-1-url"]])
            obtain.assert_not_called()
            self.assertEqual(Product.objects.filter(name="Panela").count(), 1)
            self.assertTrue(product.has_available_image)
            self.assertEqual(product.illustration_key, "cookware_black")

    @patch("gifts.external.obtain_product_image")
    def test_invalid_and_forged_product_forms_never_extract(self, obtain):
        data = self.product_data()
        data["links-0-url"] = "http://127.0.0.1/private"
        self.assertEqual(self.client.post(reverse("create_product"), data).status_code, 400)
        data["submission_key"] = str(uuid.uuid4())
        self.assertEqual(self.client.post(reverse("create_product"), data).status_code, 400)
        obtain.assert_not_called()

    def test_reencoded_photo_is_stored_and_delivered_only_after_identification(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            data = self.product_data()
            data["name"] = "Kit Panelas"
            self.assertEqual(self.client.post(reverse("create_product"), data).status_code, 302)
            product = Product.objects.get(name="Kit Panelas")
            self.assertTrue(product.image.storage.exists(product.image.name))
            guest = Client()
            url = reverse("product_image", args=[product.pk])
            self.assertEqual(guest.get(url).status_code, 404)
            self.identify(guest)
            response = guest.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/webp")
            self.assertTrue(b"".join(response.streaming_content).startswith(b"RIFF"))
            self.assertEqual(guest.get("/media/" + product.image.name).status_code, 404)

    def test_product_name_is_escaped_in_html_and_dialog_data(self):
        self.product.name = '<script>alert("x")</script>'
        self.product.save()
        self.identify()
        response = self.client.get(reverse("catalog"))
        self.assertNotContains(response, self.product.name)
        self.assertContains(response, "&lt;script&gt;")


class LoginThrottleTests(TestCase):
    def test_both_logins_share_database_throttle_and_ignore_forwarded_ip(self):
        from axes.models import AccessAttempt
        for index in range(5):
            path = reverse("login") if index % 2 else "/admin/login/"
            self.client.post(path, {"username": "unknown", "password": "incorrect"}, HTTP_X_FORWARDED_FOR=f"8.8.8.{index}")
        self.assertEqual(AccessAttempt.objects.count(), 1)
        self.assertEqual(AccessAttempt.objects.get().ip_address, "127.0.0.1")
        response = self.client.post(reverse("login"), {"username": "unknown", "password": "incorrect"})
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Tente novamente mais tarde", status_code=429)
