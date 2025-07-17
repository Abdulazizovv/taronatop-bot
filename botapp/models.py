from django.db import models


class BotUser(models.Model):
    user_id = models.CharField(max_length=255, unique=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    language_code = models.CharField(max_length=10, blank=True, null=True, default='uz')
    is_bot = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.user_id})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    class Meta:
        verbose_name = "Bot User"
        verbose_name_plural = "Bot Users"
        ordering = ['-created_at']
        

class BotChat(models.Model):
    chat_id = models.CharField(max_length=255, unique=True)
    chat_type = models.CharField(max_length=50, choices=[('private', 'Private'), ('group', 'Group'), ('supergroup', 'Supergroup'), ('channel', 'Channel')])
    title = models.CharField(max_length=255, blank=True, null=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    invite_link = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    is_required = models.BooleanField(default=False, help_text="Is this chat required for bot operation?")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.chat_id})" 
    
    class Meta:
        verbose_name = "Bot Chat"
        verbose_name_plural = "Bot Chats"
        ordering = ['-created_at']

    @property
    def full_title(self):
        return self.title if self.title else self.username if self.username else f"Chat {self.chat_id}"
    
    @property
    def chat_identifier(self):
        return self.username if self.username else self.chat_id
    
    @property
    def chat_type_display(self):
        return dict(self._meta.get_field('chat_type').choices).get(self.chat_type, 'Unknown')
    
    @property
    def is_private_chat(self):
        return bool(self.username)
    
    def required_chats():
        return BotChat.objects.filter(is_required=True, is_active=True, is_admin=True)