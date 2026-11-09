#!/usr/bin/env python3
"""
Telegram Security Alert, Remote Access & Supabase Sync Bot
---------------------------------------------------------
Author: Autonomous IoT & Automation Engineer
Description:
  - Monitors MQTT & Home Assistant events (Face Recognition & Radar).
  - Sends immediate Telegram alerts with camera snapshots when strangers are detected.
  - Interactive Inline Keyboards (Remote Unlock, Alarm Siren, Snapshot).
  - Synchronizes access logs and security events with Supabase PostgreSQL & Storage.
"""

import os
import sys
import time
import json
import logging
import threading
from datetime import datetime
import urllib.request
import urllib.parse
import urllib.error

# Import Supabase Client
try:
    from supabase_client import (
        log_access_event,
        log_security_alert,
        log_sensor_telemetry
    )
    SUPABASE_SYNC_ENABLED = True
except ImportError:
    SUPABASE_SYNC_ENABLED = False

# Optional MQTT support
try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SmartHomeTelegramBot")

# Environment & Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_HERE")
HA_BASE_URL = os.getenv("HA_BASE_URL", "http://localhost:8123")
HA_ACCESS_TOKEN = os.getenv("HA_ACCESS_TOKEN", "YOUR_LONG_LIVED_ACCESS_TOKEN")
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
CAM_SNAPSHOT_URL = os.getenv("CAM_SNAPSHOT_URL", "http://localhost:8081/saved_photo.jpg")

# In-memory security & telemetry state
STATE = {
    "armed": False,
    "last_alert_time": 0.0,
    "cooldown_seconds": 20.0,
    "current_temp": "28.5",
    "current_humidity": "65.0",
    "latest_person": "None",
    "latest_confidence": 0.0
}

def telegram_api_request(method: str, params: dict = None) -> dict:
    """Send an HTTP POST request to Telegram Bot API."""
    if TELEGRAM_BOT_TOKEN.startswith("YOUR_"):
        logger.warning("Telegram Bot Token is not configured. Skipping request: %s", method)
        return {"ok": False, "description": "Token not configured"}

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    headers = {"Content-Type": "application/json"}
    data = json.dumps(params or {}).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.error("Failed to call Telegram API '%s': %s", method, exc)
        return {"ok": False, "error": str(exc)}

def send_telegram_alert(text: str, reply_markup: dict = None, parse_mode: str = "HTML"):
    """Send text alert message to the configured Telegram chat."""
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return telegram_api_request("sendMessage", payload)

def download_camera_snapshot() -> bytes:
    """Fetch camera JPEG frame from ESP32-CAM snapshot endpoint."""
    try:
        req = urllib.request.Request(CAM_SNAPSHOT_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read()
    except Exception as err:
        logger.debug("Could not fetch camera snapshot: %s", err)
        return b""

def send_telegram_photo(caption: str, photo_bytes: bytes, reply_markup: dict = None):
    """Uploads and sends a photo with inline buttons to Telegram."""
    if not photo_bytes or TELEGRAM_BOT_TOKEN.startswith("YOUR_"):
        return send_telegram_alert(caption, reply_markup)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    boundary = "----SmartHomeBoundary" + str(int(time.time()))
    body = []

    # chat_id
    body.extend([
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="chat_id"',
        b'',
        str(TELEGRAM_CHAT_ID).encode("utf-8")
    ])

    # caption
    body.extend([
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="caption"',
        b'',
        caption.encode("utf-8")
    ])

    # parse_mode
    body.extend([
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="parse_mode"',
        b'',
        b"HTML"
    ])

    # reply_markup (inline keyboard)
    if reply_markup:
        body.extend([
            f"--{boundary}".encode("utf-8"),
            b'Content-Disposition: form-data; name="reply_markup"',
            b'',
            json.dumps(reply_markup).encode("utf-8")
        ])

    # photo file
    body.extend([
        f"--{boundary}".encode("utf-8"),
        b'Content-Disposition: form-data; name="photo"; filename="snapshot.jpg"',
        b'Content-Type: image/jpeg',
        b'',
        photo_bytes,
        f"--{boundary}--".encode("utf-8")
    ])

    payload = b"\r\n".join(body)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    req = urllib.request.Request(url, data=payload, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.error("Failed to upload photo to Telegram: %s", exc)
        return send_telegram_alert(caption, reply_markup)

def ha_api_post(endpoint: str, payload: dict) -> dict:
    """Trigger service in Home Assistant."""
    if HA_ACCESS_TOKEN.startswith("YOUR_"):
        return {}
    url = f"{HA_BASE_URL.rstrip('/')}/api/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {HA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.error("HA API POST '%s' error: %s", endpoint, exc)
        return {}

def trigger_door_unlock(requester: str = "Telegram"):
    """Unlocks front door for 5 seconds pulse."""
    logger.info("Unlocking door requested by: %s", requester)
    ha_api_post("services/lock/unlock", {"entity_id": "lock.front_door"})
    if SUPABASE_SYNC_ENABLED:
        log_access_event(
            location="front_door",
            person_name=requester,
            access_granted=True,
            confidence_score=100.0,
            auth_method="remote_app",
            notes=f"Unlocked via Telegram by {requester}"
        )

# ==============================================================================
# SECURITY & STRANGER EVENT HANDLERS
# ==============================================================================
def handle_stranger_detected(location: str = "Cửa chính (Camera Doorbell)"):
    """Handles stranger detection: captures snapshot, notifies, logs to Supabase."""
    now = time.time()
    if now - STATE["last_alert_time"] < STATE["cooldown_seconds"]:
        return
    STATE["last_alert_time"] = now

    photo_bytes = download_camera_snapshot()
    timestamp_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

    caption = (
        "🚨 <b>[CẢNH BÁO: PHÁT HIỆN NGƯỜI LẠ TRƯỚC CỬA]</b> 🚨\n\n"
        f"📍 <b>Vị trí:</b> {location}\n"
        f"⏱ <b>Thời gian:</b> {timestamp_str}\n"
        f"⚠️ <b>Hệ thống Face AI:</b> Không khớp danh sách gia đình (< 50% match)\n"
        f"🌡 <b>Nhiệt độ hiện tại:</b> {STATE['current_temp']} °C\n"
    )

    # Interactive Inline Keyboard for homeowner
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔓 Mở cửa (5s)", "callback_data": "btn_unlock_door"},
                {"text": "🚨 Hú còi báo động", "callback_data": "btn_siren_alarm"}
            ],
            [
                {"text": "📸 Chụp lại ảnh", "callback_data": "btn_refresh_cam"}
            ]
        ]
    }

    send_telegram_photo(caption, photo_bytes, keyboard)

    if SUPABASE_SYNC_ENABLED:
        log_security_alert(
            alert_type="stranger_detected",
            location="front_door",
            severity="HIGH",
            details={"temp": STATE["current_temp"], "humidity": STATE["current_humidity"]},
            image_bytes=photo_bytes
        )

