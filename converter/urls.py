from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_image, name='upload_image'),
    #path('', views.convert_to_pdf, name='convert'),
    path('save-preferences', views.save_preferences, name='save_preferences'),
    path('statistics/', views.get_statistics, name='get_statistics'),

]