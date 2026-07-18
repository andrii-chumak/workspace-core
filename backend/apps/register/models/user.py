from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    email = models.EmailField(unique=True)
    avatar_url = models.URLField(default="", blank=True)
    # решта полів - вбудовані у AbstractUser

    class Meta:
        db_table = "User"


