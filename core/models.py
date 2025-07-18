from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    github_access_token = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.user.username