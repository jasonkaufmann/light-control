#include <WiFi.h>
#include <ArduinoOTA.h>
#include <ESP32Servo.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <esp_task_wdt.h>  // Include ESP32 hardware watchdog API

const char* ssid = "LadyWilldown";
const char* password = "Jjsting7";

Servo servoA;  
int pos = 90;

WebServer server(80);

// Watchdog variables
const char* serverUrl = "http://10.0.0.213:5069/status";
int failedChecks = 0;
const int maxFailedChecks = 5;
unsigned long lastCheckTime = 0;
const unsigned long checkInterval = 10000;

// -- GRACE PERIOD SETTINGS --
bool inGracePeriod = true;
const unsigned long gracePeriod = 2UL * 60UL * 1000UL; // 2 minutes
unsigned long bootTime;

// Wi-Fi Reconnect settings
unsigned long lastWiFiCheck = 0;
const unsigned long wifiCheckInterval = 30000; // Check Wi-Fi every 30s

void setup() {
  Serial.begin(115200);

  // Record the time the ESP boots
  bootTime = millis();

  // Start WiFi (non-blocking)
  WiFi.begin(ssid, password);
  Serial.println("Attempting to connect to WiFi...");

  // Start OTA
  ArduinoOTA.begin();
  Serial.println("OTA Ready");

  // Attach the servo and set its initial position
  servoA.attach(7);
  servoA.write(pos);

  // Define HTTP endpoints
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/plain", "ESP32 HTTP Server is online.");
  });

  server.on("/servo", HTTP_POST, []() {
    if (server.hasArg("position")) {
      pos = server.arg("position").toInt();
      if (pos == 0 || pos == 180) {
        servoA.write(pos);
        delay(450);
        servoA.write(90);
        server.send(200, "application/json",
                    "{\"success\": true, "
                    "\"message\": \"Servo moved to position: " +
                    String(pos) + "\"}");
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

  // Initialize the hardware watchdog with a 60-second timeout using the new API.
  // Note: Use "trigger_panic" instead of "panic"
  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = 60000,  // 60 seconds
    .idle_core_mask = 0,  // monitor both cores (adjust if needed)
    .trigger_panic = true
  };
  if (esp_task_wdt_init(&wdt_config) != ESP_OK) {
    Serial.println("Failed to initialize hardware watchdog");
  }
  // Add the current task (the main loop) to the watchdog.
  esp_task_wdt_add(NULL);
}

void loop() {
  ArduinoOTA.handle();
  server.handleClient();

  // Check Wi-Fi status and reconnect if needed
  if ((millis() - lastWiFiCheck) >= wifiCheckInterval) {
    lastWiFiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Wi-Fi not connected, attempting reconnect...");
      WiFi.disconnect();
      WiFi.begin(ssid, password);
    }
  }

  // End the grace period after the set time
  if (inGracePeriod && (millis() - bootTime >= gracePeriod)) {
    inGracePeriod = false;
  }

  // Perform status check to the server if Wi-Fi is connected and not in the grace period
  if (!inGracePeriod && WiFi.status() == WL_CONNECTED) {
    if (millis() - lastCheckTime >= checkInterval) {
      lastCheckTime = millis();

      HTTPClient http;
      http.begin(serverUrl);
      int httpCode = http.GET();

      if (httpCode == 200) {
        String payload = http.getString();
        Serial.println("Server status check successful: " + payload);
        failedChecks = 0;
      } else {
        failedChecks++;
        Serial.println("Failed to reach server. Attempt: " + String(failedChecks));

        if (failedChecks >= maxFailedChecks) {
          Serial.println("Max failed server checks reached. Rebooting...");
          ESP.restart();
        }
      }

      http.end();
    }
  }

  // Reset (feed) the hardware watchdog to prevent a reset if the loop is running properly
  esp_task_wdt_reset();

  delay(10);
}
