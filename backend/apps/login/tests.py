from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class LoginAPIViewTests(APITestCase):

    def setUp(self):
        self.username = "testuser"
        self.email = "testuser@example.com"
        self.password = "SecretPassword123"

        self.user = User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password
        )

        self.login_url = reverse('api_login')


    def test_login_success_with_username(self):
        response = self.client.post(
            self.login_url,
            {
                "username": self.username,
                "password": self.password
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        data = response.json()

        self.assertIn("access", data)
        self.assertIn("refresh", data)

        self.assertEqual(
            data["user"]["username"],
            self.username
        )


    def test_login_success_with_email(self):
        response = self.client.post(
            self.login_url,
            {
                "username": self.email,
                "password": self.password
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        data = response.json()

        self.assertIn("access", data)
        self.assertIn("refresh", data)


    def test_login_success_case_insensitive_email(self):
        mixed_case_email = self.email.upper()

        response = self.client.post(
            self.login_url,
            {
                "username": mixed_case_email,
                "password": self.password
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        data = response.json()

        self.assertIn("access", data)
        self.assertIn("refresh", data)


    def test_login_failed_with_wrong_credentials(self):
        response = self.client.post(
            self.login_url,
            {
                "username": self.username,
                "password": "WrongPassword"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

        data = response.json()

        self.assertIn(
            "detail",
            data
        )


    def test_login_failed_blank_fields(self):
        response = self.client.post(
            self.login_url,
            {
                "username": "",
                "password": ""
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        data = response.json()

        self.assertIn(
            "username",
            data
        )

        self.assertIn(
            "password",
            data
        )


    def test_login_failed_inactive_user(self):
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            self.login_url,
            {
                "username": self.username,
                "password": self.password
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )