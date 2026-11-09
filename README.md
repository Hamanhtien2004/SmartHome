# 🏡 Local-First Smart Home, AI Face Recognition, Web Command Dashboard & Supabase

Hệ thống Nhà thông minh cục bộ (**Local-first Smart Home**) chuẩn công nghiệp, tích hợp **Trí tuệ nhân tạo Nhận diện khuôn mặt (CompreFace + Double-Take)**, **Bảng điều khiển & Giám sát Web Trực quan (Web Command Dashboard)** và **Cơ sở dữ liệu đám mây Supabase (PostgreSQL & Object Storage)**.

---

## 🌟 Điểm nổi bật & Cơ chế Chống xung đột (Zero Conflict Architecture)
1. **Hoạt động độc lập & Chống xung đột phần cứng (Hardware & Pin Integrity)**:
   - Tất cả chân GPIO trên các mạch ESP32 đều được quy hoạch độc lập, lọc nhiễu phần mềm (**debounce 50ms - 100ms**), không trùng lặp chân.
   - Công tắc cơ âm tường được xử lý trực tiếp tại **Edge ESP32**, giúp thiết bị hoạt động bình thường ngay cả khi mất Wi-Fi hay máy chủ bảo trì.
2. **Đồng bộ song song MQTT & Native API**:
   - ESPHome phát đồng thời qua Home Assistant Native API và Mosquitto MQTT, tránh xung đột dữ liệu giữa Home Assistant, Node-RED, Python Bot và Web Dashboard.
3. **Cơ chế chống dao động rơ-le (Hysteresis & Anti-Flapping)**:
   - Cảm biến nhiệt độ bật quạt tích hợp vùng đệm trễ ($30^\circ\text{C}$ bật, $\le 27^\circ\text{C}$ tắt), chống tình trạng relay quạt đóng ngắt liên tục.
   - Khóa chốt điện từ tự động ngắt sau xung kích 5 giây, bảo vệ cuộn hút không bị quá nhiệt.
4. **Bảng điều khiển & Giám sát Web độc lập (Web Management Dashboard)**:
   - Giao diện Web hiện đại (Cổng `5000`), tích hợp **Bộ giả lập kiểm thử phần cứng (Hardware Simulator)** cho phép kiểm tra mọi tính năng ngay cả khi chưa cắm thiết bị thật!
   - Kéo thanh trượt điều chỉnh độ nhạy radar, thời gian trễ tắt đèn, ngưỡng nhận diện khuôn mặt trực tiếp từ trình duyệt.

---

