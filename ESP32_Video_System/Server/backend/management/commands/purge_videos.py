import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from backend.models import VideoCapture

class Command(BaseCommand):
    help = 'Deletes videos older than 3 days that are not saved to the cloud.'

    def handle(self, *args, **kwargs):
        # Calculate the exact time 72 hours ago
        three_days_ago = timezone.now() - timedelta(days=3)

        # Find all videos older than 3 days AND where is_cloud_saved is False
        expired_videos = VideoCapture.objects.filter(
            timestamp__lt=three_days_ago, 
            is_cloud_saved=False
        )

        deleted_count = 0

        for video in expired_videos:
            # 1. Delete the physical .mp4 file from the server's hard drive
            if video.video_file and os.path.isfile(video.video_file.path):
                os.remove(video.video_file.path)
            
            # 2. Delete the record from the database
            video.delete()
            deleted_count += 1

        # Print a success message to the server terminal
        self.stdout.write(self.style.SUCCESS(f'Successfully purged {deleted_count} expired videos.'))