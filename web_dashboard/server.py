#!/usr/bin/env python3
"""
Smart Home Standalone Monitoring & Control Management Server
------------------------------------------------------------
Author: Autonomous IoT & Automation Engineer
Description:
  - Lightweight, high-performance web dashboard backend.
  - Exposes REST API to control devices, update parameters, and query state.
  - Interfaces with Home Assistant REST API, Mosquitto MQTT, and Supabase.
  - Built-in Hardware Simulator to verify data communication without physical devices.
"""

import os
import sys
import json
import time
import socket
import logging
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request
import urllib.parse
import urllib.error
import threading

# Optional Supabase integration
try:
    from supabase import create_client
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    if SUPABASE_URL and not SUPABASE_URL.startswith("https://your-"):
        sp_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    else:
        sp_client = None
except Exception:
    sp_client = None

# Optional MQTT client
try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SmartHomeDashboard")

PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
HA_URL = os.getenv("HA_BASE_URL", "http://localhost:8123")
HA_TOKEN = os.getenv("HA_ACCESS_TOKEN", "YOUR_LONG_LIVED_ACCESS_TOKEN")
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Real-time state cache
CACHE_STATE = {
    "system": {
        "status": "ONLINE",
        "uptime": 0,
        "mqtt_connected": False,
        "ha_connected": False,
        "supabase_connected": bool(sp_client),
        "server_time": ""
    },
    "security": {
        "armed_away": False,
        "vacation_mode": False,
        "house_mode": "Bình thường (Normal)",
        "anti_spoofing": True,
        "latest_face_match": "None",
        "latest_face_confidence": 0.0,
        "door_contact_open": False,
        "door_lock_engaged": True
    },
    "relays": {
        "main_light": False,
        "ambient_light": False,
        "ceiling_fan": False,
        "aux_socket": False,
        "door_strike_relay": False
    },
    "sensors": {
        "temperature": 28.5,
        "humidity": 65.0,
        "radar_presence": False,
        "radar_motion": False,
        "radar_distance": 120.0,
        "radar_energy": 45
    },
    "settings": {
        "face_threshold": 85,
        "light_off_delay": 5,
        "fan_temp_high": 30.0,
        "fan_temp_low": 27.0,
        "unlock_duration": 5,
        "cooldown_seconds": 30
    },
    "recent_logs": []
}

mqtt_client_instance = None

def ha_call(endpoint: str, method: str = "GET", payload: dict = None) -> dict:
    """Make requests to Home Assistant REST API."""
    if not HA_TOKEN or HA_TOKEN.startswith("YOUR_"):
        return {}
    url = f"{HA_URL.rstrip('/')}/api/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            CACHE_STATE["system"]["ha_connected"] = True
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        CACHE_STATE["system"]["ha_connected"] = False
        logger.debug("HA call error: %s", exc)
        return {}

def publish_mqtt(topic: str, payload: str):
    """Publish MQTT message through global client."""
    global mqtt_client_instance
    if mqtt_client_instance and CACHE_STATE["system"]["mqtt_connected"]:
        try:
            mqtt_client_instance.publish(topic, payload)
            logger.info("Published MQTT [%s]: %s", topic, payload)
        except Exception as e:
            logger.error("Failed to publish MQTT: %s", e)

