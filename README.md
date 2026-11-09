# 🏡 Local-First Smart Home & AI Agent System

Dự án triển khai hệ thống Nhà thông minh cục bộ (**Local-first Smart Home**) với độ trễ siêu thấp, bảo mật quyền riêng tư tối đa và khả năng hoạt động độc lập ngay cả khi mất kết nối Internet quốc tế.

---

## 📑 Mục lục
1. [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
2. [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
3. [Sơ đồ đấu nối phần cứng ESP32](#-sơ-đồ-đấu-nối-phần-cứng-esp32)
4. [Hướng dẫn cài đặt hạ tầng Docker](#-hướng-dẫn-cài-đặt-hạ-tầng-docker)
5. [Nạp Firmware cho các Node ESPHome](#-nạp-firmware-cho-các-node-esphome)
6. [Cấu hình Home Assistant & Dashboard UI](#-cấu-hình-home-assistant--dashboard-ui)
7. [Triển khai Bot An ninh Telegram](#-triển-khai-bot-an-ninh-telegram)
8. [Quản lý mã nguồn với Git & GitHub](#-quản-lý-mã-nguồn-với-git--github)

---

## 🏗 Kiến trúc hệ thống

```text
       +-------------------------------------------------------------+
       |                     NGƯỜI DÙNG / APP                        |
       |     Home Assistant App / Kiosk Lovelace / Telegram Bot     |
       +------------------------------+------------------------------+
                                      |
                     [HTTP :8123]     |    [Telegram API / Polling]
                                      v
       +-------------------------------------------------------------+
       |               CORE SERVER (Docker Containers)               |
       |                                                             |
       |  +------------------+             +----------------------+  |
       |  |  Home Assistant  |<----------->|     Node-RED Flow    |  |
       |  |     (Core Hub)   |  WebSocket  |  (Advanced Automate) |  |
       |  +---------+--------+             +-----------+----------+  |
       |            |                                  |             |
       |            +---------------+  +---------------+             |
       |                            |  |                             |
       |                            v  v                             |
       |                  +--------------------+                     |
       |                  |   Mosquitto MQTT   |                     |
       |                  |    (Local Broker)  |                     |
       |                  +----+----------+----+                     |
       |                       |          |                          |
       +-----------------------|----------|--------------------------+
                               |          |
                   [MQTT / IP] |          | [Zigbee / Coordinator]
                               |          v
                               |   +-------------------+
                               |   |    Zigbee2MQTT    |
                               |   +---------+---------+
                               |             | (Zigbee 3.0 Mesh)
                               |             v
                               |     +----------------+
                               |     | Cảm biến Zigbee|
                               |     +----------------+
                               v
       +-------------------------------------------------------------+
       |               HARDWARE NODES (ESPHome on ESP32)             |
       |                                                             |
       |  [Node 1: Relay Phòng khách]     [Node 2: Cảm biến Phòng ngủ]|
       |  - 4 Rơ-le điều khiển đèn/quạt    - Cảm biến nhiệt ẩm DHT22   |
       |  - 4 Công tắc âm tường vật lý    - Radar vi sóng HLK-LD2410  |
       +-------------------------------------------------------------+
```

---

## 📂 Cấu trúc thư mục

```text
SmartHome/
├── docker-compose.yml                  # Khởi chạy HA, MQTT, Z2M, Node-RED, ESPHome
├── .env.example                        # Mẫu biến môi trường
├── .gitignore                          # Cấu hình bỏ qua file nhạy cảm và cache
├── ha_config/
│   ├── configuration.yaml              # Cấu hình lõi Home Assistant & MQTT
│   ├── automations.yaml                # Các kịch bản tự động hóa (Ánh sáng, An ninh)
│   ├── ui-lovelace.yaml                # Dashboard giao diện Kiosk UI hiện đại
│   ├── scripts.yaml                    # Các script mở rộng của HA
│   └── scenes.yaml                     # Ngữ cảnh chiếu sáng
├── esphome_nodes/
│   ├── esp32_livingroom_relay.yaml     # Node ESP32 4 rơ-le & 4 công tắc cơ
│   └── esp32_bedroom_sensor.yaml       # Node ESP32 DHT22 & Radar mmWave LD2410
├── mosquitto/
│   └── config/
│       └── mosquitto.conf              # Cấu hình Mosquitto MQTT Broker (port 1883, 9001)
├── zigbee2mqtt/
│   └── data/
│       └── configuration.yaml.example  # Cấu hình mẫu kết nối Zigbee USB Dongle
├── custom_scripts/
│   ├── telegram_alert_bot.py           # Script cảnh báo an ninh & điều khiển qua Telegram
│   └── requirements.txt                # Thư viện Python hỗ trợ bot
└── README.md                           # Tài liệu kỹ thuật hoàn chỉnh
```

---

## 🔌 Sơ đồ đấu nối phần cứng ESP32

### 1. Node Phòng khách: ESP32 + Rơ-le 4 kênh (`esp32_livingroom_relay.yaml`)

Module rơ-le kích mức Thấp (**Active LOW**) kèm dự phòng công tắc vật lý:

| Chân ESP32 | Chân Thiết bị ngoại vi | Thiết bị kết nối | Chức năng |
| :--- | :--- | :--- | :--- |
| **GPIO16** | Relay IN1 | Rơ-le Đèn chính trần | Điều khiển bật/tắt đèn trần |
| **GPIO17** | Relay IN2 | Rơ-le Đèn hắt viền | Điều khiển đèn Ambient/viền |
| **GPIO18** | Relay IN3 | Rơ-le Quạt trần | Điều khiển bật/tắt quạt |
| **GPIO19** | Relay IN4 | Rơ-le Ổ cắm Aux | Điều khiển tải phụ trợ |
| **GPIO32** | Công tắc cơ SW1 -> GND | Công tắc âm tường 1 | Đảo trạng thái Rơ-le 1 tức thì |
| **GPIO33** | Công tắc cơ SW2 -> GND | Công tắc âm tường 2 | Đảo trạng thái Rơ-le 2 tức thì |
| **GPIO25** | Công tắc cơ SW3 -> GND | Công tắc âm tường 3 | Đảo trạng thái Rơ-le 3 tức thì |
| **GPIO26** | Công tắc cơ SW4 -> GND | Công tắc âm tường 4 | Đảo trạng thái Rơ-le 4 tức thì |
| **GND** | GND Relay & Switches | Chung mass hệ thống | Nối đất |
| **VIN / 5V** | VCC Relay Board | Nguồn cấp 5V DC | Cấp nguồn nuôi cuộn hút |

> **Lưu ý an toàn:** Khi đấu nối nguồn 220VAC vào tiếp điểm COM và NO của rơ-le, hãy ngắt atomat điện trước khi thao tác.

---

### 2. Node Phòng ngủ: ESP32 + DHT22 + Radar HLK-LD2410 (`esp32_bedroom_sensor.yaml`)

| Chân ESP32 | Chân Module | Ghi chú kỹ thuật |
| :--- | :--- | :--- |
| **GPIO4** | DHT22 Data (Chân 2) | Kèm điện trở kéo lên trở treo 4.7kΩ – 10kΩ lên 3.3V |
| **3V3** | DHT22 VCC (Chân 1) | Nguồn nuôi cảm biến nhiệt ẩm |
| **GND** | DHT22 GND (Chân 4) | Nối mass chung |
| **GPIO16 (RX2)** | HLK-LD2410 TX | Nhận dữ liệu radar UART (Baud 256000) |
| **GPIO17 (TX2)** | HLK-LD2410 RX | Gửi lệnh cấu hình khoảng cách / độ nhạy radar |
| **5V (VIN)** | HLK-LD2410 VCC | Radar mmWave yêu cầu nguồn 5V ổn định (>150mA) |
| **GND** | HLK-LD2410 GND | Nối mass chung |

---

## 🚀 Hướng dẫn cài đặt hạ tầng Docker

### Yêu cầu tiên quyết
- Máy tính hoặc Raspberry Pi / Mini PC chạy Windows, Ubuntu Linux hoặc macOS đã cài **Docker** và **Docker Compose**.

### Các bước khởi động
1. Tạo file môi trường từ mẫu:
   ```bash
   cp .env.example .env
   ```
2. Khởi chạy toàn bộ hệ thống ở chế độ nền (detached):
   ```bash
   docker compose up -d
   ```
3. Kiểm tra trạng thái các container:
   ```bash
   docker compose ps
   ```

### Bảng cổng dịch vụ (Ports)
| Dịch vụ | Cổng truy cập | Mô tả |
| :--- | :--- | :--- |
| **Home Assistant** | `http://localhost:8123` | Giao diện điều khiển trung tâm |
| **ESPHome Dashboard** | `http://localhost:6052` | Biên dịch & nạp firmware qua web |
| **Node-RED** | `http://localhost:1880` | Thiết kế luồng tự động hóa trực quan |
| **Zigbee2MQTT** | `http://localhost:8080` | Quản lý thiết bị mạng Zigbee |
| **Mosquitto MQTT** | `1883` (TCP), `9001` (WS) | Trạm trung chuyển bản tin |

---

## ⚡ Nạp Firmware cho các Node ESPHome

### Cách 1: Nạp qua giao diện Web ESPHome (Khuyến nghị)
1. Mở trình duyệt truy cập: `http://localhost:6052`
2. Cắm mạch ESP32 vào máy chủ bằng cáp MicroUSB / Type-C.
3. Chọn node tương ứng (`esp32-livingroom-relay` hoặc `esp32-bedroom-sensor`).
4. Nhấn **Install** -> Chọn **Plug into this computer** hoặc tải file `.bin` nạp qua [web.esphome.io](https://web.esphome.io).
5. Các lần cập nhật sau có thể thực hiện hoàn toàn qua mạng Wi-Fi (**OTA - Wirelessly**).

### Cách 2: Nạp bằng dòng lệnh ESPHome CLI
```bash
# Biên dịch và nạp cho Node Relay
esphome run esphome_nodes/esp32_livingroom_relay.yaml

# Biên dịch và nạp cho Node Cảm biến
esphome run esphome_nodes/esp32_bedroom_sensor.yaml
```

---

## 🖥 Cấu hình Home Assistant & Dashboard UI

1. Đăng nhập vào Home Assistant tại `http://localhost:8123`.
2. Vào **Settings** -> **Devices & Services** -> Bấm **Add Integration**:
   - Chọn **MQTT**: Nhập broker `mosquitto`, port `1883` (Anonymous hoặc user nếu có đặt).
   - Chọn **ESPHome**: Nhập địa chỉ IP của từng mạch ESP32 để tự động khám phá toàn bộ các thực thể rơ-le và radar.
3. Dashboard YAML đã được liên kết tại `ha_config/ui-lovelace.yaml`.
   - Để kích hoạt chế độ Lovelace YAML, vào Home Assistant bấm nút **Menu 3 chấm** -> **Reload Lovelace Configuration**.

---

## 🤖 Triển khai Bot An ninh Telegram

Script `telegram_alert_bot.py` giúp gửi cảnh báo tức thì kèm nhiệt độ/độ ẩm khi phát hiện mục tiêu di chuyển trong chế độ bảo vệ (`Armed Away`).

### 1. Cài đặt thư viện Python
```bash
cd custom_scripts
pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường
Mở file `.env` và điền:
- `TELEGRAM_BOT_TOKEN`: Lấy từ `@BotFather` trên Telegram.
- `TELEGRAM_CHAT_ID`: ID người dùng hoặc group nhận cảnh báo (lấy qua `@userinfobot`).
- `HA_ACCESS_TOKEN`: Long-Lived Access Token tạo tại trang Profile cá nhân trong Home Assistant.

### 3. Chạy Bot
```bash
python custom_scripts/telegram_alert_bot.py
```

### 4. Danh sách lệnh điều khiển bot
- `/status` : Xem báo cáo tổng quát nhiệt độ, độ ẩm, an ninh.
- `/arm` : Bật chế độ cảnh báo xâm nhập.
- `/disarm` : Tắt chế độ bảo vệ.
- `/lights_on` : Bật đèn phòng khách khẩn cấp.
- `/lights_off` : Tắt đèn phòng khách.
- `/fan_toggle` : Đảo trạng thái quạt trần.

---

## 📦 Quản lý mã nguồn với Git & GitHub

Hệ thống đã được thiết kế sẵn sàng đưa lên GitHub:

```bash
# Khởi tạo repository Git
git init

# Thêm tất cả file
git add .

# Tạo commit đầu tiên
git commit -m "feat: complete local-first smart home system architecture"

# Liên kết với repository GitHub của bạn (thay thế URL tương ứng)
git branch -M main
git remote add origin https://github.com/<USERNAME>/<REPO_NAME>.git

# Đẩy mã nguồn lên GitHub
git push -u origin main
```

---
*Tài liệu được xây dựng chuẩn hoá theo kế hoạch thực thi kỹ thuật Smart Home AI Agent.*
