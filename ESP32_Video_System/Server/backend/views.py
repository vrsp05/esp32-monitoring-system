import os
import tempfile
import subprocess
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files import File
from .models import ESP32Camera, VideoCapture
from django.utils import timezone
import json
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt

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
                '-vcodec', 'libx264', 
                '-pix_fmt', 'yuv420p', # <-- THE ENCODING FIX for Windows/Web playback
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
        
        # --- THE FILENAME FIX ---
        # Get the exact local time when the video arrives
        local_time = timezone.localtime(timezone.now())
        time_str = local_time.strftime('%m-%d-%Y_%I-%M-%p')
        final_filename = f"capture_{time_str}.mp4"

        with open(temp_mp4_path, 'rb') as f:
            new_capture.video_file.save(final_filename, File(f))
        new_capture.save()

        # 6. Clean up: Delete the temporary files to prevent server hard drive overflow
        os.remove(temp_avi_path)
        os.remove(temp_mp4_path)

        return JsonResponse({"status": "success", "message": "Video converted to .mp4 and securely routed!"})

    return JsonResponse({"status": "error", "message": "Only POST requests allowed"}, status=405)

def get_videos(request):
    # Grab the 24 newest videos from the database
    videos = VideoCapture.objects.all().order_by('-timestamp')[:24]
    
    video_list = []
    for video in videos:
        # Convert raw UTC to local Mountain Time
        local_time = timezone.localtime(video.timestamp)
        
        video_list.append({
            "id": video.id,
            "url": video.video_file.url,
            "timestamp": local_time.strftime('%m/%d/%Y %I:%M %p') # Use local_time here!
        })
        
    return JsonResponse({"videos": video_list})

# --- AUTHENTICATION ENDPOINTS ---

# Note: @csrf_exempt is used here so your static HTML file can easily 
# talk to the server. Enmanuel will secure this later in Next.js!
@csrf_exempt
def api_signup(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            
            if User.objects.filter(username=username).exists():
                return JsonResponse({"status": "error", "message": "Username already exists."}, status=400)
            
            # Create the user in the database
            user = User.objects.create_user(username=username, password=password)
            return JsonResponse({"status": "success", "message": "Account created!"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
    return JsonResponse({"status": "error", "message": "POST request required."}, status=405)

@csrf_exempt
def api_login(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        
        # Check if the credentials match the database
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({"status": "success", "message": "Logged in successfully!"})
        else:
            return JsonResponse({"status": "error", "message": "Invalid username or password."}, status=400)
    return JsonResponse({"status": "error", "message": "POST request required."}, status=405)