# MQTT Background Worker
def init_mqtt():
    global mqtt_client_instance
    if not PAHO_AVAILABLE:
        logger.warning("paho-mqtt not available.")
        return

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            CACHE_STATE["system"]["mqtt_connected"] = True
            logger.info("Dashboard connected to MQTT Broker (%s:%d)", MQTT_BROKER, MQTT_PORT)
            client.subscribe("esphome/#")
            client.subscribe("double-take/#")
        else:
            CACHE_STATE["system"]["mqtt_connected"] = False

    def on_message(client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8", errors="ignore").strip()

        # Update cache from MQTT
        if "dht22_temperature" in topic:
            try:
                CACHE_STATE["sensors"]["temperature"] = float(payload)
            except ValueError:
                pass
        elif "dht22_humidity" in topic:
            try:
                CACHE_STATE["sensors"]["humidity"] = float(payload)
            except ValueError:
                pass
        elif "ld2410_has_target" in topic:
            CACHE_STATE["sensors"]["radar_presence"] = payload.upper() in ("ON", "1", "TRUE")
        elif "ld2410_has_moving_target" in topic:
            CACHE_STATE["sensors"]["radar_motion"] = payload.upper() in ("ON", "1", "TRUE")
        elif topic == "double-take/matches":
            try:
                data = json.loads(payload)
                CACHE_STATE["security"]["latest_face_match"] = data.get("name", "unknown")
                if "match" in data:
                    CACHE_STATE["security"]["latest_face_confidence"] = round((data["match"].get("confidence", 0) * 100), 1)
            except Exception:
                pass

    mqtt_client_instance = mqtt.Client(client_id="smart_home_web_dashboard")
    mqtt_client_instance.on_connect = on_connect
    mqtt_client_instance.on_message = on_message

    try:
        mqtt_client_instance.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client_instance.loop_start()
    except Exception as exc:
        logger.warning("Could not connect dashboard to MQTT: %s", exc)

class DashboardRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        directory = os.path.dirname(os.path.abspath(__file__))
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/state":
            CACHE_STATE["system"]["server_time"] = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
            self._send_json(CACHE_STATE)
        elif parsed.path == "/api/logs":
            self._handle_get_logs()
        elif parsed.path in ("/", "/index.html"):
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        data = {}
        if length > 0:
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                pass

        if parsed.path == "/api/control/relay":
            target = data.get("relay")
            state = data.get("state") # True / False
            if target in CACHE_STATE["relays"]:
                CACHE_STATE["relays"][target] = state
                # Forward to HA and MQTT
                ha_entity_map = {
                    "main_light": "switch.living_room_main_light",
                    "ambient_light": "switch.living_room_ambient_light",
                    "ceiling_fan": "switch.living_room_ceiling_fan",
                    "aux_socket": "switch.living_room_aux_socket"
                }
                if target in ha_entity_map:
                    svc = "turn_on" if state else "turn_off"
                    ha_call(f"services/switch/{svc}", "POST", {"entity_id": ha_entity_map[target]})
                publish_mqtt(f"esphome/livingroom_relay/switch/{target}/command", "ON" if state else "OFF")
            self._send_json({"ok": True, "relays": CACHE_STATE["relays"]})

        elif parsed.path == "/api/control/unlock":
            # Trigger Door Unlock Pulse
            CACHE_STATE["relays"]["door_strike_relay"] = True
            CACHE_STATE["security"]["door_lock_engaged"] = False
            ha_call("services/lock/unlock", "POST", {"entity_id": "lock.front_door"})
            publish_mqtt("esphome/livingroom_relay/switch/front_door_lock_electronic_relay/command", "ON")

            def auto_relock():
                time.sleep(CACHE_STATE["settings"]["unlock_duration"])
                CACHE_STATE["relays"]["door_strike_relay"] = False
                CACHE_STATE["security"]["door_lock_engaged"] = True

            threading.Thread(target=auto_relock, daemon=True).start()
            self._send_json({"ok": True, "message": "Door unlocked"})

        elif parsed.path == "/api/control/security":
            armed = data.get("armed_away")
            if armed is not None:
                CACHE_STATE["security"]["armed_away"] = bool(armed)
                svc = "turn_on" if armed else "turn_off"
                ha_call(f"services/input_boolean/{svc}", "POST", {"entity_id": "input_boolean.security_armed_away"})
            self._send_json({"ok": True, "security": CACHE_STATE["security"]})

        elif parsed.path == "/api/settings":
            for k in ("face_threshold", "light_off_delay", "fan_temp_high", "fan_temp_low", "unlock_duration", "cooldown_seconds"):
                if k in data:
                    CACHE_STATE["settings"][k] = float(data[k])
            # Sync to Home Assistant
            ha_call("services/input_number/set_value", "POST", {
                "entity_id": "input_number.face_recognition_threshold",
                "value": CACHE_STATE["settings"]["face_threshold"]
            })
            self._send_json({"ok": True, "settings": CACHE_STATE["settings"]})

        elif parsed.path == "/api/simulate":
            # Hardware Test Simulator
            event_type = data.get("type")
            self._handle_simulation(event_type, data)
            self._send_json({"ok": True, "simulated": event_type, "state": CACHE_STATE})
        else:
            self._send_json({"error": "Unknown endpoint"}, 404)

    def _handle_simulation(self, event_type: str, data: dict):
        """Simulate hardware sensor/camera events to test system reactivity."""
        now_str = datetime.now().strftime("%H:%M:%S")
        if event_type == "face_match":
            person = data.get("person", "Nguyen Van A")
            confidence = float(data.get("confidence", 94.5))
            CACHE_STATE["security"]["latest_face_match"] = person
            CACHE_STATE["security"]["latest_face_confidence"] = confidence

            # Publish to MQTT Double-Take topic
            dt_payload = json.dumps({
                "name": person,
                "match": {"confidence": confidence / 100.0, "name": person}
            })
            publish_mqtt("double-take/matches", dt_payload)
            CACHE_STATE["recent_logs"].insert(0, {
                "time": now_str,
                "type": "FACE_MATCH",
                "desc": f"Khớp khuôn mặt: {person} ({confidence}%) -> Mở khóa cửa"
            })

        elif event_type == "stranger_detected":
            CACHE_STATE["security"]["latest_face_match"] = "unknown"
            CACHE_STATE["security"]["latest_face_confidence"] = 32.0
            dt_payload = json.dumps({
                "name": "unknown",
                "match": {"confidence": 0.32, "name": "unknown"}
            })
            publish_mqtt("double-take/matches", dt_payload)
            CACHE_STATE["recent_logs"].insert(0, {
                "time": now_str,
                "type": "STRANGER_ALERT",
                "desc": "Cảnh báo: Phát hiện người lạ trước camera chuông cửa (<50%)"
            })

        elif event_type == "doorbell_ring":
            publish_mqtt("esphome/cam_doorbell/doorbell_button/state", "ON")
            CACHE_STATE["recent_logs"].insert(0, {
                "time": now_str,
                "type": "DOORBELL",
                "desc": "Sự kiện: Có khách bấm chuông cửa chính"
            })

        elif event_type == "motion_trigger":
            has_motion = bool(data.get("motion", True))
            CACHE_STATE["sensors"]["radar_presence"] = has_motion
            CACHE_STATE["sensors"]["radar_motion"] = has_motion
            publish_mqtt("esphome/bedroom_sensor/binary_sensor/ld2410_has_target/state", "ON" if has_motion else "OFF")
            publish_mqtt("esphome/bedroom_sensor/binary_sensor/ld2410_has_moving_target/state", "ON" if has_motion else "OFF")
            CACHE_STATE["recent_logs"].insert(0, {
                "time": now_str,
                "type": "RADAR_MOTION",
                "desc": f"Radar mmWave HLK-LD2410: {'Phát hiện hiện diện mục tiêu' if has_motion else 'Không còn người'}"
            })

        elif event_type == "temp_change":
            temp = float(data.get("temp", 31.5))
            hum = float(data.get("humidity", 68.0))
            CACHE_STATE["sensors"]["temperature"] = temp
            CACHE_STATE["sensors"]["humidity"] = hum
            publish_mqtt("esphome/bedroom_sensor/sensor/dht22_temperature/state", str(temp))
            publish_mqtt("esphome/bedroom_sensor/sensor/dht22_humidity/state", str(hum))
            CACHE_STATE["recent_logs"].insert(0, {
                "time": now_str,
                "type": "DHT22_UPDATE",
                "desc": f"Cập nhật DHT22: {temp}°C, Độ ẩm: {hum}%"
            })

        if len(CACHE_STATE["recent_logs"]) > 50:
            CACHE_STATE["recent_logs"] = CACHE_STATE["recent_logs"][:50]

    def _handle_get_logs(self):
        logs = []
        if sp_client:
            try:
                res = sp_client.table("access_logs").select("*").order("timestamp", desc=True).limit(20).execute()
                logs = res.data
            except Exception as e:
                logger.error("Supabase log fetch error: %s", e)
        if not logs:
            logs = CACHE_STATE["recent_logs"]
        self._send_json({"logs": logs})

    def _send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

def run_server():
    init_mqtt()
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, DashboardRequestHandler)
    logger.info("==================================================================")
    logger.info("  🚀 Smart Home Web Management Dashboard started successfully!")
    logger.info("  👉 URL: http://localhost:%d", PORT)
    logger.info("==================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard server shutting down.")

if __name__ == "__main__":
    run_server()
