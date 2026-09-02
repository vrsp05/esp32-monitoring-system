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

class MiniSentinelSecurityTests(TestCase):
    def setUp(self):
        # This runs before every test to set up a clean, isolated database
        self.client = Client()
        self.test_user = User.objects.create_user(username="general182", password="validpassword123")
        self.camera = ESP32Camera.objects.create(user=self.test_user, device_id="fake-uuid-5678")

    def test_signup_short_password(self):
        response = self.client.post('/api/signup/', json.dumps({
            'username': 'newuser',
            'password': '123'
        }), content_type='application/json')
        
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('at least 5 characters', data['message'])

    def test_signup_duplicate_username(self):
        response = self.client.post('/api/signup/', json.dumps({
            'username': 'general182',
            'password': 'newpassword123'
        }), content_type='application/json')
        
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('already taken', data['message'])

    def test_login_success_and_camera_fetch(self):
        response = self.client.post('/api/login/', json.dumps({
            'username': 'general182',
            'password': 'validpassword123'
        }), content_type='application/json')
        
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['device_id'], 'fake-uuid-5678')

class DeviceManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.test_user = User.objects.create_user(username="general182", password="validpassword123")

    def test_device_creation_and_limit(self):
        # 1. Create the first 3 devices (Should Succeed)
        for i in range(3):
            response = self.client.post('/api/camera/create/', json.dumps({
                'username': 'general182'
            }), content_type='application/json')
            self.assertEqual(response.status_code, 200)

        # 2. Attempt to create a 4th device (Should Fail)
        response_fail = self.client.post('/api/camera/create/', json.dumps({
            'username': 'general182'
        }), content_type='application/json')
        
        data = response_fail.json()
        self.assertEqual(response_fail.status_code, 400)
        self.assertIn('Maximum of 3 devices allowed', data['message'])

    def test_get_devices_list(self):
        # Manually create a test device
        ESP32Camera.objects.create(user=self.test_user, device_id="fake-uuid-123", name="Camera 1")
        
        response = self.client.get('/api/devices/?user=general182')
        data = response.json()
        
        # Verify the API returns exactly 1 device with the correct generated data
        self.assertEqual(len(data['devices']), 1)
        self.assertEqual(data['devices'][0]['name'], 'Camera 1')
        self.assertEqual(data['devices'][0]['video_count'], 0)

    def test_delete_device_security(self):
        # Create a device to delete
        camera = ESP32Camera.objects.create(user=self.test_user, device_id="delete-me-uuid")
        
        response = self.client.post(f'/api/camera/delete/{camera.id}/', json.dumps({
            'username': 'general182'
        }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the database is actually empty
        self.assertEqual(ESP32Camera.objects.count(), 0)