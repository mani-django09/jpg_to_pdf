from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.exceptions import ValidationError
from PIL import Image, ImageEnhance
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from io import BytesIO
import time
import os
from io import BytesIO
from reportlab.lib.pagesizes import letter, landscape

import json
import traceback
from django.utils import timezone
from datetime import datetime
from django.db.models import Sum, Count
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Conversion, WebsiteSettings, ErrorLog, UserProfile, UserPreference

def upload_image(request):
    if request.method == 'POST':
        start_time = time.time()
        
        try:
            files = request.FILES.getlist('images')
            if not files:
                return JsonResponse({'error': 'No files uploaded'}, status=400)

            # Process first image
            first_image = None
            images = []

            for file in files:
                # Open and process image
                img = Image.open(file)
                
                # Convert to RGB if necessary
                if img.mode in ['RGBA', 'LA']:
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[3])
                    else:
                        background.paste(img)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Apply rotation
                rotation = int(request.POST.get(f'rotation_{file.name}', '0'))
                if rotation:
                    img = img.rotate(-rotation, expand=True)

                # Apply auto enhancement if selected
                if request.POST.get('autoEnhance') == 'true':
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.2)
                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(1.1)

                if first_image is None:
                    first_image = img
                else:
                    images.append(img)

            # Create PDF
            pdf_buffer = BytesIO()
            
            # Save first image as PDF with additional images
            first_image.save(
                pdf_buffer,
                'PDF',
                save_all=True,
                append_images=images,
                resolution=300,
                optimize=False,
                quality=95
            )

            # Get PDF data
            pdf_data = pdf_buffer.getvalue()
            pdf_buffer.seek(0)

            # Create response
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="converted_{timestamp}.pdf"'
            response['Content-Length'] = len(pdf_data)
            response.write(pdf_data)

            # Log successful conversion
            if request.user.is_authenticated:
                Conversion.objects.create(
                    user=request.user,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    num_images=len(files),
                    pdf_size=len(pdf_data),
                    status='completed',
                    processing_time=time.time() - start_time
                )

            return response

        except Exception as e:
            print(f"Error in PDF conversion: {str(e)}")
            print(traceback.format_exc())
            return JsonResponse({'error': str(e)}, status=500)

        finally:
            if 'pdf_buffer' in locals():
                pdf_buffer.close()

    return render(request, 'converter/upload.html')
@login_required
def profile_view(request):
    user = request.user
    profile = UserProfile.objects.get_or_create(user=user)[0]
    preferences = UserPreference.objects.get_or_create(user=user)[0]
    
    all_conversions = Conversion.objects.filter(user=user)
    stats = {
        'total_conversions': all_conversions.count(),
        'successful_conversions': all_conversions.filter(status='completed').count(),
        'total_size': all_conversions.filter(status='completed').aggregate(total=Sum('pdf_size'))['total'] or 0,
        'recent_conversions': all_conversions.order_by('-timestamp')[:5]
    }
    
    context = {
        'profile': profile,
        'preferences': preferences,
        'stats': stats,
        'recent_conversions': stats['recent_conversions'],
        'total_conversions': stats['total_conversions'],
        'successful_conversions': stats['successful_conversions'],
        'total_size': stats['total_size']
    }
    
    return render(request, 'converter/profile.html', context)

@login_required
def edit_profile(request):
    user = request.user
    profile = UserProfile.objects.get_or_create(user=user)[0]
    preferences = UserPreference.objects.get_or_create(user=user)[0]

    if request.method == 'POST':
        profile.bio = request.POST.get('bio', '')
        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        profile.save()

        preferences.default_quality = int(request.POST.get('default_quality', 80))
        preferences.auto_enhance = request.POST.get('auto_enhance') == 'on'
        preferences.compression = request.POST.get('compression') == 'on'
        preferences.orientation = request.POST.get('orientation', 'portrait')
        preferences.save()

        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('converter:profile')

    context = {
        'profile': profile,
        'preferences': preferences,
        'user': user
    }
    return render(request, 'converter/edit_profile.html', context)

@login_required
def my_conversions(request):
    conversions = Conversion.objects.filter(user=request.user).order_by('-timestamp')
    
    stats = {
        'total_conversions': conversions.count(),
        'successful_conversions': conversions.filter(status='completed').count(),
        'total_size': conversions.filter(status='completed').aggregate(total=Sum('pdf_size'))['total'] or 0,
    }
    
    context = {
        'conversions': conversions,
        'stats': stats,
    }
    
    return render(request, 'converter/my_conversions.html', context)

@login_required
def settings_view(request):
    preferences = UserPreference.objects.get_or_create(user=request.user)[0]
    
    if request.method == 'POST':
        preferences.default_quality = int(request.POST.get('default_quality', 80))
        preferences.auto_enhance = request.POST.get('auto_enhance') == 'on'
        preferences.compression = request.POST.get('compression') == 'on'
        preferences.orientation = request.POST.get('orientation', 'portrait')
        preferences.save()
        
        messages.success(request, 'Settings updated successfully!')
        return redirect('converter:settings')
    
    return render(request, 'converter/settings.html', {'preferences': preferences})

def save_preferences(request):
    if request.method == 'POST':
        try:
            preferences = json.loads(request.body)
            request.session['converter_preferences'] = preferences
            return JsonResponse({'status': 'success'})
        except Exception as e:
            ErrorLog.objects.create(
                error_type=type(e).__name__,
                error_message=str(e),
                stack_trace=traceback.format_exc(),
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            return JsonResponse({'error': str(e)}, status=400)
    
    elif request.method == 'GET':
        try:
            preferences = request.session.get('converter_preferences', {
                'orientation': 'portrait',
                'autoEnhance': False,
                'compression': True
            })
            return JsonResponse(preferences)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

def get_statistics(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    try:
        total_conversions = Conversion.objects.count()
        successful_conversions = Conversion.objects.filter(status='completed').count()
        failed_conversions = Conversion.objects.filter(status='failed').count()
        success_rate = (successful_conversions / total_conversions * 100) if total_conversions > 0 else 0

        return JsonResponse({
            'total_conversions': total_conversions,
            'successful_conversions': successful_conversions,
            'failed_conversions': failed_conversions,
            'success_rate': success_rate,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    temp_filename = os.path.join(settings.TEMP_DIR, f'{settings.TEMP_PREFIX}{time.time()}.jpg')
