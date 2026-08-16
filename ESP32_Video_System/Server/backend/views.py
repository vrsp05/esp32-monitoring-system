from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from .models import ESP32Camera, VideoCapture

@csrf_exempt
def upload_video(request):
    if request.method == 'POST':
        # 1. The Bouncer: Check for the secret ID in the HTTP Headers
        device_id = request.headers.get('X-Device-ID')
        
        if not device_id:
            return JsonResponse({"status": "error", "message": "Missing Device ID"}, status=400)
            
        # 2. The Verification: Does this camera actually exist in our database?
        try:
            camera = ESP32Camera.objects.get(device_id=device_id)
        except ESP32Camera.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Invalid Device ID"}, status=403)
            
        # 3. The Package: Get the raw video bytes from the ESP32
        raw_video = request.body
        
        if not raw_video:
            return JsonResponse({"status": "error", "message": "No video data received"}, status=400)

        # 4. The Vault: Save the video directly to the user's database profile
        new_capture = VideoCapture(
            user=camera.user,
            camera=camera
        )
        # ContentFile converts the raw bytes into a format the database can store
        new_capture.video_file.save(f"capture_{camera.device_id[-6:]}.avi", ContentFile(raw_video))
        new_capture.save()

        return JsonResponse({"status": "success", "message": "Video safely routed to user account!"})

    # Reject standard web browser GET requests
    return JsonResponse({"status": "error", "message": "Only POST requests from ESP32 allowed"}, status=405)