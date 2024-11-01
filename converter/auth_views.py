from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse

def login_view(request):
    # Redirect if user is already logged in
    if request.user.is_authenticated:
        return redirect('converter:index')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        
        try:
            # Get user by email
            user = User.objects.get(email=email)
            # Authenticate using username (email in this case)
            user = authenticate(username=user.username, password=password)
            
            if user is not None:
                login(request, user)
                
                # Set session expiry based on remember me
                if not remember_me:
                    request.session.set_expiry(0)
                
                messages.success(request, 'Successfully logged in!')
                # Get next URL or default to home
                next_url = request.GET.get('next', reverse('converter:index'))
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid password!')
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email!')

        # If authentication failed, redirect back to login with error message
        return render(request, 'converter/login.html', {
            'email': email,
            'error': True
        })
    
    return render(request, 'converter/login.html')

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('converter:index')

    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Form validation
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered!')
            return render(request, 'converter/signup.html', {
                'first_name': first_name,
                'last_name': last_name,
            })

        if password != confirm_password:
            messages.error(request, 'Passwords do not match!')
            return render(request, 'converter/signup.html', {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
            })

        try:
            # Create user
            user = User.objects.create_user(
                username=email,  # Using email as username
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # Log user in
            login(request, user)
            messages.success(request, f'Welcome {first_name}! Your account has been created successfully.')
            return redirect('converter:index')

        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')
            return render(request, 'converter/signup.html', {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
            })

    return render(request, 'converter/signup.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'Successfully logged out!')
    return redirect('converter:index')
def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('converter:index')

    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email)
            messages.success(request, 'Password reset instructions sent to your email!')
            return redirect('converter:login')
            
        except User.DoesNotExist:
            messages.success(request, 'If an account exists with this email, you will receive password reset instructions.')
            return redirect('converter:login')
    
    return render(request, 'converter/forgot_password.html')