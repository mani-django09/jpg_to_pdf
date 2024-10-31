from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.exceptions import ValidationError
from PIL import Image, ImageEnhance
from io import BytesIO
import time
import traceback
import os
import json
from datetime import datetime
from .models import Conversion, WebsiteSettings, ErrorLog

@ensure_csrf_cookie
def upload_image(request):
    if request.method == 'POST':
        start_time = time.time()
        pdf_buffer = BytesIO()
        
        try:
            # Get settings
            settings = WebsiteSettings.objects.first()
            if settings and settings.maintenance_mode:
                return JsonResponse({'error': 'Site is under maintenance'}, status=503)

            files = request.FILES.getlist('images')
            orientation = request.POST.get('orientation', settings.default_orientation if settings else 'portrait')
            auto_enhance = request.POST.get('autoEnhance') == 'true'
            compression = request.POST.get('compression') == 'true'

            if not files:
                return JsonResponse({'error': 'No files uploaded'}, status=400)

            # Get allowed file types from settings
            allowed_extensions = [f'.{ext.lower().strip()}' for ext in 
                                (settings.allowed_file_types if settings else 'jpg,jpeg,png').split(',')]

            # Validate files
            for file in files:
                # Check file size
                if settings and file.size > settings.max_file_size:
                    return JsonResponse({
                        'error': f'File {file.name} is too large. Maximum size is {settings.max_file_size / (1024*1024):.1f}MB'
                    }, status=400)

                # Check file type
                ext = os.path.splitext(file.name)[1].lower()
                if ext not in allowed_extensions:
                    return JsonResponse({
                        'error': f'File type {ext} is not allowed. Allowed types: {", ".join(allowed_extensions)}'
                    }, status=400)

            # Check total number of files
            if settings and len(files) > settings.max_images_per_conversion:
                return JsonResponse({
                    'error': f'Maximum {settings.max_images_per_conversion} images allowed'
                }, status=400)

            # Process images and create PDF
            first_image = None
            images = []
            
            for file in files:
                try:
                    img = Image.open(file)
                    
                    # Convert to RGB
                    if img.mode in ['RGBA', 'P']:
                        # Create white background for transparent PNGs
                        background = Image.new('RGB', img.size, 'white')
                        if img.mode == 'RGBA':
                            background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                        else:
                            background.paste(img)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Apply rotation if specified
                    rotation = int(request.POST.get(f'rotation_{file.name}', '0'))
                    if rotation:
                        img = img.rotate(-rotation, expand=True)
                    
                    # Apply orientation
                    if orientation == 'landscape' and img.width < img.height:
                        img = img.rotate(-90, expand=True)
                    
                    # Apply auto enhancement
                    if auto_enhance:
                        enhancer = ImageEnhance.Contrast(img)
                        img = enhancer.enhance(1.2)
                        enhancer = ImageEnhance.Brightness(img)
                        img = enhancer.enhance(1.1)
                        enhancer = ImageEnhance.Color(img)
                        img = enhancer.enhance(1.2)

                    if first_image is None:
                        first_image = img
                    else:
                        images.append(img)

                except Exception as e:
                    raise ValidationError(f"Error processing image {file.name}: {str(e)}")

            if first_image is None:
                raise ValidationError("No valid images to process")

            # Create PDF
            first_image.save(
                pdf_buffer,
                'PDF',
                resolution=300.0,
                save_all=True,
                append_images=images,
                optimize=compression
            )

            # Prepare response
            pdf_buffer.seek(0)
            response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
            
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'converted_{timestamp}.pdf'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            # Record successful conversion
            processing_time = time.time() - start_time
            Conversion.objects.create(
                ip_address=request.META.get('REMOTE_ADDR'),
                num_images=len(files),
                orientation=orientation,
                auto_enhance=auto_enhance,
                compression=compression,
                pdf_size=len(pdf_buffer.getvalue()),
                status='completed',
                processing_time=processing_time
            )

            return response

        except ValidationError as e:
            ErrorLog.objects.create(
                error_type='ValidationError',
                error_message=str(e),
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            return JsonResponse({'error': str(e)}, status=400)

        except Exception as e:
            ErrorLog.objects.create(
                error_type=type(e).__name__,
                error_message=str(e),
                stack_trace=traceback.format_exc(),
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            Conversion.objects.create(
                ip_address=request.META.get('REMOTE_ADDR'),
                num_images=len(files) if 'files' in locals() else 0,
                orientation=orientation if 'orientation' in locals() else 'unknown',
                status='failed',
                processing_time=time.time() - start_time
            )

            return JsonResponse({'error': 'An error occurred during conversion'}, status=500)

        finally:
            if 'pdf_buffer' in locals():
                pdf_buffer.close()

    return render(request, 'converter/upload.html')

def save_preferences(request):
    """Handle saving user preferences."""
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
            ErrorLog.objects.create(
                error_type=type(e).__name__,
                error_message=str(e),
                stack_trace=traceback.format_exc(),
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            return JsonResponse({'error': str(e)}, status=500)

def get_statistics(request):
    """Get conversion statistics for admin dashboard."""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    try:
        total_conversions = Conversion.objects.count()
        successful_conversions = Conversion.objects.filter(status='completed').count()
        failed_conversions = Conversion.objects.filter(status='failed').count()
        avg_processing_time = Conversion.objects.filter(status='completed').aggregate(
            avg_processing_time('processing_time'))['processing_time__avg']

        return JsonResponse({
            'total_conversions': total_conversions,
            'successful_conversions': successful_conversions,
            'failed_conversions': failed_conversions,
            'success_rate': (successful_conversions / total_conversions * 100) if total_conversions > 0 else 0,
            'avg_processing_time': round(avg_processing_time, 2) if avg_processing_time else 0
        })
    except Exception as e:
        ErrorLog.objects.create(
            error_type=type(e).__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        return JsonResponse({'error': str(e)}, status=500)