from django.urls import path
from . import views
from . import auth_views


app_name = 'converter'  # Add namespace

urlpatterns = [
    path('', views.upload_image, name='index'),
    path('upload/', views.upload_image, name='upload'),

    #path('', views.convert_to_pdf, name='convert'),
    path('save-preferences', views.save_preferences, name='save_preferences'),
    path('statistics/', views.get_statistics, name='get_statistics'),
    path('login/', auth_views.login_view, name='login'),
    path('login', auth_views.login_view, name='login'),  # Handle both with and without trailing slash
    path('signup', auth_views.signup_view, name='signup'),  # Handle both with and without trailing slash
    path('signup/', auth_views.signup_view, name='signup'),  # Keep only one signup pattern
    path('logout/', auth_views.logout_view, name='logout'),
    path('login/', auth_views.login_view, name='login'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    #path('edit_profile/', views.edit_profile, name='edit_profile'),

    path('my_conversions/', views.my_conversions, name='my_conversions'),
    path('settings/', views.settings_view, name='settings'),
    path('forgot-password/', auth_views.forgot_password_view, name='forgot_password'),



]