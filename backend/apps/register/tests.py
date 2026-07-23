from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch
from .models import SocialAccount
from .services import generate_email_verification_token, verify_google_token, generate_unique_username
from django.db import IntegrityError
from .serializers import RegisterSerializer
from rest_framework import serializers

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


class RegisterSerializerTests(APITestCase):

    @patch("apps.register.serializers.User.objects.create_user")
    def test_register_integrity_error(
        self,
        mock_create,
    ):
        email = "test@test.com"

        token = generate_email_verification_token(
            email
        )

        serializer = RegisterSerializer(
            data={
                "username": "john",
                "password": "Password123!",
                "verification_token": token,
            }
        )

        self.assertTrue(
            serializer.is_valid()
        )

        mock_create.side_effect = IntegrityError()

        with self.assertRaises(serializers.ValidationError):
            serializer.save()



    def test_serializer_duplicate_username(self):

        User.objects.create_user(
            username="john",
            email="other@test.com",
            password="Password123!",
        )

        token = generate_email_verification_token(
            "new@test.com"
        )

        serializer = RegisterSerializer(
            data={
                "username": "john",
                "password": "Password123!",
                "verification_token": token,
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "username",
            serializer.errors,
        )


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


class GoogleRegisterViewTests(APITestCase):

    def setUp(self):
        self.url = reverse("google-register")

        self.payload = {
            "sub": "google-user-123",
            "email": "google@example.com",
            "email_verified": True,
            "given_name": "John",
            "family_name": "Doe",
            "picture": "https://example.com/avatar.png",
        }

    @patch("apps.register.views.send_welcome_email")
    @patch("apps.register.serializers.verify_google_token")
    def test_google_register_new_user(
            self,
            mock_verify,
            mock_send_email,
    ):
        mock_verify.return_value = self.payload

        response = self.client.post(
            self.url,
            {"google_token": "valid-token"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["action"],
            "registered",
        )

        self.assertTrue(
            User.objects.filter(
                email=self.payload["email"]
            ).exists()
        )

        mock_send_email.assert_called_once()

    @patch("apps.register.serializers.verify_google_token")
    def test_google_password_is_unusable(
            self,
            mock_verify,
    ):
        mock_verify.return_value = self.payload

        self.client.post(
            self.url,
            {"google_token": "token"},
        )

        user = User.objects.get(email=self.payload["email"])

        self.assertFalse(
            user.has_usable_password()
        )

    @patch("apps.register.serializers.verify_google_token")
    def test_google_avatar_saved(
            self,
            mock_verify,
    ):
        mock_verify.return_value = self.payload

        self.client.post(
            self.url,
            {"google_token": "token"},
        )

        user = User.objects.get(email=self.payload["email"])

        self.assertEqual(
            user.avatar_url,
            self.payload["picture"],
        )

    @patch("apps.register.views.send_welcome_email")
    @patch("apps.register.serializers.verify_google_token")
    def test_google_account_already_linked(
            self,
            mock_verify,
            mock_send_email,
    ):
        user = User.objects.create_user(
            username="john",
            email=self.payload["email"],
        )

        SocialAccount.objects.create(
            user=user,
            provider=SocialAccount.Provider.GOOGLE,
            provider_user_id=self.payload["sub"],
        )

        mock_verify.return_value = self.payload

        response = self.client.post(
            self.url,
            {"google_token": "token"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["action"],
            "login_required",
        )

        mock_send_email.assert_not_called()

    @patch("apps.register.views.send_welcome_email")
    @patch("apps.register.serializers.verify_google_token")
    def test_link_google_to_existing_user(
            self,
            mock_verify,
            mock_send_email,
    ):
        user = User.objects.create_user(
            username="john",
            email=self.payload["email"],
            password="Password123!",
        )

        mock_verify.return_value = self.payload

        response = self.client.post(
            self.url,
            {"google_token": "token"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["action"],
            "linked",
        )

        self.assertTrue(
            SocialAccount.objects.filter(
                user=user,
                provider=SocialAccount.Provider.GOOGLE,
            ).exists()
        )

        mock_send_email.assert_not_called()

    @patch("apps.register.serializers.verify_google_token")
    def test_invalid_google_token(
            self,
            mock_verify,
    ):
        mock_verify.return_value = None

        response = self.client.post(
            self.url,
            {"google_token": "invalid"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @patch("apps.register.services.id_token.verify_oauth2_token")
    def test_verify_google_token_unverified_email(
            self,
            mock_verify,
    ):
        mock_verify.return_value = {
            "sub": "123",
            "email": "test@test.com",
            "email_verified": False,
        }

        result = verify_google_token("token")

        self.assertIsNone(result)

    @patch("apps.register.serializers.verify_google_token")
    def test_google_returns_access_token(
            self,
            mock_verify,
    ):
        mock_verify.return_value = self.payload

        response = self.client.post(
            self.url,
            {"google_token": "token"},
        )

        self.assertIn(
            "access",
            response.data,
        )

    @patch("apps.register.serializers.verify_google_token")
    def test_google_returns_refresh_token(
            self,
            mock_verify,
    ):
        mock_verify.return_value = self.payload

        response = self.client.post(
            self.url,
            {"google_token": "token"},
        )

        self.assertIn(
            "refresh",
            response.data,
        )

    @patch("apps.register.serializers.verify_google_token")
    def test_google_generates_username(
            self,
            mock_verify,
    ):
        mock_verify.return_value = self.payload

        self.client.post(
            self.url,
            {"google_token": "token"},
        )

        user = User.objects.get(email=self.payload["email"])

        self.assertTrue(user.username)

    @patch("apps.register.serializers.verify_google_token")
    def test_google_returns_user_data(
            self,
            mock_verify,
    ):
        mock_verify.return_value = self.payload

        response = self.client.post(
            self.url,
            {"google_token": "token"},
        )

        self.assertEqual(
            response.data["user"]["email"],
            self.payload["email"],
        )

        self.assertEqual(
            response.data["user"]["first_name"],
            self.payload["given_name"],
        )

        self.assertEqual(
            response.data["user"]["last_name"],
            self.payload["family_name"],
        )

    @patch("apps.register.serializers.SocialAccount.objects.create")
    @patch("apps.register.serializers.verify_google_token")
    def test_google_social_account_race_condition(
            self,
            mock_verify,
            mock_create,
    ):
        mock_verify.return_value = self.payload
        mock_create.side_effect = IntegrityError()

        response = self.client.post(
            self.url,
            {"google_token": "token"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            User.objects.filter(
                email=self.payload["email"],
            ).exists()
        )
        
class UsernameGenerationTests(APITestCase):

    def test_generate_unique_username_with_duplicates(self):
        User.objects.create_user(
            username="john",
            email="john1@test.com",
        )

        User.objects.create_user(
            username="john1",
            email="john2@test.com",
        )

        username = generate_unique_username(
            "john@gmail.com"
        )

        self.assertEqual(
            username,
            "john2",
        )


class GoogleTokenServiceTests(APITestCase):

    @patch("apps.register.services.id_token.verify_oauth2_token")
    def test_verify_google_token_invalid(
        self,
        mock_verify,
    ):
        mock_verify.side_effect = ValueError()

        result = verify_google_token(
            "invalid-token"
        )

        self.assertIsNone(result)


