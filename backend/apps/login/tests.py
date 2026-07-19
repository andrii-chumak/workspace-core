from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class LoginViewTests(TestCase):
    def setUp(self):
        self.username = "testuser"
        self.email = "testuser@example.com"
        self.password = "SecretPassword123"

        self.user = User.objects.create_user(username=self.username, email=self.email, password=self.password)

        self.login_url = reverse('login')

    def test_login_success_with_username(self):
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password
        })

        self.assertEqual(response.status_code, 302)

        self.assertIn('_auth_user_id', self.client.session)

    def test_login_success_with_email(self):
        response = self.client.post(self.login_url, {
            'username': self.email,
            'password': self.password
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_failed_with_wrong_credentials(self):
        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': 'WrongPassword'
        })

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(response.context['form'].errors)

    def test_login_success_case_insensitive_email(self):
        mixed_case_email = self.email.upper()

        response = self.client.post(self.login_url, {
            'username': mixed_case_email,
            'password': self.password
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_failed_blank_fields(self):
        response = self.client.post(self.login_url, {
            'username': '',
            'password': ''
        })

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

        form = response.context['form']
        self.assertIn('username', form.errors)
        self.assertIn('password', form.errors)

    def test_login_failed_inactive_user(self):
        self.user.is_active = False
        self.user.save()

        response = self.client.post(self.login_url, {
            'username': self.username,
            'password': self.password
        })

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)