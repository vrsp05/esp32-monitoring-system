import os
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# We disable CSRF protection here because our ESP32 is a simple edge device
# and cannot easily negotiate complex web security tokens.
@csrf_exempt
def receive_video(request):
    if request.method == 'POST':
        try:
            # 1. Grab the raw binary data the ESP32 just sent
            video_data = request.body
            
            if not video_data:
                return JsonResponse({'status': 'error', 'message': 'No video data received'}, status=400)

            # 2. Define where to save the files (we will create this folder later)
            save_directory = os.path.join('media', 'videos')
            os.makedirs(save_directory, exist_ok=True)

            # 3. Create a unique filename using a timestamp so videos do not overwrite each other
            timestamp = int(time.time())
            filename = f"esp32_capture_{timestamp}.avi"
            filepath = os.path.join(save_directory, filename)

            # 4. Open the file in 'Write Binary' (wb) mode and save the data
            with open(filepath, 'wb') as f:
                f.write(video_data)

            print(f"SUCCESS: Saved new video -> {filename} ({len(video_data)} bytes)")
            
            # 5. Send a confirmation response back to the ESP32
            return JsonResponse({'status': 'success', 'message': 'Video safely archived.'}, status=200)

        except Exception as e:
            print(f"ERROR: Failed to process upload: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    # If a standard web browser accidentally tries to look at this URL (GET request)
    return JsonResponse({'status': 'error', 'message': 'Only POST requests from ESP32 allowed'}, status=405)