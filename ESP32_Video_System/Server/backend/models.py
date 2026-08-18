from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone

class ESP32Camera(models.Model):
    # Links this camera directly to a specific user account
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cameras')
    
    # Automatically generates a secure, unique ID for the hardware
    device_id = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    
    # Allows the user to name their camera (e.g., "Front Porch")
    name = models.CharField(max_length=50, default="New Camera")
    
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.device_id}"


class VideoCapture(models.Model):
    # Links the video to the user (makes it easy to enforce the 10-video limit)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='videos')
    
    # Links the video to the specific camera that recorded it
    camera = models.ForeignKey(ESP32Camera, on_delete=models.CASCADE, related_name='captures')
    
    # Where the file is physically stored on the server's hard drive
    video_file = models.FileField(upload_to='videos/')
    
    # The exact date and time the video was uploaded
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # The flag for Enmanuel's "Safety Deposit Box" (True = permanent, False = deletes in 3 days)
    is_cloud_saved = models.BooleanField(default=False)

    def __str__(self):
        # Convert the internal UTC timestamp to your local Mountain Time
        local_time = timezone.localtime(self.timestamp)

        # Format it as: general182 - 08/16/2026 08:50 PM.mp4
        formatted_time = local_time.strftime('%m/%d/%Y-%I:%M-%p')
        return f"{self.user.username} - {formatted_time}.mp4"