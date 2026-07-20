from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


class RegisterViewTests(APITestCase):
    def setUp(self):
        self.register_url = reverse("register")
        self.valid_payload = {
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "SecretPassword123",
            "first_name": "Денис",
            "last_name": "Заставний",
        }

    def test_register_success(self):
        response = self.client.post(self.register_url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="testuser@example.com").exists())

    def test_register_password_is_hashed(self):
        self.client.post(self.register_url, self.valid_payload)
        user = User.objects.get(email="testuser@example.com")
        self.assertNotEqual(user.password, self.valid_payload["password"])
        self.assertTrue(user.password.startswith("argon2"))

    def test_register_password_not_in_response(self):
        response = self.client.post(self.register_url, self.valid_payload)
        self.assertNotIn("password", response.data)

    def test_register_failed_duplicate_email(self):
        User.objects.create_user(username="existing", email="testuser@example.com", password="SomePass123")
        response = self.client.post(self.register_url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_failed_weak_password(self):
        payload = {**self.valid_payload, "password": "12345678"}
        response = self.client.post(self.register_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_register_failed_blank_fields(self):
        response = self.client.post(self.register_url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertIn("email", response.data)
        self.assertIn("password", response.data)


class CheckEmailViewTests(APITestCase):
    def setUp(self):
        self.check_email_url = reverse("check-email")
        User.objects.create_user(username="taken", email="taken@example.com", password="SomePass123")

    def test_email_is_taken(self):
        response = self.client.get(self.check_email_url, {"email": "taken@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["available"])

    def test_email_is_available(self):
        response = self.client.get(self.check_email_url, {"email": "free@example.com"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["available"])

    def test_email_case_insensitive(self):
        response = self.client.get(self.check_email_url, {"email": "TAKEN@EXAMPLE.COM"})
        self.assertFalse(response.data["available"])

    def test_email_missing_parameter(self):
        response = self.client.get(self.check_email_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)