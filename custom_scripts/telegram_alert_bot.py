#!/usr/bin/env python3
"""
Telegram Security Alert & Control Bot for Local Smart Home
---------------------------------------------------------
Author: Autonomous IoT & Automation Engineer
Description:
  - Monitors MQTT / Home Assistant states for unauthorized movement.
  - Sends instant high-priority alerts to Telegram when security is armed.
  - Provides interactive commands to query status, arm/disarm, and control relays.
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

# In-memory security state
STATE = {
    "armed": False,
    "last_motion_time": 0.0,
    "motion_cooldown_seconds": 30.0,
    "current_temp": "N/A",
    "current_humidity": "N/A"
}

def telegram_api_request(method: str, params: dict = None) -> dict:
    """Send an HTTP POST request directly to Telegram Bot API."""
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

def send_telegram_alert(text: str, parse_mode: str = "HTML"):
    """Send text alert message to the configured Telegram chat."""
    logger.info("Sending Telegram Alert: %s", text)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode
    }
    return telegram_api_request("sendMessage", payload)

def ha_api_get(endpoint: str) -> dict:
    """Query Home Assistant REST API."""
    if HA_ACCESS_TOKEN.startswith("YOUR_"):
        return {}
    url = f"{HA_BASE_URL.rstrip('/')}/api/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {HA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.debug("HA API GET '%s' error: %s", endpoint, exc)
        return {}

def ha_api_post(endpoint: str, payload: dict) -> dict:
    """Call a service or update state via Home Assistant REST API."""
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

def handle_unauthorized_movement(sensor_name: str, details: str = ""):
    """Triggers security alarm when movement is detected while armed."""
    now = time.time()
    # Anti-spam cooldown
    if now - STATE["last_motion_time"] < STATE["motion_cooldown_seconds"]:
        logger.info("Movement detected but cooldown is active. Suppressing alert.")
        return

    STATE["last_motion_time"] = now
    timestamp_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

    alert_msg = (
        "🚨 <b>[CẢNH BÁO AN NINH SMART HOME]</b> 🚨\n\n"
        f"📍 <b>Khu vực:</b> {sensor_name}\n"
        f"⏱ <b>Thời gian:</b> {timestamp_str}\n"
        f"⚠️ <b>Trạng thái:</b> Phát hiện mục tiêu di chuyển / Hiện diện bất thường!\n"
        f"🌡 <b>Nhiệt độ hiện tại:</b> {STATE['current_temp']} °C\n"
        f"💧 <b>Độ ẩm:</b> {STATE['current_humidity']} %\n"
    )
    if details:
        alert_msg += f"ℹ️ <b>Chi tiết cảm biến:</b> {details}\n"

    alert_msg += "\n💡 <i>Gửi /disarm để tắt còi hoặc /lights_on để bật sáng toàn bộ khu vực.</i>"
    send_telegram_alert(alert_msg)

# ==============================================================================
# MQTT SUBSCRIBER THREAD
# ==============================================================================
def on_mqtt_connect(client, userdata, flags, rc):
    logger.info("Connected to Mosquitto MQTT Broker (code %d)", rc)
    # Subscribe to ESPHome bedroom sensor topics
    client.subscribe("esphome/bedroom_sensor/#")
    client.subscribe("homeassistant/binary_sensor/+/state")

def on_mqtt_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8").strip()
        topic = msg.topic

        if "ld2410_has_moving_target" in topic or "bedroom_mmwave_motion" in topic:
            if payload.upper() in ("ON", "1", "TRUE"):
                logger.info("Motion detected on topic: %s", topic)
                if STATE["armed"]:
                    handle_unauthorized_movement("Phòng ngủ (Radar mmWave LD2410)", f"Topic: {topic}")

        elif "dht22_temperature" in topic:
            STATE["current_temp"] = payload
        elif "dht22_humidity" in topic:
            STATE["current_humidity"] = payload

    except Exception as exc:
        logger.error("Error processing MQTT message: %s", exc)

def start_mqtt_client():
    if not PAHO_AVAILABLE:
        logger.warning("paho-mqtt is not installed. Polling fallback mode enabled.")
        return

    client = mqtt.Client(client_id="telegram_security_bot")
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except Exception as err:
        logger.error("Failed to connect to MQTT broker (%s:%d): %s", MQTT_BROKER, MQTT_PORT, err)

# ==============================================================================
# TELEGRAM LONG POLLING FOR COMMANDS (/status, /arm, /disarm, /lights_on, etc.)
# ==============================================================================
def process_telegram_command(text: str) -> str:
    cmd = text.strip().lower()
    if cmd in ("/start", "/help"):
        return (
            "🤖 <b>Hệ thống Trợ lý An ninh Smart Home</b>\n\n"
            "Các lệnh điều khiển:\n"
            "🔹 /status - Kiểm tra trạng thái hệ thống & cảm biến\n"
            "🔒 /arm - Kích hoạt chế độ bảo vệ (Báo động khi có người)\n"
            "🔓 /disarm - Vô hiệu hóa chế độ bảo vệ\n"
            "💡 /lights_on - Bật đèn phòng khách\n"
            "🌑 /lights_off - Tắt đèn phòng khách\n"
            "🌀 /fan_toggle - Bật/tắt quạt phòng khách"
        )
    elif cmd == "/arm":
        STATE["armed"] = True
        ha_api_post("services/input_boolean/turn_on", {"entity_id": "input_boolean.security_armed_away"})
        return "🔒 <b>Hệ thống đã KÍCH HOẠT bảo vệ (ARMED AWAY)!</b> Mọi chuyển động sẽ kích hoạt cảnh báo."
    elif cmd == "/disarm":
        STATE["armed"] = False
        ha_api_post("services/input_boolean/turn_off", {"entity_id": "input_boolean.security_armed_away"})
        return "🔓 <b>Hệ thống đã TẮT bảo vệ (DISARMED).</b>"
    elif cmd == "/status":
        armed_str = "🔒 ĐANG BẬT" if STATE["armed"] else "🔓 ĐANG TẮT"
        return (
            "📊 <b>TRẠNG THÁI HỆ THỐNG SMART HOME</b>\n\n"
            f"🛡 Chế độ an ninh: <b>{armed_str}</b>\n"
            f"🌡 Nhiệt độ: <b>{STATE['current_temp']} °C</b>\n"
            f"💧 Độ ẩm: <b>{STATE['current_humidity']} %</b>\n"
            f"📡 Broker MQTT: <code>{MQTT_BROKER}:{MQTT_PORT}</code>\n"
            f"🏠 Home Assistant: <code>{HA_BASE_URL}</code>"
        )
    elif cmd == "/lights_on":
        ha_api_post("services/switch/turn_on", {"entity_id": "switch.living_room_main_light"})
        return "💡 Đã gửi lệnh <b>BẬT ĐÈN</b> phòng khách."
    elif cmd == "/lights_off":
        ha_api_post("services/switch/turn_off", {"entity_id": "switch.living_room_main_light"})
        return "🌑 Đã gửi lệnh <b>TẮT ĐÈN</b> phòng khách."
    elif cmd == "/fan_toggle":
        ha_api_post("services/switch/toggle", {"entity_id": "switch.living_room_ceiling_fan"})
        return "🌀 Đã gửi lệnh đảo trạng thái <b>QUẠT</b> phòng khách."
    else:
        return "❓ Lệnh không hợp lệ. Nhập /help để xem danh sách lệnh."

def telegram_polling_loop():
    logger.info("Starting Telegram Bot command polling...")
    last_update_id = 0
    while True:
        try:
            params = {"offset": last_update_id + 1, "timeout": 20}
            resp = telegram_api_request("getUpdates", params)
            if resp.get("ok"):
                for update in resp.get("result", []):
                    last_update_id = update["update_id"]
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "")

                    if text and (not TELEGRAM_CHAT_ID or chat_id == str(TELEGRAM_CHAT_ID)):
                        reply = process_telegram_command(text)
                        telegram_api_request("sendMessage", {
                            "chat_id": chat_id,
                            "text": reply,
                            "parse_mode": "HTML"
                        })
            time.sleep(1)
        except Exception as exc:
            logger.error("Error in Telegram Polling loop: %s", exc)
            time.sleep(5)

if __name__ == "__main__":
    logger.info("Starting Smart Home Telegram Alert System...")
    logger.info("Armed state: %s", STATE["armed"])

    # Launch Telegram polling thread
    t_telegram = threading.Thread(target=telegram_polling_loop, daemon=True)
    t_telegram.start()

    # Launch MQTT client thread
    t_mqtt = threading.Thread(target=start_mqtt_client, daemon=True)
    t_mqtt.start()

    # Keep main alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Bot shutting down gracefully.")
