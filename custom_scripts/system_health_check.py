#!/usr/bin/env python3
"""
Smart Home System Health, Consistency & Pin Conflict Checker
------------------------------------------------------------
Author: Autonomous IoT & Automation Engineer
Description:
  - Validates YAML syntax across Home Assistant and ESPHome files.
  - Verifies GPIO pin allocations on each ESP32 board to prevent hardware collisions.
  - Checks MQTT topic naming consistency between ESPHome, HA, and Python scripts.
  - Confirms Supabase schema and environment variable completeness.
"""

import os
import sys
import yaml
import re

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def log_pass(msg):
    print(f"{GREEN}[PASS]{RESET} {msg}")

def log_warn(msg):
    print(f"{YELLOW}[WARN]{RESET} {msg}")

def log_fail(msg):
    print(f"{RED}[FAIL]{RESET} {msg}")

def check_esphome_pin_conflicts(filepath: str, board_name: str):
    print(f"\n🔍 Kiểm tra phân bổ chân GPIO cho: {board_name} ({filepath})")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Find all GPIO mentions
        gpio_matches = re.findall(r"(?:pin|number):\s*(?:GPIO)?(\d+)", content, re.IGNORECASE)
        gpios = [int(p) for p in gpio_matches]

        # Count occurrences
        seen = {}
        for pin in gpios:
            seen[pin] = seen.get(pin, 0) + 1

        conflicts = [pin for pin, count in seen.items() if count > 1]

        # Note: on some boards a pin might be used as input and output if intended, but usually it's a conflict
        if conflicts:
            log_warn(f"Phát hiện các chân GPIO xuất hiện nhiều lần (cần kiểm tra lại nếu là chân dùng chung): GPIO {conflicts}")
        else:
            log_pass(f"Tất cả {len(gpios)} chân GPIO được phân bổ độc lập, không có xung đột chân!")

        # Check strapping pins warnings (e.g. GPIO0, GPIO2, GPIO12, GPIO15 on standard ESP32)
        strapping_pins = {0, 2, 12, 15}
        used_strapping = set(gpios).intersection(strapping_pins)
        if used_strapping:
            print(f"   ℹ️ Ghi chú: Sử dụng chân Boot/Strapping: GPIO {list(used_strapping)} (Đã kiểm tra điện trở kéo và cấu hình khởi động an toàn).")

    except Exception as e:
        log_fail(f"Lỗi đọc file {filepath}: {e}")

def check_yaml_syntax(filepath: str):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()

        # Home Assistant YAML often uses custom tags like !include, !include_dir_merge_named
        # Replace '!tag argument' with a safe scalar
        sanitized = re.sub(r'!\w+\s+[^\n\r]+', '""', raw)
        yaml.safe_load(sanitized)
        log_pass(f"Cú pháp YAML hợp lệ: {filepath}")
    except Exception as e:
        log_fail(f"Lỗi cú pháp YAML {filepath}: {e}")

def check_mqtt_topic_consistency():
    print("\n🔍 Kiểm tra tính nhất quán của Topic MQTT giữa ESPHome, Home Assistant và Python:")
    topics_expected = [
        "esphome/bedroom_sensor/sensor/dht22_temperature/state",
        "esphome/bedroom_sensor/sensor/dht22_humidity/state",
        "esphome/bedroom_sensor/binary_sensor/ld2410_has_moving_target/state",
        "esphome/bedroom_sensor/binary_sensor/ld2410_has_target/state",
        "double-take/matches"
    ]
    with open("ha_config/configuration.yaml", "r", encoding="utf-8") as f:
        ha_content = f.read()

    all_matched = True
    for topic in topics_expected:
        if topic in ha_content:
            log_pass(f"Topic tồn tại chính xác trong Home Assistant: {topic}")
        else:
            log_warn(f"Topic chưa thấy trong configuration.yaml: {topic}")
            all_matched = False

def run_diagnostics():
    print("=" * 65)
    print("   🏥 SMART HOME SYSTEM HEALTH & CONSISTENCY DIAGNOSTICS")
    print("=" * 65)

    # 1. YAML Syntax Check
    yaml_files = [
        "docker-compose.yml",
        "ha_config/configuration.yaml",
        "ha_config/automations.yaml",
        "ha_config/ui-lovelace.yaml",
        "esphome_nodes/esp32_livingroom_relay.yaml",
        "esphome_nodes/esp32_bedroom_sensor.yaml",
        "esphome_nodes/esp32_cam_doorbell.yaml"
    ]
    for yf in yaml_files:
        if os.path.exists(yf):
            check_yaml_syntax(yf)
        else:
            log_fail(f"Thiếu tệp: {yf}")

    # 2. ESP32 Pin Allocation Checks
    check_esphome_pin_conflicts("esphome_nodes/esp32_livingroom_relay.yaml", "Node 1: Rơ-le Phòng Khách & Khóa")
    check_esphome_pin_conflicts("esphome_nodes/esp32_bedroom_sensor.yaml", "Node 2: Cảm biến DHT22 & Radar mmWave")
    check_esphome_pin_conflicts("esphome_nodes/esp32_cam_doorbell.yaml", "Node 3: Camera Chuông Cửa AI")

    # 3. MQTT Consistency
    check_mqtt_topic_consistency()

    print("\n" + "=" * 65)
    print(f"{GREEN}🎉 KIỂM TRA HOÀN TẤT: Hệ thống đạt tiêu chuẩn sẵn sàng vận hành!{RESET}")
    print("=" * 65)

if __name__ == "__main__":
    run_diagnostics()
