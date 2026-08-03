#include "esp_camera.h"
#include "FS.h"
#include "SD_MMC.h"

// --- CAMERA PIN BLUEPRINT ---
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

void setup() {
  Serial.begin(115200);
  delay(1000);

  // 1. OPEN THE BACKPACK (SD CARD)
  if (!SD_MMC.begin()) {
    Serial.println("ERROR: SD card failed to mount.");
    return;
  }
  
  // 2. WAKE UP THE EYE (CAMERA)
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
  config.frame_size = FRAMESIZE_VGA; // Slightly larger resolution for our photo
  config.pixel_format = PIXFORMAT_JPEG; 
  config.jpeg_quality = 12;
  config.fb_count = 1;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("ERROR: Camera failed to initialize.");
    return;
  }

  // 3. TAKE THE PICTURE
  Serial.println("Taking a picture in 3 seconds... Smile!");
  delay(3000); // Give you time to point the camera at something
  
  camera_fb_t * fb = esp_camera_fb_get(); // "fb" stands for Frame Buffer (the picture)
  if (!fb) {
    Serial.println("ERROR: Camera failed to capture image.");
    return;
  }

  // 4. SAVE TO BACKPACK
  Serial.println("Picture taken! Saving to SD card...");
  File file = SD_MMC.open("/test_photo.jpg", FILE_WRITE);
  if (!file) {
    Serial.println("ERROR: Failed to open file on SD card.");
  } else {
    file.write(fb->buf, fb->len); // Push the image data into the file
    Serial.println("SUCCESS: Photo saved as test_photo.jpg!");
  }
  file.close();

  // Clean up memory so the ESP32 doesn't crash
  esp_camera_fb_return(fb); 
}

void loop() {
  // Empty
}