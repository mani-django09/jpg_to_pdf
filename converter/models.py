
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Conversion(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    num_images = models.IntegerField(default=0)
    orientation = models.CharField(max_length=20, default='portrait')
    auto_enhance = models.BooleanField(default=False)
    compression = models.BooleanField(default=True)
    pdf_size = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('processing', 'Processing')
        ],
        default='processing'
    )
    processing_time = models.FloatField(default=0.0)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'PDF Conversion'
        verbose_name_plural = 'PDF Conversions'

    def __str__(self):
        return f"Conversion {self.id} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
class ErrorLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    stack_trace = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Error Log'
        verbose_name_plural = 'Error Logs'

    def __str__(self):
        return f"{self.error_type} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

# Your existing models remain the same
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    conversion_count = models.IntegerField(default=0)
    storage_used = models.BigIntegerField(default=0)
    last_login = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.email}'s Profile"

class UserPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    default_quality = models.IntegerField(default=80)
    auto_enhance = models.BooleanField(default=False)
    compression = models.BooleanField(default=True)
    orientation = models.CharField(
        max_length=20,
        choices=[('portrait', 'Portrait'), ('landscape', 'Landscape')],
        default='portrait'
    )

    class Meta:
        verbose_name = 'User Preference'
        verbose_name_plural = 'User Preferences'

    def __str__(self):
        return f"{self.user.email}'s Preferences"

class WebsiteSettings(models.Model):
    max_file_size = models.IntegerField(
        default=10485760,
        help_text="Maximum file size in bytes"
    )
    max_files_per_conversion = models.IntegerField(
        default=20,
        help_text="Maximum number of files per conversion"
    )
    allowed_file_types = models.CharField(
        max_length=200,
        default="jpg,jpeg,png",
        help_text="Comma separated file extensions (e.g., jpg,jpeg,png)"
    )
    maintenance_mode = models.BooleanField(
        default=False,
        help_text="Enable maintenance mode"
    )
    maintenance_message = models.TextField(
        default="Site is under maintenance. Please try again later.",
        blank=True
    )

    class Meta:
        verbose_name = 'Website Setting'
        verbose_name_plural = 'Website Settings'

    def __str__(self):
        return "Website Settings"

    def save(self, *args, **kwargs):
        if not self.pk and WebsiteSettings.objects.exists():
            return
        super().save(*args, **kwargs)

# Signals remain the same
@receiver(post_save, sender=User)
def create_user_profile_and_preferences(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        UserPreference.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile_and_preferences(sender, instance, **kwargs):
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)

    try:
        instance.userpreference.save()
    except UserPreference.DoesNotExist:
        UserPreference.objects.create(user=instance)