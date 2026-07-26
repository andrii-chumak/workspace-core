from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.test import APITestCase
from rest_framework import status

from .services import generate_password_change_token

User = get_user_model()


class ProfileModuleTestCase(APITestCase):
    def setUp(self):
        self.user_password = "StrongPassword123!"
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password=self.user_password,
            first_name="Test",
            last_name="User"
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="otheruser@example.com",
            password="OtherPassword123!"
        )

        self.profile_url = reverse("user_profile")
        self.request_password_url = reverse("request_password_change")
        self.confirm_password_url = reverse("confirm_password_change")


    def test_get_profile_unauthorized(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_profile_success(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], self.user.username)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["first_name"], self.user.first_name)

    def test_update_profile_success(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "first_name": "UpdatedName",
            "last_name": "UpdatedLastName"
        }
        response = self.client.patch(self.profile_url, payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "UpdatedName")
        self.assertEqual(self.user.last_name, "UpdatedLastName")

    def test_update_username_conflict(self):
        self.client.force_authenticate(user=self.user)
        payload = {"username": "otheruser"}
        response = self.client.patch(self.profile_url, payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_update_same_username_success(self):
        self.client.force_authenticate(user=self.user)
        payload = {"username": "testuser", "first_name": "NewName"}
        response = self.client.patch(self.profile_url, payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_email_is_read_only(self):
        self.client.force_authenticate(user=self.user)
        payload = {"email": "hacked_email@example.com"}
        response = self.client.patch(self.profile_url, payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "testuser@example.com")

    def test_request_password_change_sends_email(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.request_password_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Request to Change Password", mail.outbox[0].subject)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_confirm_password_change_success(self):
        self.client.force_authenticate(user=self.user)
        token = generate_password_change_token(self.user.id)
        new_password = "NewStrongPassword123!"

        payload = {
            "token": token,
            "new_password": new_password
        }
        response = self.client.post(self.confirm_password_url, payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password(self.user_password))
        self.assertTrue(self.user.check_password(new_password))

    def test_confirm_password_change_invalid_token(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "token": "fake_invalid_token_123",
            "new_password": "NewStrongPassword123!"
        }
        response = self.client.post(self.confirm_password_url, payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_password_change_foreign_token(self):
        self.client.force_authenticate(user=self.user)
        foreign_token = generate_password_change_token(self.other_user.id)

        payload = {
            "token": foreign_token,
            "new_password": "NewStrongPassword123!"
        }
        response = self.client.post(self.confirm_password_url, payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)