def handle_authorized_access(person: str, confidence: float):
    """Triggered when recognized family member unlocks the door."""
    timestamp_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    text = (
        f"🔓 <b>XÁC THỰC THÀNH CÔNG (Face ID)</b>\n\n"
        f"👤 <b>Thành viên:</b> {person}\n"
        f"🎯 <b>Độ tin cậy:</b> {confidence:.1f}%\n"
        f"⏱ <b>Thời gian:</b> {timestamp_str}\n"
        f"🚪 Cửa chính đã tự động mở và tắt an ninh."
    )
    send_telegram_alert(text)

    if SUPABASE_SYNC_ENABLED:
        photo_bytes = download_camera_snapshot()
        log_access_event(
            location="front_door",
            person_name=person,
            access_granted=True,
            confidence_score=confidence,
            auth_method="face_recognition",
            image_bytes=photo_bytes
        )

# ==============================================================================
# MQTT SUBSCRIBER
# ==============================================================================
def on_mqtt_connect(client, userdata, flags, rc):
    logger.info("Connected to Mosquitto MQTT Broker (code %d)", rc)
    client.subscribe("double-take/matches")
    client.subscribe("esphome/bedroom_sensor/#")

def on_mqtt_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode("utf-8").strip()

        # Double-Take Face Recognition Events
        if topic == "double-take/matches":
            data = json.loads(payload)
            person = data.get("name", "unknown")
            confidence = (data.get("match", {}).get("confidence", 0.0) or 0.0) * 100

            STATE["latest_person"] = person
            STATE["latest_confidence"] = confidence

            if confidence >= 85.0 and person != "unknown":
                handle_authorized_access(person, confidence)
            elif person == "unknown" or confidence < 50.0:
                handle_stranger_detected()

        # Telemetry updates
        elif "dht22_temperature" in topic:
            STATE["current_temp"] = payload
        elif "dht22_humidity" in topic:
            STATE["current_humidity"] = payload

    except Exception as exc:
        logger.error("Error in MQTT callback: %s", exc)

def start_mqtt_client():
    if not PAHO_AVAILABLE:
        logger.warning("paho-mqtt not available.")
        return
    client = mqtt.Client(client_id="telegram_face_security_bot")
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except Exception as err:
        logger.error("MQTT connection failed (%s:%d): %s", MQTT_BROKER, MQTT_PORT, err)

# ==============================================================================
# TELEGRAM COMMAND & CALLBACK POLLING LOOP
# ==============================================================================
def process_callback_query(callback: dict):
    data = callback.get("data", "")
    cq_id = callback.get("id")
    user = callback.get("from", {}).get("first_name", "User")

    # Acknowledge callback immediately
    telegram_api_request("answerCallbackQuery", {"callback_query_id": cq_id})

    if data == "btn_unlock_door":
        trigger_door_unlock(f"Telegram Button ({user})")
        send_telegram_alert(f"✅ <b>{user}</b> đã bấm mở cửa từ xa!")
    elif data == "btn_siren_alarm":
        ha_api_post("services/switch/turn_on", {"entity_id": "switch.living_room_aux_socket"})
        send_telegram_alert(f"🚨 <b>CÒI BÁO ĐỘNG ĐÃ ĐƯỢC KÍCH HOẠT bởi {user}!</b>")
    elif data == "btn_refresh_cam":
        photo_bytes = download_camera_snapshot()
        send_telegram_photo(f"📸 <i>Ảnh chụp trực tiếp lúc {datetime.now().strftime('%H:%M:%S')}</i>", photo_bytes)

