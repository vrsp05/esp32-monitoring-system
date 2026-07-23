#include "esp_camera.h"
#include "FS.h"
#include "SD_MMC.h"
#include "avi_stapler.h" // Our custom flipbook maker

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

File avi_file;

void setup() {
  Serial.begin(115200);
  delay(1000);

  // 1. OPEN THE BACKPACK
  // The 'true' at the end forces 1-bit mode, freeing Pin 4 and killing the flash!
  if (!SD_MMC.begin("/sdcard", true)) {
    Serial.println("ERROR: SD card failed to mount.");
    return;
  }
  
  // 2. WAKE UP THE EYE
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
  
  config.frame_size = FRAMESIZE_VGA; 
  config.pixel_format = PIXFORMAT_JPEG; 
  config.jpeg_quality = 12;
  config.fb_count = 2; // UPGRADE: 2 desks for faster processing!

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("ERROR: Camera failed to initialize.");
    return;
  }

  // 3. START THE MOVIE
  Serial.println("ACTION! Recording 20-second video...");
  
  avi_file = SD_MMC.open("/test_video.avi", FILE_WRITE);
  start_avi(avi_file); // Write the cover page
  
  unsigned long start_time = millis();
  int frames_recorded = 0;

  // 4. THE RECORDING LOOP (Run for exactly 20,000 milliseconds)
  while (millis() - start_time < 20000) {
    camera_fb_t * fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Dropped a frame!");
      continue;
    }

    // Glue the picture into the flipbook
    add_frame(avi_file, fb->buf, fb->len);
    frames_recorded++;

    esp_camera_fb_return(fb); // Clear the desk for the next photo
  }

  // 5. CUT! END THE MOVIE
  end_avi(avi_file, frames_recorded); 
  Serial.printf("CUT! Video saved. Total frames: %d\n", frames_recorded);
}

void loop() {
  // Empty
}