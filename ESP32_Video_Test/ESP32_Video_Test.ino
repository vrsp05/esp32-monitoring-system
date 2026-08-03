#include "esp_camera.h"
#include "FS.h"
#include "SD_MMC.h"
#include "avi_stapler.h" 
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

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

File avi_file;

QueueHandle_t frame_queue;
volatile bool is_recording = false;
int frames_recorded = 0;

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

void setup() {
  Serial.begin(115200);
  delay(1000);

  // PIN 4 ISOLATION (Kills SD card interference)
  pinMode(4, OUTPUT);
  digitalWrite(4, LOW);

  // EMI FIX: 20MHz SD bus speed in 1-Bit mode ('true')
  if (!SD_MMC.begin("/sdcard", true, false, 20000)) { 
    Serial.println("CRITICAL ERROR: SD card failed to mount.");
    return;
  }
  if (SD_MMC.cardType() == CARD_NONE) {
    Serial.println("CRITICAL ERROR: No SD card inserted!");
    return;
  }

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
  
  // THE 30 FPS HARDWARE TUNE
  config.xclk_freq_hz = 20000000;       // 20MHz native clock required for 30 FPS
  config.frame_size = FRAMESIZE_QVGA;   // 320x240 Resolution
  config.pixel_format = PIXFORMAT_JPEG; 
  config.jpeg_quality = 12;             // High Quality
  config.fb_count = 5;                  // 5 PSRAM Desks

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

  Serial.println("ACTION! Recording 20-second 30 FPS video...");
  
  avi_file = SD_MMC.open("/test_video.avi", FILE_WRITE);
  start_avi(avi_file);
  
  is_recording = true;

  xTaskCreatePinnedToCore(
    sd_writer_task,   
    "SD_Writer",      
    4096,             
    NULL,             
    1,                
    NULL,             
    0                 
  );

  unsigned long start_time = millis();
  unsigned long last_frame_time = 0;

  while (millis() - start_time < 20000) {
    // 33 milliseconds = 30 Frames Per Second Metronome
    if (millis() - last_frame_time >= 33) { 
      last_frame_time = millis();
      
      camera_fb_t * fb = esp_camera_fb_get();
      if (!fb) {
        Serial.println("Camera skipped a beat!");
        continue;
      }

      if (xQueueSend(frame_queue, &fb, 0) != pdPASS) {
        Serial.println("WARNING: Conveyor belt backed up! Dropping frame.");
        esp_camera_fb_return(fb); 
      }
    }
  }

  is_recording = false; 

  Serial.println("Recording finished. Waiting for Core 0 to archive final frames...");
  
  while(uxQueueMessagesWaiting(frame_queue) > 0) {
    delay(10);
  }
  delay(100); 

  end_avi(avi_file, frames_recorded); 
  Serial.printf("CUT! Video successfully processed on Dual Cores. Total frames: %d\n", frames_recorded);
}

void loop() {
}