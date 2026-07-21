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
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(response.json()['user']['username'], self.username)

    def test_login_success_with_email(self):
        response = self.client.post(self.login_url, {
            'username': self.email,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_failed_with_wrong_credentials(self):
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': 'WrongPassword'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('_auth_user_id', self.client.session)

        self.assertIn('non_field_errors', response.json())

    def test_login_success_case_insensitive_email(self):
        mixed_case_email = self.email.upper()

        response = self.client.post(self.login_url, {
            'username': mixed_case_email,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_failed_blank_fields(self):
        response = self.client.post(self.login_url, {
            'username': '',
            'password': ''
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('_auth_user_id', self.client.session)

        errors = response.json()
        self.assertIn('username', errors)
        self.assertIn('password', errors)

    def test_login_failed_inactive_user(self):
        self.user.is_active = False
        self.user.save()

        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('_auth_user_id', self.client.session)