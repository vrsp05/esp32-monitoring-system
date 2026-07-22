// This code simply opens a communication line to your computer
// and sends a single heartbeat message to prove it is alive.

void setup() {
  // 115200 is the "speed limit" for our serial communication
  Serial.begin(115200); 
  
  // Wait a brief moment for the connection to stabilize
  delay(1000); 
  
  // Send the heartbeat message to the computer
  Serial.println("Hello Lead Engineer, the ESP32 is awake and breathing!");
}

void loop() {
  // We leave the loop empty because we only need it to say hello once.
}