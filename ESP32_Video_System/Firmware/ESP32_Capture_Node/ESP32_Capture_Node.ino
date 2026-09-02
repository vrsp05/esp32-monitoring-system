#include "esp_camera.h"
#include "FS.h"
#include "SD_MMC.h"
#include "avi_stapler.h" 
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include "time.h"
#include "driver/rtc_io.h"

// --- 1. NETWORK & DELIVERY CREDENTIALS ---
const char* ssid = "Internet Orange";
const char* password = "amamosrd";
const char* server_url = "http://vrsp-linux-server.tail0a3e2c.ts.net/upload/";

// Add your unique Device ID right here:
const String DEVICE_ID = "dadce4de-bc02-4807-b894-65080a6c627a";

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// --- TIMING CONSTANTS ---
#define uS_TO_S_FACTOR 1000000ULL  // Conversion factor for micro seconds to seconds
#define TIME_TO_SLEEP  900         // 15 minutes (900 seconds)

File avi_file;
QueueHandle_t frame_queue;
volatile bool is_recording = false;
int frames_recorded = 0;

// --- 3-BLINK SUCCESS SIGNAL ---
void signalSuccess() {
  for(int i = 0; i < 3; i++) {
    digitalWrite(4, HIGH);
    delay(150);
    digitalWrite(4, LOW);
    delay(150);
  }
}

void sd_writer_task(void *pvParameters) {
  camera_fb_t *fb;
  while (is_recording || uxQueueMessagesWaiting(frame_queue) > 0) {
    if (xQueueReceive(frame_queue, &fb, pdMS_TO_TICKS(10)) == pdPASS) {
      add_frame(avi_file, fb->buf, fb->len);
      frames_recorded++;
      esp_camera_fb_return(fb); 
    }
  }
  vTaskDelete(NULL);
}

