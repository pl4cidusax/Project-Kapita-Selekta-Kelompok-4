# Water Monitoring IoT (ESP32 + Flask)

Sistem **server–client** untuk memantau ketinggian air dan kondisi cahaya.
ESP32 (client) membaca sensor lalu mengirim data ke **server Flask** di komputer
melalui WiFi. Server menyimpan data ke SQLite dan menampilkan dashboard web.

```
  [ ESP32 + sensor ]  --WiFi/HTTP POST (JSON)-->  [ server.py / Flask ]
                                                        |
                                              SQLite + Dashboard web
```

## Daftar isi
1. Komponen
2. Pinout
3. Diagram & peringatan kabel (PENTING)
4. Persiapan server (Python)
5. Persiapan ESP32 (Arduino IDE)
6. Menjalankan & menguji
7. Kalibrasi
8. Troubleshooting
9. Struktur file
10. Alternatif (MQTT)

---

## 1. Komponen
- ESP32 DevKit V1 (DOIT, 30 pin) + kabel USB
- Sensor water level (3 pin: `S`, `+`, `-`)
- Sensor ultrasonik HC-SR04 (4 pin: `VCC`, `Trig`, `Echo`, `GND`)
- Modul LDR berbasis LM393 (4 pin: `AO`, `DO`, `GND`, `VCC`)
- 2 resistor untuk voltage divider Echo: **1 kΩ** dan **2 kΩ**
- Breadboard + kabel jumper
- Komputer untuk menjalankan server (1 jaringan WiFi dengan ESP32)

---

## 2. Pinout

| Sensor | Pin sensor | Pin ESP32 | Keterangan |
|---|---|---|---|
| Water level | `S` | **GPIO 34** | analog (ADC1, input-only) |
| Water level | `+` | **3V3** | **bukan 5V** (lihat §3) |
| Water level | `-` | **GND** | |
| HC-SR04 | `VCC` | **VIN (5V)** | butuh 5V agar stabil |
| HC-SR04 | `Trig` | **GPIO 18** | output |
| HC-SR04 | `Echo` | **GPIO 19** | **lewat voltage divider** |
| HC-SR04 | `GND` | **GND** | |
| LDR | `VCC` | **3V3** | |
| LDR | `GND` | **GND** | |
| LDR | `AO` | **GPIO 35** | analog (ADC1, input-only) |
| LDR | `DO` | **GPIO 23** | digital (HIGH/LOW) |

> Pin analog sengaja dipilih dari **ADC1** (GPIO 32–39). ADC2 (mis. GPIO 0, 2, 4,
> 12–15, 25–27) **tidak bisa dipakai analog saat WiFi aktif**, jadi hindari untuk sensor analog.

---

## 3. Diagram & peringatan kabel (PENTING)

### a) Voltage divider untuk Echo (wajib)
Pin `Echo` HC-SR04 mengeluarkan **5V**, sedangkan GPIO ESP32 hanya tahan **3.3V**.
Tanpa pembagi tegangan, GPIO bisa rusak. Pasang seperti ini:

```
HC-SR04 Echo ---[ R1 = 1kΩ ]---+---> ESP32 GPIO 19
                               |
                          [ R2 = 2kΩ ]
                               |
                              GND
```
Tegangan di titik tengah = 5V × 2k/(1k+2k) ≈ **3.3V**. GPIO 19 disambung ke titik
tengah (antara R1 dan R2). `Trig` (GPIO 18) tidak butuh divider karena itu output.

### b) Daya sensor water level → 3V3, jangan 5V
Output analog sensor water level ikut tegangan VCC-nya. Jika diberi 5V, sinyal `S`
bisa mendekati 5V dan melebihi batas ADC ESP32 (3.3V). Beri `+` dari **pin 3V3**.

### c) Common ground
Semua `GND` (ESP32, ketiga sensor, dan R2 divider) **harus tersambung jadi satu**.
Tanpa ground bersama, pembacaan akan kacau.

### d) Daya
HC-SR04 ambil 5V dari **VIN** (= 5V dari USB saat ESP32 ditenagai USB). Water level
dan LDR ambil dari **3V3**.

---

## 4. Persiapan server (Python)
Butuh Python 3.9+.

```bash
pip install flask          # atau: pip install -r requirements.txt
python server.py
```

Saat dijalankan, terminal mencetak sesuatu seperti:

```
Dashboard       : http://192.168.1.100:5000
Endpoint ESP32  : http://192.168.1.100:5000/api/data   <-- isi ke .ino
```

Catat alamat **Endpoint ESP32** itu — akan dimasukkan ke kode ESP32 (§5).
Data tersimpan otomatis di file `water_data.db` (SQLite) di folder yang sama.

---

## 5. Persiapan ESP32 (Arduino IDE)

