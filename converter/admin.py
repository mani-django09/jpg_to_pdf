from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.http import HttpResponse
import csv
from datetime import datetime
from .models import Conversion, WebsiteSettings, ErrorLog

@admin.register(Conversion)
class ConversionAdmin(admin.ModelAdmin):
    list_display = ('id', 'timestamp', 'ip_address', 'num_images', 
                   'orientation', 'status', 'processing_time', 'colored_status')
    list_filter = ('status', 'orientation', 'auto_enhance', 'compression')
    search_fields = ('ip_address', 'status')
    date_hierarchy = 'timestamp'
    
    def colored_status(self, obj):
        colors = {
            'completed': 'green',
            'failed': 'red',
            'processing': 'orange'
        }
        color = colors.get(obj.status.lower(), 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.status
        )
    colored_status.short_description = 'Status'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export-csv/', self.export_csv, name='export_conversions_csv'),
        ]
        return custom_urls + urls

    def export_csv(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="conversions_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Timestamp', 'IP Address', 'Number of Images', 
                        'Orientation', 'Status', 'Processing Time'])
        
        for conversion in Conversion.objects.all():
            writer.writerow([
                conversion.id,
                conversion.timestamp,
                conversion.ip_address,
                conversion.num_images,
                conversion.orientation,
                conversion.status,
                conversion.processing_time
            ])
        
        return response

    actions = ['export_selected_conversions']

    def export_selected_conversions(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="selected_conversions.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Timestamp', 'IP Address', 'Number of Images', 
                        'Orientation', 'Status', 'Processing Time'])
        
        for conversion in queryset:
            writer.writerow([
                conversion.id,
                conversion.timestamp,
                conversion.ip_address,
                conversion.num_images,
                conversion.orientation,
                conversion.status,
                conversion.processing_time
            ])
        
        return response
    export_selected_conversions.short_description = "Export selected conversions to CSV"

@admin.register(WebsiteSettings)
class WebsiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('default_orientation', 'max_file_size_mb', 'max_images_per_conversion',
                   'maintenance_mode', 'enable_compression', 'enable_auto_enhance')
    
    def max_file_size_mb(self, obj):
        return f"{obj.max_file_size / (1024 * 1024):.2f} MB"
    max_file_size_mb.short_description = "Max File Size"

    def has_add_permission(self, request):
        # Prevent creating multiple settings instances
        return not WebsiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deleting the settings instance
        return False

@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'error_type', 'ip_address', 'short_message')
    list_filter = ('error_type', 'timestamp')
    search_fields = ('error_type', 'error_message', 'ip_address')
    readonly_fields = ('timestamp', 'error_type', 'error_message', 'stack_trace',
                      'ip_address', 'user_agent')

    def short_message(self, obj):
        return obj.error_message[:100] + '...' if len(obj.error_message) > 100 else obj.error_message
    short_message.short_description = 'Error Message'