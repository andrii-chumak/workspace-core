from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class SocialAccount(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="social_accounts",)
    provider = models.CharField(max_length=20, choices=Provider)
    provider_user_id = models.CharField(max_length=225)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_accounts"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_user_id"],
                name="unique_provider_account",
            )
        ]
