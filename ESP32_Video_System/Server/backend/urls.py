"""
URL configuration for backend project.
"""
from django.contrib import admin
from django.urls import path
from . import views  # Import the views.py file we just created in this same folder

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # This is the "Mailbox" address. 
    # When traffic hits /upload/, it triggers the receive_video logic.
    path('upload/', views.receive_video, name='receive_video'),
]