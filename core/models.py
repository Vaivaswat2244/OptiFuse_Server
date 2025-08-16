import uuid
from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    class SubscriptionTier(models.TextChoices):
        FREE = 'FREE', 'Free'
        PRO = 'PRO', 'Pro'
        ENTERPRISE = 'ENTERPRISE', 'Enterprise'
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    github_access_token = models.CharField(max_length=255, blank=True)
    aws_role_arn = models.CharField(max_length=255, blank=True, null=True)
    aws_external_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    subscription = models.CharField(
        max_length=10,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.FREE
    )

    def __str__(self):
        return f"{self.user.username} - {self.get_subscription_display()}"