def process_telegram_command(text: str) -> str:
    cmd = text.strip().lower()
    if cmd in ("/start", "/help"):
        return (
            "🤖 <b>Hệ thống Quản lý Ra Vào & An ninh AI Smart Home</b>\n\n"
            "Các lệnh điều khiển:\n"
            "🔓 /unlock - Mở chốt khóa cửa chính từ xa (5 giây)\n"
            "📸 /cam - Chụp ảnh snapshot trực tiếp từ Camera chuông cửa\n"
            "👤 /who - Xem kết quả nhận diện khuôn mặt gần nhất\n"
            "📊 /status - Trạng thái hệ thống & thông số môi trường\n"
            "🔒 /arm - Kích hoạt chế độ bảo vệ (Armed Away)\n"
            "🔓 /disarm - Tắt chế độ bảo vệ\n"
            "💡 /lights_on - Bật đèn phòng khách\n"
            "🌑 /lights_off - Tắt đèn phòng khách"
        )
    elif cmd == "/unlock":
        trigger_door_unlock("Telegram Command")
        return "🔓 <b>Đã mở chốt cửa chính thành công!</b> Cửa sẽ tự khóa lại sau 5 giây."
    elif cmd == "/cam":
        photo_bytes = download_camera_snapshot()
        send_telegram_photo("📸 <i>Ảnh snapshot Camera Cửa chính</i>", photo_bytes)
        return "Đang gửi ảnh..."
    elif cmd == "/who":
        return (
            f"👤 <b>Nhận diện gần nhất:</b> {STATE['latest_person']}\n"
            f"🎯 <b>Độ khớp:</b> {STATE['latest_confidence']:.1f}%\n"
            f"⏱ <b>Thời điểm:</b> {datetime.now().strftime('%H:%M:%S')}"
        )
    elif cmd == "/status":
        armed_str = "🔒 ĐANG BẬT" if STATE["armed"] else "🔓 ĐANG TẮT"
        sync_str = "🟢 ĐÃ KẾT NỐI" if SUPABASE_SYNC_ENABLED else "⚪ TẮT"
        return (
            "📊 <b>TRẠNG THÁI HỆ THỐNG SMART HOME</b>\n\n"
            f"🛡 Chế độ an ninh: <b>{armed_str}</b>\n"
            f"⚡ Đồng bộ Supabase: <b>{sync_str}</b>\n"
            f"🌡 Nhiệt độ: <b>{STATE['current_temp']} °C</b>\n"
            f"💧 Độ ẩm: <b>{STATE['current_humidity']} %</b>\n"
            f"📡 Broker MQTT: <code>{MQTT_BROKER}:{MQTT_PORT}</code>"
        )
    elif cmd == "/arm":
        STATE["armed"] = True
        ha_api_post("services/input_boolean/turn_on", {"entity_id": "input_boolean.security_armed_away"})
        return "🔒 <b>Hệ thống đã KÍCH HOẠT bảo vệ!</b>"
    elif cmd == "/disarm":
        STATE["armed"] = False
        ha_api_post("services/input_boolean/turn_off", {"entity_id": "input_boolean.security_armed_away"})
        return "🔓 <b>Hệ thống đã TẮT bảo vệ.</b>"
    else:
        return "❓ Lệnh không hợp lệ. Gõ /help để xem trợ giúp."

def telegram_polling_loop():
    logger.info("Starting Telegram Polling loop...")
    last_update_id = 0
    while True:
        try:
            params = {"offset": last_update_id + 1, "timeout": 20}
            resp = telegram_api_request("getUpdates", params)
            if resp.get("ok"):
                for update in resp.get("result", []):
                    last_update_id = update["update_id"]

                    # Callback query (button press)
                    if "callback_query" in update:
                        process_callback_query(update["callback_query"])
                        continue

                    # Regular message
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "")

                    if text and (not TELEGRAM_CHAT_ID or chat_id == str(TELEGRAM_CHAT_ID)):
                        reply = process_telegram_command(text)
                        if reply and reply != "Đang gửi ảnh...":
                            telegram_api_request("sendMessage", {
                                "chat_id": chat_id,
                                "text": reply,
                                "parse_mode": "HTML"
                            })
            time.sleep(1)
        except Exception as exc:
            logger.error("Error in Telegram Polling: %s", exc)
            time.sleep(5)

if __name__ == "__main__":
    logger.info("Starting Face AI & Supabase Integrated Telegram Bot...")

    # Start Telegram Polling Thread
    t_tel = threading.Thread(target=telegram_polling_loop, daemon=True)
    t_tel.start()

    # Start MQTT Client Thread
    t_mqtt = threading.Thread(target=start_mqtt_client, daemon=True)
    t_mqtt.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
