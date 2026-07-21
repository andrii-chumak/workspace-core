from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from .services import generate_email_verification_token

User = get_user_model()

class RegisterViewTests(APITestCase):

    def setUp(self):
        self.url = reverse("register")

        self.email = "test@example.com"
        self.token = generate_email_verification_token(self.email)

        self.payload = {
            "username": "testuser",
            "password": "SecretPassword123!",
            "first_name": "Denys",
            "last_name": "Zastavnyi",
            "verification_token": self.token,
        }

    def test_register_success(self):
        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertTrue(
            User.objects.filter(email=self.email).exists()
        )


    def test_password_is_hashed(self):
        self.client.post(self.url, self.payload)

        user = User.objects.get(email=self.email)

        self.assertNotEqual(
            user.password,
            "SecretPassword123!"
        )

        self.assertTrue(user.check_password("SecretPassword123!"))

    def test_password_not_in_response(self):
        response = self.client.post(self.url, self.payload)

        self.assertNotIn("password", response.data)

    def test_register_duplicate_email(self):
        User.objects.create_user(
            username="existing",
            email=self.email,
            password="Password123!"
        )

        response = self.client.post(self.url, self.payload)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "email",
            response.data
        )

    def test_register_duplicate_username(self):
        User.objects.create_user(
            username="testuser",
            email="another@example.com",
            password="Password123!"
        )

        response = self.client.post(self.url, self.payload)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "username",
            response.data
        )

    def test_register_weak_password(self):
        payload = self.payload.copy()

        payload["password"] = "12345678"

        response = self.client.post(self.url, payload)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "password",
            response.data
        )

    def test_register_required_fields(self):
        response = self.client.post(self.url, {})

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("username", response.data)
        self.assertIn("password", response.data)
        self.assertIn("verification_token", response.data)

    def test_register_without_token(self):
        payload = self.payload.copy()

        payload.pop("verification_token")

        response = self.client.post(self.url, payload)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "verification_token",
            response.data
        )

    def test_register_invalid_token(self):
        payload = self.payload.copy()

        payload["verification_token"] = "invalid-token"

        response = self.client.post(self.url, payload)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            "verification_token",
            response.data
        )

    def test_same_token_cannot_register_twice(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        payload = self.payload.copy()
        payload["username"] = "second_user"

        response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)
        self.assertIn("email", response.data)



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

    @patch("apps.register.views.send_verification_email")
    def test_email_sent_for_available_email(self, mock_send_email):
        response = self.client.get(
            self.check_email_url,
            {"email": "free@example.com"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        mock_send_email.assert_called_once()

    @patch("apps.register.views.send_verification_email")
    def test_email_not_sent_for_taken_email(self, mock_send_email):
        response = self.client.get(
            self.check_email_url,
            {"email": "taken@example.com"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        mock_send_email.assert_not_called()

    @patch("apps.register.views.send_verification_email")
    def test_email_sent_with_correct_email(self, mock_send_email):
        email = "free@example.com"

        self.client.get(
            self.check_email_url,
            {"email": email},
        )

        args, kwargs = mock_send_email.call_args

        self.assertEqual(args[0], email)

class VerifyEmailViewTests(APITestCase):

    def setUp(self):
        self.url = reverse("verify-email")

        self.email = "test@example.com"

        self.token = generate_email_verification_token(
            self.email
        )

    def test_verify_success(self):
        response = self.client.get(
            self.url,
            {"token": self.token}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertTrue(response.data["verified"])

    def test_verify_invalid_token(self):
        response = self.client.get(
            self.url,
            {"token": "invalid-token"}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            response.data["detail"],
            "invalid or expired token"
        )

    def test_verify_without_token(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            response.data["detail"],
            "Token is required."
        )

    @patch("apps.register.views.verify_email_verification_token")
    def test_verify_expired_token(self, mock_verify):
        mock_verify.return_value = None

        response = self.client.get(
            self.url,
            {"token": self.token}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            response.data["detail"],
            "invalid or expired token"
        )

    def test_verify_returns_correct_email(self):
        response = self.client.get(
            self.url,
            {"token": self.token}
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["email"],
            self.email
        )