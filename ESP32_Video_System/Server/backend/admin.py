from django.contrib import admin
from .models import ESP32Camera, VideoCapture

# This tells Django to show these tables in the web dashboard
admin.site.register(ESP32Camera)
admin.site.register(VideoCapture)