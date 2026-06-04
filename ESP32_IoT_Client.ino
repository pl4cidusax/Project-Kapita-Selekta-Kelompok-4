/*
 * Water Monitoring IoT - CLIENT (ESP32 DevKit V1)
 * ------------------------------------------------
 * Membaca 3 sensor lalu mengirim data JSON ke server Flask via WiFi (HTTP POST).
 *
 * Sensor:
 *   - Water level (S, +, -)  -> analog (resistif, berbasis kontak air)
 *   - HC-SR04 ultrasonik     -> jarak permukaan air (Trig/Echo)
 *   - LDR modul (AO/DO)      -> intensitas cahaya
 *
 * PENTING (lihat README):
 *   - Echo HC-SR04 keluar 5V -> WAJIB pakai voltage divider ke GPIO 19.
 *   - Beri + water sensor dari 3V3 (bukan 5V) supaya output analog <= 3.3V.
 *   - Semua GND harus terhubung jadi satu (common ground).
 *
 * Arduino IDE:
 *   Board  : "DOIT ESP32 DEVKIT V1"
 *   Letakkan file ini di folder bernama "water_monitor".
 */

#include <WiFi.h>
#include <HTTPClient.h>

// ============================ KONFIGURASI ============================
const char* WIFI_SSID     = "ditapao";
const char* WIFI_PASSWORD = "kepoparahh";

// Alamat endpoint server (lihat baris yang dicetak saat menjalankan server.py)
const char* SERVER_URL    = "http://172.20.10.2:5000/api/data";

const char* DEVICE_ID     = "esp32-water-01";

// Tinggi tangki = jarak dari sensor ultrasonik (di atas) ke dasar saat KOSONG.
const float TANK_HEIGHT_CM = 30.0f;

// Selang waktu kirim data (milidetik)
const unsigned long SEND_INTERVAL_MS = 5000;

// ============================ PIN MAP ===============================
const int PIN_WATER_ANALOG = 34;  // Water level "S"  (ADC1, input-only)
const int PIN_LDR_ANALOG   = 35;  // LDR "AO"         (ADC1, input-only)
const int PIN_LDR_DIGITAL  = 23;  // LDR "DO"
const int PIN_TRIG         = 18;  // HC-SR04 Trig
const int PIN_ECHO         = 19;  // HC-SR04 Echo (LEWAT VOLTAGE DIVIDER!)

const int ADC_MAX = 4095;         // resolusi 12-bit

unsigned long lastSend = 0;

// ---------------------------------------------------------- WiFi
void connectWiFi() {
  Serial.print("Menghubungkan ke WiFi \"");
  Serial.print(WIFI_SSID);
  Serial.print("\" ");
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("Terhubung. IP ESP32: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[!] Gagal terhubung. Cek SSID/password.");
  }
}

// ------------------------------------------------- Baca HC-SR04
// Mengembalikan jarak dalam cm, atau -1 jika tidak ada echo / di luar jangkauan.
float readDistanceCm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  // pulseIn: lama pulsa HIGH di Echo, timeout 30 ms (~5 meter)
  long duration = pulseIn(PIN_ECHO, HIGH, 30000UL);
  if (duration == 0) return -1.0f;

  // jarak = (durasi_us * 0.0343 cm/us) / 2  (bolak-balik)
  return (duration * 0.0343f) / 2.0f;
}

// ---------------------------------------------------------- Setup
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nWater Monitoring - ESP32 client");

  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_LDR_DIGITAL, INPUT);
  digitalWrite(PIN_TRIG, LOW);
  // Pin analog (34, 35) tidak perlu pinMode.

  analogReadResolution(12);   // 0..4095

  connectWiFi();
}

// ----------------------------------------------------------- Loop
void loop() {
  if (millis() - lastSend < SEND_INTERVAL_MS) return;
  lastSend = millis();

  // ---- Baca semua sensor ----
  float distance = readDistanceCm();

  float waterLevelCm  = -1.0f;
  float waterLevelPct = -1.0f;
  if (distance >= 0) {
    waterLevelCm = TANK_HEIGHT_CM - distance;
    if (waterLevelCm < 0) waterLevelCm = 0;
    if (waterLevelCm > TANK_HEIGHT_CM) waterLevelCm = TANK_HEIGHT_CM;
    waterLevelPct = (waterLevelCm / TANK_HEIGHT_CM) * 100.0f;
  }

  int   waterRaw    = analogRead(PIN_WATER_ANALOG);
  float waterRawPct = (waterRaw / (float)ADC_MAX) * 100.0f;

  int   ldrRaw     = analogRead(PIN_LDR_ANALOG);
  float ldrPct     = (ldrRaw / (float)ADC_MAX) * 100.0f;
  int   ldrDigital = digitalRead(PIN_LDR_DIGITAL);
  // Catatan: banyak modul -> DO LOW saat terang, HIGH saat gelap.
  // Jika terbalik di modul Anda, ubah baris berikut.
  bool  ldrDark = (ldrDigital == HIGH);

  // ---- Cetak ke Serial Monitor ----
  Serial.println("----- Pembacaan -----");
  Serial.printf("Jarak ultrasonik : %.1f cm\n", distance);
  Serial.printf("Tinggi air       : %.1f cm (%.0f%%)\n", waterLevelCm, waterLevelPct);
  Serial.printf("Water analog     : %d (%.0f%%)\n", waterRaw, waterRawPct);
  Serial.printf("LDR analog       : %d (%.0f%%)\n", ldrRaw, ldrPct);
  Serial.printf("LDR digital      : %s\n", ldrDark ? "gelap" : "terang");

  // ---- Kirim ke server ----
  if (WiFi.status() != WL_CONNECTED) connectWiFi();

  if (WiFi.status() == WL_CONNECTED) {
    char payload[384];
    snprintf(payload, sizeof(payload),
      "{"
        "\"device_id\":\"%s\","
        "\"distance_cm\":%.1f,"
        "\"water_level_cm\":%.1f,"
        "\"water_level_pct\":%.1f,"
        "\"water_analog_raw\":%d,"
        "\"water_analog_pct\":%.1f,"
        "\"ldr_raw\":%d,"
        "\"ldr_pct\":%.1f,"
        "\"ldr_dark\":%s,"
        "\"uptime_ms\":%lu"
      "}",
      DEVICE_ID, distance, waterLevelCm, waterLevelPct,
      waterRaw, waterRawPct, ldrRaw, ldrPct,
      ldrDark ? "true" : "false", millis());

    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    int code = http.POST((uint8_t*)payload, strlen(payload));
    if (code > 0) {
      Serial.printf("POST -> HTTP %d\n", code);
    } else {
      Serial.printf("POST gagal: %s\n", http.errorToString(code).c_str());
    }
    http.end();
  }
}
