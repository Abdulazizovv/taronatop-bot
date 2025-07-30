
from reklama.models import AdPostTg, AdPostButton, Advertisement
from django.utils import timezone
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.http import HttpResponseRedirect
from django_celery_beat.models import PeriodicTask
from django.contrib import admin



@admin.register(AdPostTg)
class AdPostTgAdmin(admin.ModelAdmin):
    list_display = ("message_id", "user", "created_at")
    search_fields = ("message_id", "user__full_name")

    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    


@admin.register(AdPostButton)
class AdPostButtonAdmin(admin.ModelAdmin):
    list_display = ("title", "url", "is_active", "created_at")


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ("post", "status", "scheduled_time", "sent_time", "count", "send_now_action")
    list_filter = ("status",)
    filter_horizontal = ("buttons", "target_users")
    actions = ["send_advertisement"]
    readonly_fields = ["count", "created_at", "updated_at", "sent_time"]

    def send_now_action(self, obj):
        if obj.status == "draft":
            return mark_safe(f'<a class="button" href="{reverse("admin:send_advertisement_now", args=[obj.pk])}">📤 Yuborish</a>')
        return "-"
    send_now_action.short_description = "Yuborish"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        from django.shortcuts import get_object_or_404
        def send_now_view(request, ad_id):
            from botapp.tasks import send_advertisement_task
            ad = get_object_or_404(Advertisement, pk=ad_id)
            send_advertisement_task.delay(ad.id)
            self.message_user(request, f"📤 Reklama yuborish navbatiga qo‘shildi (ID: {ad.id})")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        custom_urls = [
            path("send/<int:ad_id>/", self.admin_site.admin_view(send_now_view), name="send_advertisement_now"),
        ]
        return custom_urls + urls

    def send_advertisement(self, request, queryset):
        from botapp.tasks import send_advertisement_task
        for ad in queryset:
            send_advertisement_task.delay(ad.id)
        self.message_user(request, f"{queryset.count()} ta reklama yuborish uchun navbatga qo‘shildi.")