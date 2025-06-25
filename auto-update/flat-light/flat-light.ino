#include <WiFi.h>
#include <ArduinoOTA.h>
#include <ESP32Servo.h>
#include <Preferences.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <esp_task_wdt.h>  // Include ESP32 hardware watchdog API

/********** Wi-Fi Settings **********/
const char* ssid = "LadyWilldown";
const char* password = "Jjsting7";

// Non-blocking Wi-Fi reconnect settings
unsigned long lastWiFiCheck = 0;
const unsigned long wifiCheckInterval = 30000; // 30 seconds between Wi-Fi connection checks

/********** Grace Period Settings **********/
bool inGracePeriod = true;
const unsigned long gracePeriod = 2UL * 60UL * 1000UL; // 2 minutes to allow your server to fully boot
unsigned long bootTime = 0; // Will store the time the device started

/********** Servo & Light Control **********/
Servo servoA;          // Create a Servo object for servo A (pin 7)
int pos = 90;          // Default servo position
bool lightState = false; // Current state of the light

/********** HTTP Server **********/
WebServer server(80);  // Create an HTTP server on port 80

/********** Preferences **********/
Preferences preferences;

/********** GPIO2 Configuration (Button) **********/
const int gpioPin = 3;              // GPIO2 for button input
bool lastButtonState = HIGH;        // Last state of the GPIO pin (assuming pull-up, default HIGH)
unsigned long lastDebounceTime = 0; // Last time the pin state changed
const unsigned long debounceDelay = 50; // Debounce delay in milliseconds

/********** Watchdog for Server Status Check **********/
const char* serverUrl = "http://10.0.0.213:5069/status"; // Replace with your server's address
int failedChecks = 0;                 // Count of consecutive failed status checks
const int maxFailedChecks = 5;        // Reboot after 5 failed status checks
unsigned long lastCheckTime = 0;      // Last time a status check was performed
const unsigned long checkInterval = 10000; // Check server status every 10 seconds

/*******************************************************
 * Setup
 *******************************************************/
void setup() {
  Serial.begin(115200);

  // Record the boot time for the grace period
  bootTime = millis();

  // Initialize Preferences
  if (!preferences.begin("state", false)) {
    Serial.println("Failed to initialize Preferences");
  }
  // Load last saved light state
  lightState = preferences.getBool("lightState", false);

  // Start non-blocking Wi-Fi
  WiFi.begin(ssid, password);
  Serial.println("Attempting to connect to WiFi (non-blocking)...");

  // Start OTA
  ArduinoOTA.begin();
  Serial.println("OTA Ready");

  // Attach the servo to its respective pin and set initial position
  servoA.attach(7);
  servoA.write(90);

  // Configure GPIO2 as INPUT with internal pull-up resistor
  pinMode(gpioPin, INPUT_PULLUP);
  Serial.println("GPIO2 configured as INPUT with pull-up resistor");

  // Define HTTP endpoints
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/plain", "ESP32 HTTP Server is online.");
  });

  server.on("/servo", HTTP_POST, []() {
    if (server.hasArg("position")) {
      pos = server.arg("position").toInt();
      if (pos == 0 || pos == 180) {
        // Only toggle if there's an actual change
        if ((pos == 0 && lightState) || (pos == 180 && !lightState)) {
          toggleLight();
          server.send(200, "application/json", 
                      "{\"success\": true, "
                      "\"message\": \"Servo moved to position: " + String(pos) + "\"}");
        } else {
          server.send(200, "application/json", 
                      "{\"success\": false, "
                      "\"message\": \"Light is already in the desired state.\"}");
        }
      } else {
        server.send(400, "application/json", 
                    "{\"success\": false, "
                    "\"message\": \"Invalid position. Use 0 or 180.\"}");
      }
    } else {
      server.send(400, "application/json", 
                  "{\"success\": false, "
                  "\"message\": \"Missing position parameter.\"}");
    }
  });

  // Start the HTTP server
  server.begin();
  Serial.println("HTTP server started");

  // Initialize hardware watchdog with a 60-second timeout using the new API.
  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = 60000, // 60 seconds
    .idle_core_mask = 0,  // monitor both cores (adjust if needed)
    .trigger_panic = true
  };
  if (esp_task_wdt_init(&wdt_config) != ESP_OK) {
    Serial.println("Failed to initialize hardware watchdog");
  }
  // Add the current task (loop task) to the watchdog.
  esp_task_wdt_add(NULL);
}

/*******************************************************
 * Toggle Light Function
 *******************************************************/
void toggleLight() {
  lightState = !lightState;
  preferences.putBool("lightState", lightState);

  int targetPos = lightState ? 180 : 0;
  servoA.write(targetPos);
  delay(450);
  servoA.write(90); // Return to neutral position
  Serial.println("Light state toggled. New state: " + String(lightState ? "ON" : "OFF"));
}

/*******************************************************
 * Button Press Handler
 *******************************************************/
void handleButtonPress() {
  int buttonState = digitalRead(gpioPin);
  // If pressed (LOW) and different from last state:
  if (buttonState == LOW && lastButtonState == HIGH) {
    toggleLight();
    delay(1000);  // Small delay to avoid fast repeated toggles
  }
  lastButtonState = buttonState;
}

/*******************************************************
 * Main Loop
 *******************************************************/
void loop() {
  ArduinoOTA.handle();
  server.handleClient();
  handleButtonPress();

  // 1) Check and reconnect Wi-Fi if needed
  if (millis() - lastWiFiCheck >= wifiCheckInterval) {
    lastWiFiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Wi-Fi not connected, attempting reconnect...");
      WiFi.disconnect();
      WiFi.begin(ssid, password);
    }
  }

  // 2) End grace period after the set time
  if (inGracePeriod && (millis() - bootTime >= gracePeriod)) {
    inGracePeriod = false;
    Serial.println("Grace period ended. Server watchdog will now take effect.");
  }

  // 3) Server watchdog: Check server status if Wi-Fi is connected and not in grace period
  if (!inGracePeriod && WiFi.status() == WL_CONNECTED) {
    if (millis() - lastCheckTime >= checkInterval) {
      lastCheckTime = millis();
      HTTPClient http;
      http.begin(serverUrl);  // Begin connection to the server
      int httpCode = http.GET();  // Send GET request

      if (httpCode == 200) {  // HTTP 200 OK
        String payload = http.getString();
        Serial.println("Server status check successful: " + payload);
        failedChecks = 0;  // Reset failed check counter on success
      } else {
        failedChecks++;
        Serial.println("Failed to reach server. Attempt: " + String(failedChecks));
        if (failedChecks >= maxFailedChecks) {
          Serial.println("Max failed server checks reached. Rebooting...");
          ESP.restart();
        }
      }
      http.end();  // Close the connection
    }
  }

  // Reset (feed) the hardware watchdog to prevent reset if the loop is running properly
  esp_task_wdt_reset();

  delay(10);
}
