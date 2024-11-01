from django.contrib import admin
from .models import (
    UserProfile, 
    UserPreference, 
    Conversion, 
    WebsiteSettings, 
    ErrorLog
)

@admin.register(Conversion)
class ConversionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'timestamp', 'num_images', 'status', 'processing_time')
    list_filter = ('status', 'auto_enhance', 'compression')
    search_fields = ('user__email', 'ip_address')
    readonly_fields = ('timestamp', 'processing_time')

@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'error_type', 'ip_address', 'user')
    list_filter = ('error_type', 'timestamp')
    search_fields = ('error_message', 'ip_address', 'user__email')
    readonly_fields = ('timestamp',)

# Your existing admin registrations remain the same
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'conversion_count', 'storage_used', 'date_joined')
    search_fields = ('user__email', 'user__username')

@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'default_quality', 'auto_enhance', 'compression', 'orientation')
    list_filter = ('auto_enhance', 'compression', 'orientation')

@admin.register(WebsiteSettings)
class WebsiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('max_file_size', 'max_files_per_conversion', 'maintenance_mode')
    
    def has_add_permission(self, request):
        return not WebsiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False