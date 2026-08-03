#include "FS.h"
#include "SD_MMC.h"

void setup() {
  Serial.begin(115200);
  // Wait a brief moment for the connection to stabilize
  delay(1000); 

  Serial.println("Opening the backpack...");

  // Try to connect to the SD card
  if (!SD_MMC.begin()) {
    Serial.println("CRITICAL ERROR: Failed to mount SD card. Check if it is inserted properly.");
    return;
  }

  // Check if a card is actually inside the slot
  uint8_t cardType = SD_MMC.cardType();
  if (cardType == CARD_NONE) {
    Serial.println("ERROR: No SD card attached.");
    return;
  }

  Serial.println("SUCCESS: The SD card is mounted and ready for video!");
}

void loop() {
  // Empty loop for now
}