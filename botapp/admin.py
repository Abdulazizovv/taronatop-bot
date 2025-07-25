from django.contrib import admin
from botapp.models import BotUser, BotChat, YoutubeAudio


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'full_name', 'username', 'language_code', 'is_admin', 'is_active', 'is_blocked', 'created_at')
    search_fields = ('user_id', 'username', 'first_name', 'last_name')
    list_filter = ('is_admin', 'is_active', 'is_blocked')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'


@admin.register(BotChat)
class BotChatAdmin(admin.ModelAdmin):
    list_display = ('chat_id', 'title', 'chat_type', 'username', 'invite_link', 'is_active', 'is_blocked', 'is_admin', 'is_required', 'created_at')
    search_fields = ('chat_id', 'title', 'username')
    list_filter = ('chat_type', 'is_active', 'is_blocked', 'is_admin', 'is_required')
    ordering = ('-created_at',)
    readonly_fields = ('chat_id', 'title', 'username', 'invite_link', 'is_active', 'is_blocked', 'is_admin', 'chat_type', 'created_at', 'updated_at')
    def full_name(self, obj):
        return obj.title or obj.username or obj.chat_id
    full_name.short_description = 'Chat Name'
    def chat_type_display(self, obj):
        return dict(BotChat._meta.get_field('chat_type').choices).get(obj.chat_type, 'Unknown')
    chat_type_display.short_description = 'Chat Type'

    def has_add_permission(self, request, obj=None):
        return False
    
    # def has_change_permission(self, request, obj=None):
    #     return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_view_permission(self, request, obj=None):
        return True
    

@admin.register(YoutubeAudio)
class YoutubeAudioAdmin(admin.ModelAdmin):
    list_display = ('video_id', 'title', 'user', 'created_at', 'updated_at')
    search_fields = ('video_id', 'title')
    list_filter = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')


    def has_add_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    