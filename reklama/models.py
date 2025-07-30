from django.db import models
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from botapp.models import BotUser



# === Advertisements ===


class AdPostTg(models.Model):
    message_id = models.CharField(max_length=255, unique=True, help_text="Telegram message ID for the advertisement")

    user: "BotUser" = models.ForeignKey("botapp.BotUser", on_delete=models.SET_NULL, related_name='ad_posts', blank=True, null=True, help_text="User who created the advertisement")

    created_at = models.DateTimeField(auto_now_add=True, help_text="When the advertisement was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When the advertisement was last updated")

    def __str__(self):
        return f"AdPost {self.message_id} by {self.user.full_name if self.user else 'Unknown'}"
    
    class Meta:
        verbose_name = "Advertisement Post"
        verbose_name_plural = "Advertisement Posts"
        ordering = ['-created_at']



class AdPostButton(models.Model):
    title = models.CharField(max_length=255, help_text="Button title")
    url = models.URLField(blank=True, null=True, help_text="URL to open when the button is clicked")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the button was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When the button was last updated")
    is_active = models.BooleanField(default=True, help_text="Is the button currently active?")


class Advertisement(models.Model):
    post = models.ForeignKey(AdPostTg, on_delete=models.CASCADE, related_name='advertisements', help_text="Telegram post associated with the advertisement")

    user: "BotUser" = models.ForeignKey("botapp.BotUser", on_delete=models.SET_NULL, related_name='advertisements', blank=True, null=True, help_text="User who created the advertisement")

    class AdvertisementStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'
    
    status = models.CharField(max_length=20, choices=AdvertisementStatus.choices, default=AdvertisementStatus.DRAFT, help_text="Current status of the advertisement")

    scheduled_time = models.DateTimeField(blank=True, null=True, help_text="When the advertisement is scheduled to be sent")
    sent_time = models.DateTimeField(blank=True, null=True, help_text="When the advertisement was sent")

    count = models.PositiveIntegerField(default=0, help_text="Number of times the advertisement has been sent")

    buttons: "AdPostButton" = models.ManyToManyField(AdPostButton, blank=True, related_name='advertisements', help_text="Buttons associated with the advertisement")

    target_users: "BotUser" = models.ManyToManyField("botapp.BotUser", blank=True, related_name="targeted_ads", help_text="Users who will receive this advertisement. Leave empty to send to all.")

    created_at = models.DateTimeField(auto_now_add=True, help_text="When the advertisement was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When the advertisement was last updated")

    def __str__(self):
        return f"Advertisement: {self.post} - {self.status}"
    
    class Meta:
        verbose_name = "Advertisement"
        verbose_name_plural = "Advertisements"
        ordering = ['-created_at']