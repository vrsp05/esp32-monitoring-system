"""
URL configuration for backend project.
"""
from django.contrib import admin
from django.urls import path
from . import views  # Import the views.py file we just created in this same folder
from django.conf import settings             
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # This is the "Mailbox" address. 
    # When traffic hits /upload/, it triggers the receive_video logic.
    path('upload/', views.upload_video, name='upload_video'),
    path('api/videos/', views.get_videos, name='get_videos'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)