1. **Pasang dukungan ESP32**: File → Preferences → *Additional Boards Manager URLs*,
   tambahkan: `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
   Lalu Tools → Board → *Boards Manager* → cari **esp32** → Install.
2. **Pilih board**: Tools → Board → **DOIT ESP32 DEVKIT V1**.
3. **Letakkan sketch**: taruh `water_monitor.ino` di dalam folder bernama
   `water_monitor` (Arduino mensyaratkan nama folder = nama file).
4. **Edit konfigurasi** di bagian atas `water_monitor.ino`:
   - `WIFI_SSID` dan `WIFI_PASSWORD` → kredensial WiFi Anda
   - `SERVER_URL` → alamat *Endpoint ESP32* dari langkah §4
   - `TANK_HEIGHT_CM` → jarak sensor ultrasonik ke dasar tangki saat kosong
5. **Upload**: pilih Port yang benar, lalu klik Upload. (Jika gagal masuk mode flash,
   tahan tombol **BOOT** saat "Connecting..." muncul.)

Tidak perlu library tambahan — `WiFi.h` dan `HTTPClient.h` sudah termasuk dalam core ESP32.

---

## 6. Menjalankan & menguji
1. Jalankan `python server.py` di komputer.
2. Nyalakan ESP32. Buka **Serial Monitor** (baud **115200**) — Anda akan melihat
   pembacaan sensor dan baris `POST -> HTTP 200`.
3. Buka alamat **Dashboard** di browser. Kartu data akan menyegar tiap 3 detik.

**Uji server tanpa ESP32** (opsional) — kirim data palsu dengan `curl`:

```bash
curl -X POST http://localhost:5000/api/data \
  -H "Content-Type: application/json" \
  -d '{"device_id":"test","distance_cm":12.0,"water_level_cm":18.0,"water_level_pct":60,"water_analog_raw":2300,"water_analog_pct":56,"ldr_raw":1500,"ldr_pct":36,"ldr_dark":false,"uptime_ms":1000}'
```

**Endpoint API**: `GET /api/latest` (data terbaru), `GET /api/history?limit=50` (riwayat).

---

## 7. Kalibrasi
- **Ultrasonik**: setel `TANK_HEIGHT_CM` sesuai tinggi tangki sebenarnya.
  `tinggi air = TANK_HEIGHT_CM − jarak`. Jika nilai aneh, cek divider Echo & jarak min HC-SR04 (~2 cm).
- **Water level (analog)**: nilai `0–4095` bersifat relatif, tidak linier.
  Catat nilai saat "kering" dan "penuh", lalu petakan ke persentase sesuai kebutuhan.
- **LDR**: putar potensiometer pada modul sampai `DO` berganti pada ambang cahaya
  yang diinginkan. Jika "gelap/terang" terbalik, ubah baris `ldrDark = (ldrDigital == HIGH)`
  di `.ino`.

> Tip umur sensor: sensor water level resistif cepat terkorosi bila terus dialiri arus.
> Untuk versi lanjutan, beri `+` dari sebuah GPIO dan nyalakan hanya saat membaca.

---

## 8. Troubleshooting
| Gejala | Kemungkinan penyebab / solusi |
|---|---|
| WiFi tidak konek | SSID/password salah; ESP32 hanya mendukung WiFi **2.4 GHz** (bukan 5 GHz) |
| `POST gagal` / connection refused | `SERVER_URL` salah; ESP32 & komputer beda jaringan; firewall memblok port 5000 |
| Dashboard kosong | Belum ada data masuk; cek Serial Monitor apakah ada `HTTP 200` |
| Jarak selalu `-1` | Kabel Trig/Echo tertukar; divider salah; objek terlalu dekat (<2 cm) |
| Nilai analog mentok / 0 | Ground tidak bersama; sensor diberi 5V (harusnya 3V3) |
| Komputer tak bisa diakses ESP32 | Izinkan Python di firewall, atau matikan firewall sementara untuk uji |

Cari IP komputer: Windows `ipconfig` (IPv4 Address) · macOS/Linux `ifconfig` atau `ip a`.

---

## 9. Struktur file
```
water_monitor/
  water_monitor.ino    # kode ESP32 (client)
server.py              # server Flask + dashboard
requirements.txt       # dependensi Python
README.md              # dokumen ini
water_data.db          # dibuat otomatis saat server jalan (SQLite)
```

---

## 10. Alternatif (MQTT)
Desain ini memakai HTTP karena paling sederhana dan andal. Untuk skala banyak device
atau real-time, alternatifnya adalah **MQTT**: ESP32 *publish* ke broker (mis. Mosquitto),
server *subscribe*. Itu menambah satu komponen (broker) dan library (`PubSubClient` di
ESP32). Beri tahu jika ingin versi MQTT-nya.
