from concurrent.futures import ThreadPoolExecutor
import threading
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from gifts.models import Product, Selection


class SelectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user("manager")
        cls.manager.user_permissions.add(*Permission.objects.filter(codename__in=["add_product", "view_product"], content_type__app_label="gifts"))
        cls.first = Product.objects.create(name="Cafeteira", created_by=cls.manager, submission_key=uuid.uuid4())
        cls.second = Product.objects.create(name="Panela", created_by=cls.manager, submission_key=uuid.uuid4())

    def identify(self, client):
        client.post(reverse("identify"), {"first_name": "João", "surname": "Silva"})

    def test_unidentified_cannot_confirm_and_get_does_not_select(self):
        url = reverse("choose_product", args=[self.first.pk])
        self.assertRedirects(self.client.post(url), reverse("catalog"))
        self.identify(self.client)
        self.assertContains(self.client.get(url), "Confirmar sua escolha?")
        self.assertFalse(Selection.objects.exists())

    def test_multiple_choices_exclusive_and_selected_items_move_to_end(self):
        other = Client()
        self.identify(self.client)
        self.identify(other)
        self.client.post(reverse("choose_product", args=[self.second.pk]))
        products = list(self.client.get(reverse("catalog")).context["products"])
        self.assertEqual(products[-1].pk, self.second.pk)
        self.assertTrue(products[-1].is_selected)
        self.assertTrue(products[-1].is_mine)
        other.post(reverse("choose_product", args=[self.second.pk]))
        self.assertEqual(Selection.objects.count(), 1)
        self.client.post(reverse("choose_product", args=[self.first.pk]))
        self.assertEqual(Selection.objects.count(), 2)
        page = other.get(reverse("catalog"))
        self.assertNotContains(page, "João")
        self.assertNotContains(page, "Silva")
        self.assertContains(page, "Já selecionado", count=2)

    def test_only_authorized_managers_see_names_and_can_cancel(self):
        self.identify(self.client)
        self.client.post(reverse("choose_product", args=[self.first.pk]))
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(reverse("panel")), "João Silva")
        cancel = reverse("cancel_selection_manager", args=[self.first.pk])
        self.assertEqual(self.client.post(cancel).status_code, 403)
        self.manager.user_permissions.add(Permission.objects.get(codename="delete_selection"))
        self.assertRedirects(self.client.post(cancel), reverse("panel"))
        self.assertFalse(Selection.objects.exists())

    def test_csrf_prevents_choice_and_manager_cancellation(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("catalog"))
        client.post(reverse("identify"), {"first_name": "João", "surname": "Silva", "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        url = reverse("choose_product", args=[self.first.pk])
        self.assertEqual(client.post(url).status_code, 403)
        self.assertFalse(Selection.objects.exists())
        self.assertEqual(client.post(url, {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}).status_code, 302)
        client.force_login(self.manager)
        self.assertEqual(client.post(reverse("cancel_selection_manager", args=[self.first.pk])).status_code, 403)

    def test_visitor_cancels_one_choice_keeps_others_and_can_choose_again(self):
        self.identify(self.client)
        for product in (self.first, self.second):
            self.client.post(reverse("choose_product", args=[product.pk]))
        cancel = reverse("cancel_selection_visitor", args=[self.first.pk])
        self.assertEqual(self.client.get(cancel).status_code, 405)
        self.assertRedirects(self.client.post(cancel), reverse("catalog"))
        self.assertFalse(Selection.objects.filter(product=self.first).exists())
        self.assertTrue(Selection.objects.filter(product=self.second).exists())
        self.client.post(reverse("choose_product", args=[self.first.pk]))
        self.assertEqual(Selection.objects.count(), 2)

    def test_same_name_in_another_session_cannot_cancel_or_see_cancel_button(self):
        self.identify(self.client)
        self.client.post(reverse("choose_product", args=[self.first.pk]))
        owner_page = self.client.get(reverse("catalog"))
        self.assertContains(owner_page, "Cancelar minha escolha")
        other = Client()
        self.identify(other)  # Mesmo nome e sobrenome, capacidade diferente.
        self.assertNotContains(other.get(reverse("catalog")), "Cancelar minha escolha")
        cancel = reverse("cancel_selection_visitor", args=[self.first.pk])
        self.assertEqual(other.post(cancel).status_code, 404)
        self.assertTrue(Selection.objects.filter(product=self.first).exists())

    def test_lost_session_cannot_cancel_and_choice_remains_persistent(self):
        self.identify(self.client)
        self.client.post(reverse("choose_product", args=[self.first.pk]))
        self.client.cookies.clear()
        cancel = reverse("cancel_selection_visitor", args=[self.first.pk])
        self.assertRedirects(self.client.post(cancel), reverse("catalog"))
        self.assertTrue(Selection.objects.filter(product=self.first).exists())
        self.identify(self.client)
        self.assertEqual(self.client.post(cancel).status_code, 404)

    def test_restored_browser_cookie_retains_visitor_cancellation_as_documented(self):
        self.identify(self.client)
        self.client.post(reverse("choose_product", args=[self.first.pk]))
        cookie = self.client.cookies["sessionid"]
        self.assertEqual(cookie["max-age"], "")
        self.assertEqual(cookie["expires"], "")
        restored = Client()
        restored.cookies["sessionid"] = cookie.value
        self.assertRedirects(restored.post(reverse("cancel_selection_visitor", args=[self.first.pk])), reverse("catalog"))
        self.assertFalse(Selection.objects.exists())

    def test_visitor_cancellation_requires_real_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("catalog"))
        token = client.cookies["csrftoken"].value
        client.post(reverse("identify"), {"first_name": "João", "surname": "Silva", "csrfmiddlewaretoken": token})
        client.post(reverse("choose_product", args=[self.first.pk]), {"csrfmiddlewaretoken": token})
        cancel = reverse("cancel_selection_visitor", args=[self.first.pk])
        self.assertEqual(client.post(cancel).status_code, 403)
        self.assertTrue(Selection.objects.exists())
        self.assertEqual(client.post(cancel, {"csrfmiddlewaretoken": token}).status_code, 302)
        self.assertFalse(Selection.objects.exists())


class ConcurrentSelectionTests(TransactionTestCase):
    def test_two_simultaneous_confirmations_have_exactly_one_winner(self):
        manager = get_user_model().objects.create_user("manager")
        product = Product.objects.create(name="Cafeteira", created_by=manager, submission_key=uuid.uuid4())
        clients = [Client(), Client()]
        for client, name in zip(clients, ["Ana", "Bruno"]):
            client.post(reverse("identify"), {"first_name": name, "surname": "Silva"})
        barrier = threading.Barrier(2)

        def confirm(client):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return client.post(reverse("choose_product", args=[product.pk])).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(confirm, clients)), [302, 302])
        self.assertEqual(Selection.objects.filter(product=product).count(), 1)
        self.assertIn(Selection.objects.get().first_name, {"Ana", "Bruno"})