void purgeOldVideos() {
  Serial.println("Checking SD Card Backpack Buffer for expired files...");
  time_t now;
  time(&now);

  File root = SD_MMC.open("/");
  File file = root.openNextFile();
  
  while (file) {
    if (!file.isDirectory()) {
      String fileName = file.name();
      if (fileName.endsWith(".avi")) {
        time_t fileTime = file.getLastWrite();
        double hoursOld = difftime(now, fileTime) / 3600.0;
        
        if (hoursOld > 72.0) {
          Serial.printf("Deleting expired file: %s (%.1f hours old)\n", fileName.c_str(), hoursOld);
          String filePath = "/" + fileName; 
          SD_MMC.remove(filePath.c_str());
        }
      }
    }
    file = root.openNextFile();
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  // --- 2. ISOLATE SD CARD PIN ---
  pinMode(4, OUTPUT);
  digitalWrite(4, LOW);

  // --- 3. MOUNT SD CARD ---
  if (!SD_MMC.begin("/sdcard", true, false, 20000)) { 
    Serial.println("CRITICAL ERROR: SD card failed to mount.");
    return;
  }

// --- 4. CONNECT TO WI-FI FIRST (Maximum Power Stress) ---
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to Local Wi-Fi...");
  
  int wifi_attempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifi_attempts < 40) { // 20-second timeout
    delay(500);
    Serial.print(".");
    wifi_attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nSUCCESS: Wi-Fi Connected!");
  } else {
    Serial.println("\nWARNING: Wi-Fi timed out. Proceeding in Offline Mode.");
  }

1// --- 4.5 SYNC REAL-WORLD TIME & PURGE ---
  if (WiFi.status() == WL_CONNECTED) {
    configTzTime("MST7MDT,M3.2.0,M11.1.0", "pool.ntp.org");
  }
  
  struct tm timeinfo;
  if (getLocalTime(&timeinfo, 10000)) {
    Serial.println("Time verified!");
  } else {
    Serial.println("WARNING: Failed to sync time.");
  }
  
  // Run the 72-hour hard drive sweep
  purgeOldVideos();

  // --- 5. INITIALIZE CAMERA (CIF @ 30 FPS) ---
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  
  config.xclk_freq_hz = 20000000;       
  config.frame_size = FRAMESIZE_CIF;   
  config.pixel_format = PIXFORMAT_JPEG; 
  config.jpeg_quality = 12;             
  config.fb_count = 5;                  

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("CRITICAL ERROR: Camera failed to initialize.");
    return;
  }

  sensor_t *s = esp_camera_sensor_get();
  s->set_exposure_ctrl(s, 1); 
  s->set_aec2(s, 1);          
  s->set_whitebal(s, 1);
  s->set_awb_gain(s, 1);
  s->set_wb_mode(s, 0);       

  frame_queue = xQueueCreate(4, sizeof(camera_fb_t *));

  // --- 6. RECORD THE VIDEO ---
  // Generate a unique file name based on the current time
  char dynamic_filename[64];
  strftime(dynamic_filename, sizeof(dynamic_filename), "/capture_%m-%d-%Y_%I-%M-%p.avi", &timeinfo);
  
  Serial.printf("ACTION! Recording 10-second video to %s...\n", dynamic_filename);
  
  avi_file = SD_MMC.open(dynamic_filename, FILE_WRITE); // Use the new string!
  start_avi(avi_file);
  
  is_recording = true;
  xTaskCreatePinnedToCore(sd_writer_task, "SD_Writer", 4096, NULL, 1, NULL, 0);

  unsigned long start_time = millis();
  unsigned long last_frame_time = 0;

  while (millis() - start_time < 10000) {
    if (millis() - last_frame_time >= 33) { 
      last_frame_time = millis();
      
      camera_fb_t * fb = esp_camera_fb_get();
      if (!fb) continue;

      if (xQueueSend(frame_queue, &fb, 0) != pdPASS) {
        esp_camera_fb_return(fb); 
      }
    }
  }

  is_recording = false; 
  while(uxQueueMessagesWaiting(frame_queue) > 0) { delay(10); }
  delay(100); 
  end_avi(avi_file, frames_recorded); 
  Serial.printf("CUT! Video saved. Total frames: %d\n", frames_recorded);

  // --- 7. HTTP POST TO DJANGO SERVER ---
  // Tell the server which dynamic file to upload
  if (WiFi.status() == WL_CONNECTED) {
    File uploadFile = SD_MMC.open(dynamic_filename, FILE_READ);
    if (!uploadFile) {
      Serial.println("ERROR: Could not open file for uploading.");
      return;
    }

    Serial.println("Starting HTTP POST Delivery to Home Server...");
    HTTPClient http;
    http.begin(server_url);
    
    http.addHeader("X-Device-ID", DEVICE_ID); 
    http.addHeader("Content-Type", "video/x-msvideo");
    
    int httpResponseCode = http.sendRequest("POST", &uploadFile, uploadFile.size());
    
    if (httpResponseCode > 0) {
      Serial.printf("HTTP Response code: %d\n", httpResponseCode);
      Serial.println("SUCCESS: Video delivered to Django!");
      signalSuccess(); 
    } else {
      Serial.printf("Error code: %d\n", httpResponseCode);
      Serial.println("FAILED: Could not deliver video.");
    }
    
    http.end();
    uploadFile.close();
  } else {
    Serial.println("Offline Mode: Upload skipped. Video buffered safely on SD card.");
  }

  // --- 8. INITIATE DEEP SLEEP ---
  Serial.println("Powering down system to prevent overheating.");
  Serial.println("Going to deep sleep for 15 minutes...");
  
  // Set the timer
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP * uS_TO_S_FACTOR);
  
  // Clear the serial buffer before shutting down
  Serial.flush(); 
  
  // Lock the flash LED pin LOW so it doesn't drain battery while sleeping
  pinMode(4, OUTPUT);
  digitalWrite(4, LOW);
  rtc_gpio_hold_en(GPIO_NUM_4); 

  // Cut the power
  esp_deep_sleep_start();
}

void loop() {
  // This will never be reached. The ESP32 reboots from scratch when it wakes up.
}