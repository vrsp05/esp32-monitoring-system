from django.core.management.base import BaseCommand
from backend.models import VideoCapture
from django.utils import timezone
from datetime import timedelta
import os

class Command(BaseCommand):
    help = 'Deletes videos older than 24 hours that are not saved to the Cloud Vault'

    def handle(self, *args, **kwargs):
        # 1. Calculate the exact time 24 hours ago
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        # 2. Find videos older than the cutoff that are NOT cloud saved
        old_videos = VideoCapture.objects.filter(timestamp__lt=cutoff_time, is_cloud_saved=False)
        
        if not old_videos.exists():
            self.stdout.write(self.style.WARNING('No old videos found to clean up.'))
            return

        deleted_count = 0
        for video in old_videos:
            # 3. Delete the physical .mp4 file from the hard drive
            if video.video_file and os.path.isfile(video.video_file.path):
                os.remove(video.video_file.path)
            
            # 4. Delete the record from the database
            video.delete()
            deleted_count += 1
            
        # Print a success message to the terminal
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted_count} temporary videos.'))