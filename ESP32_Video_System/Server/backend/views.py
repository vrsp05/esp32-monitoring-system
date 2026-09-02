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
import uuid

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
    # 1. Catch the username from the frontend request
    username = request.GET.get('user')
    
    # 2. Filter the database to ONLY grab this specific user's videos
    if username:
        videos = VideoCapture.objects.filter(user__username=username).order_by('-timestamp')[:24]
    else:
        videos = [] # Return nothing if no user is provided
    
    video_list = []
    for video in videos:
        local_time = timezone.localtime(video.timestamp)
        
        video_list.append({
            "id": video.id,
            "url": video.video_file.url,
            "timestamp": local_time.strftime('%m/%d/%Y %I:%M %p'),
            "is_cloud_saved": video.is_cloud_saved
        })
        
    return JsonResponse({"videos": video_list})

# --- AUTHENTICATION ENDPOINTS ---

# Note: @csrf_exempt is used here so your static HTML file can easily 
# talk to the server. Enmanuel will secure this later in Next.js!
@csrf_exempt
def signup(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')

        # 1. Enforce 5-character minimum password length
        if len(password) < 5:
            return JsonResponse({
                'status': 'error', 
                'message': 'Password must be at least 5 characters long.'
            }, status=400)

        # 2. Prevent duplicate usernames
        if User.objects.filter(username=username).exists():
            return JsonResponse({
                'status': 'error', 
                'message': 'Username is already taken. Please choose another.'
            }, status=400)

        # 3. Create the account if both security checks pass
        user = User.objects.create_user(username=username, password=password)
        user.save()
        
        return JsonResponse({'status': 'success'})

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
            
            # Fetch the user's camera using your custom related_name
            camera = ESP32Camera.objects.filter(user=user).first()
            device_id = camera.device_id if camera else "No Camera Registered"

            return JsonResponse({
                "status": "success", 
                "message": "Logged in successfully!",
                "username": user.username,
                "device_id": str(device_id)
            })
        else:
            return JsonResponse({"status": "error", "message": "Invalid username or password."}, status=400)
    return JsonResponse({"status": "error", "message": "POST request required."}, status=405)

@csrf_exempt
def save_to_vault(request, video_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            
            # Locate the specific video belonging to this user
            video = VideoCapture.objects.get(id=video_id, user__username=username)
            
            # Enforce the 10-video limit
            saved_count = VideoCapture.objects.filter(user__username=username, is_cloud_saved=True).count()
            
            if saved_count >= 10 and not video.is_cloud_saved:
                return JsonResponse({"status": "error", "message": "Vault is full! Maximum 10 videos allowed."}, status=400)
            
            # Save it to the vault
            video.is_cloud_saved = True
            video.save()
            return JsonResponse({"status": "success", "message": "Video permanently saved to Cloud Vault."})
            
        except VideoCapture.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Video not found."}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
            
    return JsonResponse({"status": "error", "message": "POST request required."}, status=405)

@csrf_exempt
def delete_video(request, video_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            
            # Locate the video
            video = VideoCapture.objects.get(id=video_id, user__username=username)
            
            # 1. DELETE THE PHYSICAL .MP4 FILE FROM THE HARD DRIVE
            if video.video_file:
                if os.path.isfile(video.video_file.path):
                    os.remove(video.video_file.path)
            
            # 2. DELETE THE RECORD FROM THE DATABASE
            video.delete() 
            
            return JsonResponse({"status": "success", "message": "Video permanently deleted."})
            
        except VideoCapture.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Video not found."}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)
            
    return JsonResponse({"status": "error", "message": "POST request required."}, status=405)

@csrf_exempt
@csrf_exempt
def generate_camera_id(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        
        try:
            user = User.objects.get(username=username)
            
            # 1. Enforce the 3-device maximum limit
            if ESP32Camera.objects.filter(user=user).count() >= 3:
                return JsonResponse({'status': 'error', 'message': 'Device limit reached. Maximum of 3 devices allowed.'}, status=400)
            
            new_device_id = str(uuid.uuid4())
            
            # Dynamically name the camera based on how many the user already has
            camera_count = ESP32Camera.objects.filter(user=user).count() + 1
            camera_name = f"Camera {camera_count}"
            
            ESP32Camera.objects.create(
                user=user, 
                device_id=new_device_id,
                name=camera_name
            )
            
            return JsonResponse({
                'status': 'success', 
                'device_id': new_device_id,
                'message': 'Camera registered successfully!'
            })
            
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found.'}, status=404)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=405)

def get_devices(request):
    username = request.GET.get('user')
    if not username:
        return JsonResponse({"devices": []})
    
    try:
        user = User.objects.get(username=username)
        cameras = ESP32Camera.objects.filter(user=user).order_by('-date_added')
        
        device_list = []
        for cam in cameras:
            local_time = timezone.localtime(cam.date_added)
            device_list.append({
                "id": cam.id,
                "device_id": cam.device_id,
                "name": cam.name,
                "status": cam.status,
                "storage_space": cam.storage_space,
                "date_added": local_time.strftime('%m/%d/%Y %I:%M %p'),
                # Dynamically count the videos associated with this specific camera
                "video_count": cam.captures.count() 
            })
        return JsonResponse({"devices": device_list})
    except User.DoesNotExist:
        return JsonResponse({"devices": []})

@csrf_exempt
def delete_device(request, device_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            
            # Ensure the device belongs to the correct user before deleting
            camera = ESP32Camera.objects.get(id=device_id, user__username=username)
            camera.delete()
            
            return JsonResponse({"status": "success", "message": "Device deleted."})
        except ESP32Camera.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Device not found."}, status=404)
            
    return JsonResponse({"status": "error", "message": "POST request required."}, status=405)