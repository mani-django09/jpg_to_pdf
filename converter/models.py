from django.db import models

class ImageUpload(models.Model):
    image = models.ImageField(upload_to='images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    from django.db import models
from django.utils import timezone

class Conversion(models.Model):
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(default=timezone.now)
    num_images = models.IntegerField()
    orientation = models.CharField(max_length=20)
    auto_enhance = models.BooleanField(default=False)
    compression = models.BooleanField(default=True)
    pdf_size = models.IntegerField(help_text="Size in bytes")
    status = models.CharField(max_length=20)
    processing_time = models.FloatField(help_text="Time in seconds")

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'PDF Conversion'
        verbose_name_plural = 'PDF Conversions'

    def __str__(self):
        return f"Conversion {self.id} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class WebsiteSettings(models.Model):
    max_file_size = models.IntegerField(default=10485760, help_text="Maximum file size in bytes")
    max_images_per_conversion = models.IntegerField(default=20)
    allowed_file_types = models.CharField(max_length=200, default="jpg,jpeg,png", help_text="Comma separated file extensions (e.g., jpg,jpeg,png)")
    maintenance_mode = models.BooleanField(default=False)
    default_orientation = models.CharField(
        max_length=20,
        choices=[('portrait', 'Portrait'), ('landscape', 'Landscape')],
        default='portrait'
    )
    enable_compression = models.BooleanField(default=True)
    enable_auto_enhance = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Website Setting'
        verbose_name_plural = 'Website Settings'

    def __str__(self):
        return "Website Settings"

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.__class__.objects.exclude(id=self.id).delete()
        super().save(*args, **kwargs)

class ErrorLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    stack_trace = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Error Log'
        verbose_name_plural = 'Error Logs'

    def __str__(self):
        return f"{self.error_type} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