## 📑 Mục lục
1. [Kiến trúc hệ thống toàn diện](#-kiến-trúc-hệ-thống-toàn-diện)
2. [Cấu trúc thư mục dự án](#-cấu-trúc-thư-mục-dự-án)
3. [Giao diện Giám sát & Điều khiển (Web Dashboard & Lovelace)](#-giao-diện-giám-sát--điều-khiển)
4. [Cơ sở dữ liệu Supabase](#-cơ-sở-dữ-liệu-supabase)
5. [Sơ đồ chân phần cứng ESP32 & ESP32-CAM](#-sơ-đồ-chân-phần-cứng-esp32--esp32-cam)
6. [Cài đặt hạ tầng Docker](#-cài-đặt-hạ-tầng-docker)
7. [Chẩn đoán hệ thống & Kiểm thử](#-chẩn-đoán-hệ-thống--kiểm-thử)
8. [Bot Telegram & Mở khóa từ xa](#-bot-telegram--mở-khóa-từ-xa)
9. [Quản lý mã nguồn với Git & GitHub](#-quản-lý-mã-nguồn-với-git--github)

---

## 🏗 Kiến trúc hệ thống toàn diện

```text
                  +-------------------------------------------------------------+
                  |                 NGƯỜI DÙNG & QUẢN TRỊ VIÊN                  |
                  |  Web Dashboard (:5000) / Lovelace (:8123) / Telegram Bot   |
                  +------------------------------+------------------------------+
                                                 |
                   [REST / WS :5000]             |         [Telegram Bot API]
                                                 v
+-----------------------------------------------------------------------------------------------+
|                                 MÁY CHỦ CỤC BỘ (LOCAL SERVER)                                 |
|                                                                                               |
|  +---------------------+      +---------------------+      +-------------------------------+  |
|  | Web Admin Dashboard |<---->|   Mosquitto MQTT    |<---->| Double-Take & CompreFace AI   |  |
|  |     (Port 5000)     |      |   (Port 1883, 9001) |      | (InsightFace Deep Neural Net) |  |
|  +---------------------+      +----------+----------+      +---------------+---------------+  |
|                                          |                                 |                  |
|                                          v                                 v                  |
|  +---------------------+      +---------------------+                      |                  |
|  |   Home Assistant    |<---->|  Node-RED Flow Hub  |                      |                  |
|  |     (Port 8123)     |      |     (Port 1880)     |                      |                  |
|  +----------+----------+      +---------------------+                      |                  |
+-------------|--------------------------------------------------------------|------------------+
              |                                                              |
              | (Sync Events & Snapshots)                                    | (Wi-Fi / MQTT / API)
              v                                                              v
+---------------------------+      +------------------------------------------------------------+
|    SUPABASE CLOUD DB      |      |                   CÁC PHÂN HỆ PHẦN CỨNG                    |
| - Tables:                 |      |                                                            |
|   family_members          |      |  1. Chuông cửa AI (ESP32-CAM):                             |
|   access_logs             |      |     - Camera OV2640 MJPEG (Port 8080) & Snapshot (:8081)   |
|   security_alerts         |      |     - Đèn Flash ban đêm & Nút chuông cửa GPIO13            |
|   devices, telemetry      |      |     - Rơ-le kích mở chốt cửa GPIO12                        |
| - Storage:                |      |                                                            |
|   security-snapshots      |      |  2. Khối Rơ-le Phòng khách (ESP32 DevKit):                 |
+---------------------------+      |     - 4 Rơ-le đèn, quạt & 4 công tắc cơ âm tường           |
                                   |     - Rơ-le khóa chốt điện từ GPIO23 (xung 5s an toàn)     |
                                   |     - Cảm biến má từ phát hiện đóng/mở cửa GPIO27          |
                                   |                                                            |
                                   |  3. Khối Cảm biến & Radar (ESP32 Bedroom):                 |
                                   |     - Cảm biến nhiệt ẩm DHT22 GPIO4                        |
                                   |     - Radar vi sóng mmWave 24GHz HLK-LD2410 (UART 256000)  |
                                   +------------------------------------------------------------+
```

---

## 📂 Cấu trúc thư mục dự án

```text
SmartHome/
├── docker-compose.yml                      # Triển khai HA, MQTT, Web Dashboard, Node-RED, CompreFace, Double-Take
├── .env.example                            # Mẫu biến môi trường (Telegram, Supabase, Token)
├── .gitignore                              # Chống lộ secret, db cache và credential
├── README.md                               # Hướng dẫn kỹ thuật toàn diện
├── web_dashboard/
│   ├── server.py                           # Máy chủ Dashboard quản lý, điều khiển và giả lập thiết bị (Port 5000)
│   └── index.html                          # Giao diện Glassmorphism giám sát & kéo slider chỉnh tham số
├── supabase/
│   └── schema.sql                          # DDL khởi tạo toàn bộ Table, Policy RLS, Storage Bucket
├── double-take_data/
│   └── config.yml                          # Cấu hình đối soát nhận diện camera với CompreFace
├── ha_config/
│   ├── configuration.yaml                  # Cấu hình Camera, Lock template, MQTT sensor, Input Helpers
│   ├── automations.yaml                    # Tự động mở cửa khi khớp mặt, tắt đèn theo trễ động
│   ├── ui-lovelace.yaml                    # Dashboard Kiosk Lovelace 5 Tab chuyên nghiệp
│   ├── scripts.yaml
│   └── scenes.yaml
├── esphome_nodes/
│   ├── esp32_cam_doorbell.yaml             # Firmware ESP32-CAM chuông cửa & rơ-le khóa
│   ├── esp32_livingroom_relay.yaml         # Firmware ESP32 4 rơ-le + Khóa từ + Cảm biến má cửa
│   └── esp32_bedroom_sensor.yaml           # Firmware ESP32 DHT22 + Radar mmWave LD2410
├── custom_scripts/
│   ├── system_health_check.py              # Script tự động kiểm tra cú pháp, xung đột chân GPIO & MQTT
│   ├── telegram_alert_bot.py               # Bot cảnh báo người lạ kèm ảnh & nút bấm mở cửa
│   ├── supabase_client.py                  # Module đồng bộ dữ liệu & upload ảnh lên Supabase
│   └── requirements.txt                    # Danh sách thư viện Python
├── mosquitto/
│   └── config/mosquitto.conf
└── zigbee2mqtt/
    └── data/configuration.yaml.example
```

---

## 🖥 Giao diện Giám sát & Điều khiển

Hệ thống cung cấp **2 giao diện song song**:

### 1. Web Management Dashboard độc lập (`http://localhost:5000`)
- **Khởi chạy trực tiếp**:
  ```bash
  python web_dashboard/server.py
  ```
  *(Hoặc chạy qua container `web-dashboard` trong Docker Compose)*.
- **Tính năng chính**:
  1. **Tab Giám sát & Điều khiển**: Trực quan hóa trạng thái rơ-le, khóa cửa, nhiệt độ, độ ẩm và radar. Nút bấm bật/tắt thiết bị tức thì.
  2. **Tab Tinh chỉnh Tham số**: Cho phép kéo thanh trượt thay đổi:
     - Ngưỡng tin cậy Face ID (50% - 98%).
     - Thời gian trễ tắt đèn vắng người (1 - 30 phút).
     - Nhiệt độ bật quạt ($26 - 36^\circ\text{C}$) và tắt quạt ($20 - 28^\circ\text{C}$).
     - Thời gian mở chốt cửa (2 - 15 giây).
     - Giãn cách chống spam tin nhắn Telegram (10 - 120 giây).
  3. **Tab Giả lập Thiết bị (Hardware Simulator)**:
     - Nút thử nghiệm: Nhận diện người nhà (Khớp 94.5%) -> Tự động kích hoạt mở khóa.
     - Nút thử nghiệm: Người lạ trước cửa (<50%) -> Gửi cảnh báo khẩn Telegram.
     - Nút thử nghiệm: Bấm chuông cửa.
     - Nút thử nghiệm: Chuyển động radar & Nhiệt độ phòng tăng cao (32.5°C).
  4. **Tab Nhật ký Ra vào**: Xem lịch sử mở cửa và cảnh báo từ Supabase Database.

### 2. Lovelace Dashboard trên Home Assistant (`http://localhost:8123`)
- Tích hợp 5 View chuyên dụng:
  - **View 1: Tổng quan (Overview Kiosk)**: Điều khiển nhanh đèn, quạt, khóa, an ninh.
  - **View 2: Chỉnh sửa Cấu hình (Settings)**: Bảng slider tinh chỉnh tham số trực tiếp.
  - **View 3: Kiểm soát Ra vào (Access Control)**: Trực tiếp Camera chuông cửa và danh sách thành viên.
  - **View 4: Cảm biến & Radar (Sensors)**: Biểu đồ gauge nhiệt ẩm và thông số radar mmWave.
  - **View 5: Trạng thái Thiết bị (System Health)**: Kiểm tra trạng thái Online/Offline của từng node ESP32.

---

## 🩺 Chẩn đoán hệ thống & Kiểm thử

Trước khi đấu nối dây điện hoặc đưa vào thực tế, bạn có thể chạy công cụ tự động kiểm tra:

```bash
python custom_scripts/system_health_check.py
```

Công cụ sẽ tự động rà soát:
- [x] Kiểm tra cú pháp toàn bộ tệp YAML (`docker-compose`, `ha_config`, `esphome_nodes`).
- [x] Rà soát xung đột chân GPIO trên từng bo mạch ESP32.
- [x] Kiểm tra tính nhất quán của Topic MQTT giữa ESPHome và Home Assistant.

---

## 🗄 Cơ sở dữ liệu Supabase

File khởi tạo cơ sở dữ liệu: [`supabase/schema.sql`](file:///d:/SmartHome/supabase/schema.sql)

### Các bước cài đặt Supabase:
1. Đăng nhập [supabase.com](https://supabase.com) -> Tạo Project mới.
2. Mở mục **SQL Editor** -> Dán toàn bộ file `supabase/schema.sql` -> Nhấn **Run**.
3. Điền `SUPABASE_URL` và `SUPABASE_KEY` vào file `.env`.

---

## 🚀 Khởi động toàn bộ cụm Docker

```bash
# Tạo file .env từ mẫu
cp .env.example .env

# Khởi chạy tất cả 10 dịch vụ
docker compose up -d

# Xem trạng thái
docker compose ps
```

### Bảng cổng dịch vụ
| Dịch vụ | Cổng truy cập | Chức năng |
| :--- | :--- | :--- |
| **Web Command Dashboard** | `http://localhost:5000` | Giám sát, tinh chỉnh tham số & giả lập |
| **Home Assistant** | `http://localhost:8123` | Bảng điều khiển trung tâm & Kiosk UI |
| **CompreFace Web Admin** | `http://localhost:8000` | Huấn luyện ảnh khuôn mặt gia đình |
| **Double-Take Console** | `http://localhost:3000` | Đối soát hình ảnh camera |
| **ESPHome Web** | `http://localhost:6052` | Biên dịch & nạp firmware qua web/OTA |
| **Node-RED** | `http://localhost:1880` | Thiết kế kịch bản kéo thả |
| **Mosquitto MQTT** | `1883`, `9001` | Trạm trung chuyển tin nhắn |

---

## 📦 Quản lý mã nguồn với Git & GitHub

```bash
git add .
git commit -m "feat: complete zero-conflict hardware architecture, standalone web management dashboard, and parameter tuning engine"
git push -u origin main
```
