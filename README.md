# 🏡 Local-First Smart Home, AI Face Recognition & Supabase System

Hệ thống Nhà thông minh cục bộ (**Local-first Smart Home**) tích hợp **Trí tuệ nhân tạo Nhận diện khuôn mặt (CompreFace + Double-Take)** và **Cơ sở dữ liệu đám mây Supabase (PostgreSQL & Object Storage)**.

Hệ thống đảm bảo:
- **Tốc độ siêu nhanh & bảo mật nội bộ**: Xử lý nhận diện khuôn mặt và điều khiển rơ-le khóa cửa 100% tại máy chủ cục bộ trong mạng LAN.
- **Đồng bộ sự kiện ra vào & cảnh báo lên Supabase**: Lưu trữ lịch sử ra vào số, ảnh chụp người lạ đột nhập lên Supabase Storage.
- **Tương tác 2 chiều qua Telegram Bot**: Xem ảnh camera tức thì, bấm nút mở khóa từ xa trực tiếp trên tin nhắn.

---

## 📑 Mục lục
1. [Kiến trúc hệ thống toàn diện](#-kiến-trúc-hệ-thống-toàn-diện)
2. [Cấu trúc thư mục dự án](#-cấu-trúc-thư-mục-dự-án)
3. [Cơ sở dữ liệu Supabase](#-cơ-sở-dữ-liệu-supabase)
4. [Sơ đồ chân phần cứng ESP32 & ESP32-CAM](#-sơ-đồ-chân-phần-cứng-esp32--esp32-cam)
5. [Cài đặt hạ tầng Docker](#-cài-đặt-hạ-tầng-docker)
6. [Cấu hình AI Nhận diện khuôn mặt (CompreFace & Double-Take)](#-cấu-hình-ai-nhận-diện-khuôn-mặt)
7. [Nạp Firmware cho các Node ESPHome](#-nạp-firmware-cho-các-node-esphome)
8. [Bot Telegram & Mở khóa từ xa](#-bot-telegram--mở-khóa-từ-xa)
9. [Quản lý mã nguồn với Git & GitHub](#-quản-lý-mã-nguồn-với-git--github)

---

## 🏗 Kiến trúc hệ thống toàn diện

```text
                  +----------------------------------------------+
                  |         NGƯỜI DÙNG & QUẢN TRỊ VIÊN           |
                  |   Lovelace Kiosk / Telegram Bot / Web Supabase|
                  +-----------------------+----------------------+
                                          |
                [HTTP :8123]              |          [Telegram Bot API]
                                          v
+-----------------------------------------------------------------------------------+
|                           MÁY CHỦ CỤC BỘ (LOCAL SERVER)                           |
|                                                                                   |
|  +------------------+         +---------------------+      +-------------------+  |
|  |  Home Assistant  |<------->|    Mosquitto MQTT   |<---->|  Double-Take Hub  |  |
|  |    (Core Hub)    | WebSocket|   (Local Message)   |      | (Face Aggregator) |  |
|  +--------+---------+         +----------+----------+      +---------+---------+  |
|           |                              |                           |            |
|           |                              |                           v            |
|           |                              |                 +-------------------+  |
|           |                              |                 |  CompreFace AI    |  |
|           |                              |                 | (Deep Neural Net) |  |
|           |                              |                 +-------------------+  |
|           v                              v                                        |
|  +------------------+                    |                                        |
|  |  Node-RED Flow   |                    |                                        |
|  +------------------+                    |                                        |
+-----------+------------------------------+----------------------------------------+
            |                              |
            | (Sync Events & Snapshots)    | (Wi-Fi / ESPHome Native API)
            v                              v
+-----------------------+      +----------------------------------------------------+
|  SUPABASE CLOUD DB    |      |                CÁC PHÂN HỆ PHẦN CỨNG               |
| - Postgres Tables:    |      |                                                    |
|   access_logs         |      |  1. Chuông cửa AI (ESP32-CAM):                     |
|   security_alerts     |      |     - Camera OV2640 MJPEG Stream                   |
|   family_members      |      |     - Đèn Flash chiếu sáng ban đêm & Nút chuông    |
|   sensor_telemetry    |      |                                                    |
| - Storage Bucket:     |      |  2. Khối Rơ-le & Khóa từ (ESP32 Livingroom):       |
|   security-snapshots  |      |     - Khóa chốt điện từ Drop-Bolt/Magnetic         |
+-----------------------+      |     - 4 Kênh rơ-le đèn, quạt & 4 công tắc âm tường |
                               |     - Cảm biến má từ phát hiện đóng/mở cửa         |
                               |                                                    |
                               |  3. Khối Cảm biến & Radar (ESP32 Bedroom):         |
                               |     - Cảm biến nhiệt ẩm DHT22                      |
                               |     - Radar vi sóng mmWave 24GHz HLK-LD2410        |
                               +----------------------------------------------------+
```

---

## 📂 Cấu trúc thư mục dự án

```text
SmartHome/
├── docker-compose.yml                      # Triển khai HA, MQTT, Z2M, Node-RED, ESPHome, CompreFace, Double-Take
├── .env.example                            # Mẫu biến môi trường (Telegram, Supabase, Token)
├── .gitignore                              # Chống lộ secret, db cache và credential
├── README.md                               # Hướng dẫn kỹ thuật toàn diện
├── supabase/
│   └── schema.sql                          # DDL khởi tạo toàn bộ Table, Policy RLS, Storage Bucket
├── double-take_data/
│   └── config.yml                          # Cấu hình đối soát nhận diện camera với CompreFace
├── ha_config/
│   ├── configuration.yaml                  # Cấu hình Camera, Lock template, MQTT sensor
│   ├── automations.yaml                    # Tự động mở cửa khi khớp mặt, cảnh báo người lạ
│   ├── ui-lovelace.yaml                    # Dashboard Kiosk: Live Camera, Khóa cửa, Biểu đồ 24h
│   ├── scripts.yaml
│   └── scenes.yaml
├── esphome_nodes/
│   ├── esp32_cam_doorbell.yaml             # Firmware ESP32-CAM chuông cửa & rơ-le khóa
│   ├── esp32_livingroom_relay.yaml         # Firmware ESP32 4 rơ-le + Khóa từ + Cảm biến má cửa
│   └── esp32_bedroom_sensor.yaml           # Firmware ESP32 DHT22 + Radar mmWave LD2410
├── custom_scripts/
│   ├── telegram_alert_bot.py               # Bot cảnh báo người lạ kèm ảnh & nút bấm mở cửa
│   ├── supabase_client.py                  # Module đồng bộ dữ liệu & upload ảnh lên Supabase
│   └── requirements.txt                    # Danh sách thư viện Python
├── mosquitto/
│   └── config/mosquitto.conf
└── zigbee2mqtt/
    └── data/configuration.yaml.example
```

---

## 🗄 Cơ sở dữ liệu Supabase

File khởi tạo cơ sở dữ liệu nằm tại: [`supabase/schema.sql`](file:///d:/SmartHome/supabase/schema.sql)

### 1. Danh sách bảng dữ liệu
1. **`family_members`**: Lưu danh sách thành viên gia đình, `face_id` (CompreFace), phòng được phép mở, nhiệt độ máy lạnh yêu thích (`preferred_temp`).
2. **`devices`**: Danh mục toàn bộ mạch ESP32, rơ-le, radar, camera và trạng thái kết nối.
3. **`access_logs`**: Nhật ký thời gian thực mỗi lần mở cửa/vào phòng (Tên người, Tỉ lệ khớp %, Phương thức mở, Link ảnh snapshot).
4. **`security_alerts`**: Lưu vết cảnh báo người lạ lảng vảng trước cửa, đột nhập khi vắng nhà.
5. **`sensor_telemetry`**: Lịch sử thông số nhiệt độ, độ ẩm và tọa độ radar mmWave.

### 2. Cấu hình Storage Bucket
- Bucket name: `security-snapshots` (chế độ Public hoặc Authenticated).
- Tự động lưu trữ hình ảnh người bấm chuông, người lạ hoặc ảnh thành viên xác thực lúc mở cửa.

### 3. Cách khởi tạo trên Supabase
1. Đăng nhập [supabase.com](https://supabase.com) -> Tạo Project mới.
2. Mở mục **SQL Editor** -> Dán nội dung tệp [`supabase/schema.sql`](file:///d:/SmartHome/supabase/schema.sql) -> Bấm **Run**.
3. Vào **Settings** -> **API**: Sao chép `Project URL` và `anon / service_role key` điền vào file `.env`.

---

## 🔌 Sơ đồ chân phần cứng ESP32 & ESP32-CAM

### 1. Chuông cửa AI Camera: ESP32-CAM OV2640 (`esp32_cam_doorbell.yaml`)
| Chân ESP32-CAM | Ngoại vi kết nối | Mô tả chức năng |
| :--- | :--- | :--- |
| **GPIO0 / GPIO16 / ...** | Cảm biến camera OV2640 | Cụm chân camera cố định trên mạch |
| **GPIO4** | Đèn Flash LED công suất cao | Bật sáng chiếu khuôn mặt ban đêm |
| **GPIO13** | Nút bấm chuông cửa (kéo xuống GND) | Kích hoạt chuông cửa & lệnh quét mặt |
| **GPIO12** | Rơ-le Khóa chốt điện (Pulse 5s) | Kích mở chốt khóa cửa trực tiếp |
| **5V (2A)** | Nguồn DC 5V ổn định | Cấp nguồn cho bo mạch và camera |
| **GND** | Mass chung | Nối đất |

### 2. Rơ-le Phòng khách & Khóa từ Cửa chính (`esp32_livingroom_relay.yaml`)
| Chân ESP32 | Thiết bị ngoại vi | Chức năng |
| :--- | :--- | :--- |
| **GPIO16** | Relay 1 (Đèn chính) | Bật/tắt đèn trần phòng khách |
| **GPIO17** | Relay 2 (Đèn viền) | Bật đèn đón tiếp khi mở cửa |
| **GPIO18** | Relay 3 (Quạt) | Bật quạt theo nhiệt độ DHT22 |
| **GPIO19** | Relay 4 (Ổ cắm phụ) | Còi báo động an ninh |
| **GPIO23** | Relay Khóa chốt điện từ | Kích mở khóa cửa (xung 5 giây) |
| **GPIO27** | Cảm biến từ má cửa (Reed switch) | Báo trạng thái cửa Đang Đóng hay Mở |
| **GPIO32, 33, 25, 26**| 4 Công tắc cơ âm tường | Điều khiển trực tiếp đèn/quạt tại chỗ |

---

## 🚀 Cài đặt hạ tầng Docker

Khởi chạy đồng thời toàn bộ 9 container (HA, MQTT, Z2M, Node-RED, ESPHome, Double-Take, CompreFace UI, API, Core & Postgres):

```bash
# 1. Tạo file cấu hình môi trường
cp .env.example .env

# 2. Khởi chạy toàn bộ hệ thống
docker compose up -d

# 3. Kiểm tra danh sách container
docker compose ps
```

### Bảng cổng dịch vụ
| Dịch vụ | Cổng truy cập | Chức năng |
| :--- | :--- | :--- |
| **Home Assistant** | `http://localhost:8123` | Bảng điều khiển trung tâm & Lovelace Kiosk |
| **CompreFace Web Admin** | `http://localhost:8000` | Huấn luyện & nạp ảnh khuôn mặt gia đình |
| **Double-Take Console** | `http://localhost:3000` | Đối soát hình ảnh camera và xem log khớp mặt |
| **ESPHome Web** | `http://localhost:6052` | Biên dịch & nạp firmware qua web/OTA |
| **Node-RED** | `http://localhost:1880` | Thiết kế luồng tự động hóa trực quan |
| **Mosquitto MQTT** | `1883`, `9001` | Trạm trung chuyển tin nhắn |

---

## 🧠 Cấu hình AI Nhận diện khuôn mặt

1. Truy cập giao diện quản trị CompreFace: `http://localhost:8000`.
2. Tạo tài khoản Admin -> Bấm **Create Service** (chọn loại **Recognition**).
3. Đặt tên (vd: `SmartHome_Face_Service`) -> Bấm sao chép **API Key**.
4. Dán API key vào file [`double-take_data/config.yml`](file:///d:/SmartHome/double-take_data/config.yml) và file `.env`.
5. Trong CompreFace, bấm vào **Subjects**:
   - Thêm tên từng thành viên gia đình (vd: `NguyenVanA`, `TranThiB`).
   - Tải lên 3 - 5 bức ảnh chụp rõ mặt ở các góc độ khác nhau.
6. Hệ thống sẽ ngay lập tức đối soát khuôn mặt với luồng ảnh từ ESP32-CAM!

---

## 🤖 Bot Telegram & Mở khóa từ xa

File script: [`custom_scripts/telegram_alert_bot.py`](file:///d:/SmartHome/custom_scripts/telegram_alert_bot.py)

### Cài đặt và khởi chạy
```bash
pip install -r custom_scripts/requirements.txt
python custom_scripts/telegram_alert_bot.py
```

### Tính năng tương tác:
* **Cảnh báo người lạ**: Khi camera phát hiện người lạ lảng vảng, Bot gửi ngay **ảnh chụp thực tế** kèm các nút bấm tương tác:
  - `[🔓 Mở cửa (5s)]`: Bấm để mở chốt cửa từ xa ngay trên chat.
  - `[🚨 Hú còi báo động]`: Bấm để kích hoạt còi cảnh báo đột nhập.
  - `[📸 Chụp lại ảnh]`: Chụp ảnh mới nhất gửi về máy chủ.
* **Lệnh điều khiển**:
  - `/unlock` : Mở chốt khóa cửa chính tức thì.
  - `/cam` : Yêu cầu chụp và gửi ảnh snapshot từ camera cửa.
  - `/who` : Xem người nhận diện gần nhất và % tin cậy.
  - `/status` : Xem nhiệt độ, độ ẩm và trạng thái đồng bộ Supabase.

---

## 📦 Quản lý mã nguồn với Git & GitHub

```bash
git add .
git commit -m "feat: integrate facial recognition with CompreFace, Double-Take, ESP32-CAM and Supabase DB"
git push -u origin main
```
