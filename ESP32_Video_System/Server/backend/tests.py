import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from backend.models import ESP32Camera, VideoCapture

class AuthenticationTests(TestCase):
    def setUp(self):
        # This runs before every test to set up a clean environment
        self.client = Client()
        self.signup_url = '/api/signup/'
        self.login_url = '/api/login/'
        self.test_user = {
            "username": "test_engineer",
            "password": "securepassword123"
        }

    def test_user_signup_success(self):
        # Simulate a frontend POST request to sign up
        response = self.client.post(
            self.signup_url,
            json.dumps(self.test_user),
            content_type="application/json"
        )
        data = json.loads(response.content)
        
        # Verify the server created the account
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'success')
        self.assertTrue(User.objects.filter(username="test_engineer").exists())

    def test_duplicate_signup_blocked(self):
        # Create the user once
        User.objects.create_user(**self.test_user)
        
        # Try to create the exact same user again
        response = self.client.post(
            self.signup_url,
            json.dumps(self.test_user),
            content_type="application/json"
        )
        data = json.loads(response.content)
        
        # Verify the server correctly blocked it
        self.assertEqual(response.status_code, 400)
        self.assertEqual(data['status'], 'error')

    def test_user_login_success(self):
        # Create the user in the test database
        User.objects.create_user(**self.test_user)
        
        # Attempt to log in
        response = self.client.post(
            self.login_url,
            json.dumps(self.test_user),
            content_type="application/json"
        )
        data = json.loads(response.content)
        
        # Verify the login was successful and returned a device ID
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['username'], 'test_engineer')
        self.assertIn('device_id', data)

class VaultAndVideoTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a test user and a test camera
        self.user = User.objects.create_user(username="test_engineer", password="securepassword123")
        self.camera = ESP32Camera.objects.create(user=self.user, device_id="test-device-id")
        
        # Create a dummy video record in the test database
        self.video = VideoCapture.objects.create(
            user=self.user, 
            camera=self.camera,
            video_file="dummy_path.mp4"
        )

    def test_fetch_user_videos(self):
        # Simulate the dashboard asking for videos
        response = self.client.get('/api/videos/?user=test_engineer')
        data = json.loads(response.content)
        
        # Verify the server returns the video successfully
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['videos']), 1)
        self.assertFalse(data['videos'][0]['is_cloud_saved'])

    def test_save_to_vault_success(self):
        # Simulate clicking the "Save to Vault" button
        response = self.client.post(
            f'/api/vault/save/{self.video.id}/',
            json.dumps({"username": "test_engineer"}),
            content_type="application/json"
        )
        data = json.loads(response.content)
        
        # Verify the server accepted it and updated the database
        self.assertEqual(data['status'], 'success')
        self.video.refresh_from_db()
        self.assertTrue(self.video.is_cloud_saved)

    def test_vault_limit_enforced(self):
        # Manually create 10 already-saved videos to fill the vault
        for i in range(10):
            VideoCapture.objects.create(
                user=self.user, 
                camera=self.camera, 
                is_cloud_saved=True,
                video_file=f"dummy_{i}.mp4"
            )
        
        # Try to save the 11th video (the one created in setUp)
        response = self.client.post(
            f'/api/vault/save/{self.video.id}/',
            json.dumps({"username": "test_engineer"}),
            content_type="application/json"
        )
        data = json.loads(response.content)
        
        # Verify the server firmly rejects the request
        self.assertEqual(response.status_code, 400)
        self.assertIn("Vault is full", data['message'])