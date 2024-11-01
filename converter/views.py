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


from django.shortcuts import render

def index(request):
    """
    View function for home page
    """
    context = {
        'title': 'Image to PDF Converter',
        'active_tab': 'index'
    }
    return render(request, 'converter/upload.html', context)


from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import os
from django.conf import settings
import tempfile
from docx2pdf import convert
import pythoncom  # Required for COM library initialization

@csrf_exempt
def word_to_pdf(request):
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            # Initialize COM library for thread
            pythoncom.CoInitialize()
            
            word_file = request.FILES['file']
            
            # Get conversion settings from request
            preserve_formatting = request.POST.get('preserve_formatting', 'true') == 'true'
            optimize_pdf = request.POST.get('optimize_pdf', 'true') == 'true'
            convert_images = request.POST.get('convert_images', 'true') == 'true'
            protect_pdf = request.POST.get('protect_pdf', 'false') == 'true'

            # Validate file size (50MB limit)
            if word_file.size > 50 * 1024 * 1024:  # 50MB in bytes
                return JsonResponse({'error': 'File size exceeds 50MB limit'}, status=400)

            # Validate file type
            if not word_file.name.endswith(('.doc', '.docx')):
                return JsonResponse({'error': 'Invalid file type. Only .doc and .docx files are allowed'}, status=400)

            # Create temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save uploaded file
                temp_word_path = os.path.join(temp_dir, word_file.name)
                temp_pdf_path = os.path.join(temp_dir, os.path.splitext(word_file.name)[0] + '.pdf')
                
                try:
                    # Save the uploaded file
                    with open(temp_word_path, 'wb+') as destination:
                        for chunk in word_file.chunks():
                            destination.write(chunk)
                    
                    # Convert to PDF
                    convert(temp_word_path, temp_pdf_path)
                    
                    # Read the PDF and send it as response
                    with open(temp_pdf_path, 'rb') as pdf_file:
                        response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                        response['Content-Disposition'] = f'attachment; filename="{os.path.splitext(word_file.name)[0]}.pdf"'
                        return response

                except Exception as e:
                    print(f"Conversion error: {str(e)}")
                    return JsonResponse({'error': f'Conversion failed: {str(e)}'}, status=500)
                
                finally:
                    # Cleanup: Remove temporary files
                    try:
                        if os.path.exists(temp_word_path):
                            os.remove(temp_word_path)
                        if os.path.exists(temp_pdf_path):
                            os.remove(temp_pdf_path)
                    except Exception as e:
                        print(f"Cleanup error: {str(e)}")

        except Exception as e:
            print(f"Processing error: {str(e)}")
            return JsonResponse({'error': f'Processing failed: {str(e)}'}, status=500)
            
        finally:
            # Uninitialize COM library
            pythoncom.CoUninitialize()

    # If not POST request, render the template
    context = {
        'features': [
            {
                'icon': '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" 
                          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                          <polyline points="7.5 4.21 12 6.81 16.5 4.21"/>
                          <polyline points="7.5 19.79 7.5 14.6 3 12"/>
                          <polyline points="21 12 16.5 14.6 16.5 19.79"/>
                          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                          <line x1="12" y1="22.08" x2="12" y2="12"/>
                        </svg>''',
                'title': 'Perfect Formatting',
                'description': 'Maintains original document formatting, fonts, images, and layout'
            },
            {
                'icon': '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" 
                          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <circle cx="12" cy="12" r="10"/>
                          <polyline points="12 6 12 12 16 14"/>
                        </svg>''',
                'title': 'Fast Conversion',
                'description': 'Convert your documents in seconds with high accuracy'
            },
            {
                'icon': '''<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" 
                          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                          <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                        </svg>''',
                'title': 'Secure Process',
                'description': 'Your documents are automatically deleted after conversion'
            }
        ],
        'faqs': [
            {
                'question': 'What file types are supported?',
                'answer': 'Our converter supports DOC and DOCX files from Microsoft Word.'
            },
            {
                'question': 'Will my formatting be preserved?',
                'answer': 'Yes, we maintain all formatting including fonts, images, tables, and layouts.'
            },
            {
                'question': 'Is there a file size limit?',
                'answer': 'Yes, you can upload Word documents up to 50MB in size.'
            },
            {
                'question': 'How long does conversion take?',
                'answer': 'Most documents are converted within seconds, depending on the file size and complexity.'
            }
        ],
        'stats': {
            'conversions_today': '1,234'
        }
    }
    
    return render(request, 'converter/word_to_pdf.html', context)