import os
import tempfile
import subprocess
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files import File
from .models import ESP32Camera, VideoCapture

@csrf_exempt
def upload_video(request):
    if request.method == 'POST':
        # 1. The Bouncer: Check for the secret ID
        device_id = request.headers.get('X-Device-ID')
        if not device_id:
            return JsonResponse({"status": "error", "message": "Missing Device ID"}, status=400)
            
        try:
            camera = ESP32Camera.objects.get(device_id=device_id)
        except ESP32Camera.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Invalid Device ID"}, status=403)
            
        raw_video = request.body
        if not raw_video:
            return JsonResponse({"status": "error", "message": "No video data received"}, status=400)

        # --- THE FFMPEG PIPELINE ---

        # 2. Create a temporary .avi file and write the raw ESP32 bytes into it
        fd_avi, temp_avi_path = tempfile.mkstemp(suffix=".avi")
        with os.fdopen(fd_avi, 'wb') as f:
            f.write(raw_video)
            
        # 3. Create an empty temporary .mp4 file destination
        fd_mp4, temp_mp4_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd_mp4) # Close it briefly so FFmpeg can write to it
        
        # 4. Trigger the FFmpeg conversion in the background
        try:
            subprocess.run([
                'ffmpeg', '-y', '-i', temp_avi_path, 
                '-vcodec', 'libx264', # The standard web-friendly video codec
                temp_mp4_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            os.remove(temp_avi_path)
            return JsonResponse({"status": "error", "message": "FFmpeg conversion failed."}, status=500)
        except FileNotFoundError:
            os.remove(temp_avi_path)
            return JsonResponse({"status": "error", "message": "FFmpeg is not installed on this machine."}, status=500)

        # 5. The Vault: Save the newly converted .mp4 to the user's database
        new_capture = VideoCapture(user=camera.user, camera=camera)
        with open(temp_mp4_path, 'rb') as f:
            new_capture.video_file.save(f"capture_{camera.device_id[-6:]}.mp4", File(f))
        new_capture.save()

        # 6. Clean up: Delete the temporary files to prevent server hard drive overflow
        os.remove(temp_avi_path)
        os.remove(temp_mp4_path)

        return JsonResponse({"status": "success", "message": "Video converted to .mp4 and securely routed!"})

    return JsonResponse({"status": "error", "message": "Only POST requests allowed"}, status=405)