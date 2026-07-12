from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class AdminAccessTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_non_admin_denied_from_admin_user_list(self):
        # Un utente autenticato ma non superuser deve ricevere 403
        # (SuperuserRequiredMixin con raise_exception=True).
        User.objects.create_user(username="pinco", password="password123")
        self.client.login(username="pinco", password="password123")
        response = self.client.get(reverse("accounts:admin_user_list"))
        self.assertEqual(response.status_code, 403)

    def test_admin_allowed_on_admin_user_list(self):
        User.objects.create_user(
            username="capo", password="password123", is_superuser=True
        )
        self.client.login(username="capo", password="password123")
        response = self.client.get(reverse("accounts:admin_user_list"))
        self.assertEqual(response.status_code, 200)
